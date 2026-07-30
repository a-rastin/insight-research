"""PHI-safe operational observability and security audit events (TP-20)."""
from __future__ import annotations

import hashlib
import logging
import re
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping
from uuid import UUID, uuid4

_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_LABEL = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")
_ALLOWED_LABELS = frozenset({"category", "dependency", "kind", "model", "module", "outcome", "policy_version", "version"})
_correlation: ContextVar[str] = ContextVar("tp_correlation_id", default="")
_current: ContextVar["Observability | None"] = ContextVar("tp_observability", default=None)


def safe_correlation_id(value: str | None) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return str(uuid4())


def opaque_id(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    return "sha256:" + hashlib.sha256(str(value).strip().encode("utf-8")).hexdigest()


def current_observability() -> "Observability":
    return _current.get() or _NULL


@dataclass(frozen=True)
class MetricPoint:
    name: str
    value: float
    labels: tuple[tuple[str, str], ...]
    correlation_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "labels": dict(self.labels), "correlationId": self.correlation_id}


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    recorded_at: str
    action: str
    outcome: str
    actor_id: str | None
    entity_id: str | None
    correlation_id: str

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "resourceType": "AuditEvent", "id": self.event_id, "recorded": self.recorded_at,
            "action": self.action, "outcome": self.outcome, "correlationId": self.correlation_id,
        }
        if self.actor_id:
            result["agent"] = {"who": {"identifier": {"value": self.actor_id}}}
        if self.entity_id:
            result["entity"] = [{"what": {"identifier": {"value": self.entity_id}}}]
        return result


class Observability:
    """Record operational signals and security audit events through one deep interface."""

    def __init__(self, *, logger: logging.Logger | None = None, enabled: bool = True) -> None:
        self._logger = logger or logging.getLogger("treatment_plan.observability")
        self._enabled = enabled
        self._lock = threading.RLock()
        self._points: list[MetricPoint] = []
        self._audit: list[AuditEvent] = []

    @contextmanager
    def bind(self, correlation_id: str | None) -> Iterator[str]:
        correlation = safe_correlation_id(correlation_id)
        correlation_token = _correlation.set(correlation)
        observer_token = _current.set(self)
        try:
            yield correlation
        finally:
            _current.reset(observer_token)
            _correlation.reset(correlation_token)

    @property
    def correlation_id(self) -> str:
        return _correlation.get() or safe_correlation_id(None)

    def metric(self, name: str, value: float = 1.0, *, labels: Mapping[str, str] | None = None) -> None:
        if not self._enabled:
            return
        if not _NAME.fullmatch(name):
            raise ValueError("metric name is not allowlisted structured text")
        normalized = self._labels(labels or {})
        point = MetricPoint(name, float(value), normalized, self.correlation_id)
        with self._lock:
            self._points.append(point)
        self._emit("metric.recorded", point.correlation_id, {"metric": name, "value": point.value, "labels": dict(normalized)})

    def audit(self, action: str, outcome: str, *, actor_id: str | None = None, entity_id: str | None = None) -> AuditEvent:
        if not _NAME.fullmatch(action) or outcome not in {"success", "denied", "failure"}:
            raise ValueError("audit action or outcome is invalid")
        event = AuditEvent(
            str(uuid4()), datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), action, outcome,
            str(actor_id).strip() if actor_id and str(actor_id).strip() else None,
            str(entity_id).strip() if entity_id and str(entity_id).strip() else None,
            self.correlation_id,
        )
        if self._enabled:
            with self._lock:
                self._audit.append(event)
            self._emit("security.audit", event.correlation_id, {
                "action": action, "outcome": outcome, "actor_id": opaque_id(event.actor_id), "entity_id": opaque_id(event.entity_id),
            })
        return event

    def audit_events(self, *, entity_id: str | None = None) -> tuple[AuditEvent, ...]:
        with self._lock:
            events = tuple(self._audit)
        return events if entity_id is None else tuple(event for event in events if event.entity_id == entity_id)

    def points(self) -> tuple[MetricPoint, ...]:
        with self._lock:
            return tuple(self._points)

    def dashboard(self) -> dict[str, Any]:
        totals: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        for point in self.points():
            key = (point.name, point.labels)
            totals[key] = totals.get(key, 0.0) + point.value
        metrics = [{"name": name, "labels": dict(labels), "value": value} for (name, labels), value in sorted(totals.items())]
        alerts: list[dict[str, str]] = []
        if self._total(totals, "tp_dependency_failure_total"):
            alerts.append({"severity": "warning", "name": "dependency-failures"})
        if self._total(totals, "tp_finalization_total", outcome="failure"):
            alerts.append({"severity": "critical", "name": "finalization-failures"})
        if self._total(totals, "tp_missing_input_total"):
            alerts.append({"severity": "warning", "name": "missing-inputs"})
        return {"status": "degraded" if alerts else "healthy", "metrics": metrics, "alerts": alerts}

    def prometheus(self) -> str:
        lines: list[str] = []
        for item in self.dashboard()["metrics"]:
            labels = item["labels"]
            suffix = "{" + ",".join(f'{key}="{value}"' for key, value in sorted(labels.items())) + "}" if labels else ""
            lines.append(f'{item["name"]}{suffix} {item["value"]:g}')
        return "\n".join(lines) + ("\n" if lines else "")

    @staticmethod
    def _labels(labels: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
        normalized: list[tuple[str, str]] = []
        for key, raw in labels.items():
            value = str(raw)
            if key not in _ALLOWED_LABELS or not _LABEL.fullmatch(value):
                raise ValueError("metric labels must use bounded non-clinical dimensions")
            normalized.append((key, value))
        return tuple(sorted(normalized))

    @staticmethod
    def _total(totals: Mapping[tuple[str, tuple[tuple[str, str], ...]], float], name: str, **required: str) -> float:
        return sum(value for (metric, labels), value in totals.items() if metric == name and all(dict(labels).get(key) == expected for key, expected in required.items()))

    def _emit(self, event: str, correlation_id: str, fields: Mapping[str, Any]) -> None:
        self._logger.info(event, extra={"tp_structured": {"event": event, "correlation_id": opaque_id(correlation_id), **fields}})


_NULL = Observability(logger=logging.getLogger("treatment_plan.observability.null"), enabled=False)
_NULL._logger.disabled = True
