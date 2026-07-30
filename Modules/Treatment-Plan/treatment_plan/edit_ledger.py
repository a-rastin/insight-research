"""Append-only Treatment Plan edit ledger (TP-15).

``PlanEditLedger`` is the public interface.  It preserves the generated Primary
Plan as an immutable fact and reconstructs the current review draft by replaying
attributable JSON Pointer edits.  Persistence is injected through ``PlanEditStore``
so the same concurrency rules are exercised by in-memory and SQLite adapters.
"""

from __future__ import annotations

import hashlib
import json
import threading
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Protocol, Sequence
from uuid import uuid4

from .observability import current_observability


class EditLedgerError(ValueError):
    pass


class PlanNotFound(EditLedgerError):
    pass


class PlanAlreadyExists(EditLedgerError):
    pass


class InvalidEdit(EditLedgerError):
    pass


class ReasonRequired(InvalidEdit):
    pass


class PreconditionRequired(EditLedgerError):
    pass


class PreconditionFailed(EditLedgerError):
    pass


class PlanFinalized(EditLedgerError):
    pass


class PlanSuperseded(EditLedgerError):
    pass


class EditCategory(str, Enum):
    ROUTINE = "routine"
    WARNING_REMOVAL = "warning-removal"
    SEVERE_DDI_OVERRIDE = "severe-ddi-override"
    URGENT_SETTING_OVERRIDE = "urgent-setting-override"
    POLICY_BOUND_OVERRIDE = "policy-bound-override"


@dataclass(frozen=True)
class PolicyBound:
    """A trusted policy constraint for one exact JSON Pointer."""

    minimum: float | None = None
    maximum: float | None = None
    allowed_values: tuple[Any, ...] | None = None

    def exceeded_by(self, value: Any) -> bool:
        if self.allowed_values is not None and value not in self.allowed_values:
            return True
        if self.minimum is not None or self.maximum is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return True
            if self.minimum is not None and value < self.minimum:
                return True
            if self.maximum is not None and value > self.maximum:
                return True
        return False


@dataclass(frozen=True)
class PlanEditEvent:
    edit_id: str
    plan_id: str
    actor_id: str
    session_id: str
    edited_at: str
    sequence: int
    path: str
    operation: str
    before: Any
    after: Any
    category: EditCategory
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": "1.1.0",
            "editId": self.edit_id,
            "planId": self.plan_id,
            "actorId": self.actor_id,
            "sessionId": self.session_id,
            "editedAt": self.edited_at,
            "sequence": self.sequence,
            "path": self.path,
            "operation": self.operation,
            "before": deepcopy(self.before),
            "after": deepcopy(self.after),
            "category": self.category.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PlanEditEvent":
        try:
            return cls(
                edit_id=str(value["editId"]),
                plan_id=str(value["planId"]),
                actor_id=str(value["actorId"]),
                session_id=str(value["sessionId"]),
                edited_at=str(value["editedAt"]),
                sequence=int(value["sequence"]),
                path=str(value["path"]),
                operation=str(value["operation"]),
                before=deepcopy(value.get("before")),
                after=deepcopy(value.get("after")),
                category=EditCategory(value["category"]),
                reason=value.get("reason"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidEdit("stored Plan Edit event is invalid") from exc


@dataclass(frozen=True)
class StoredPlanEdits:
    primary_plan: dict[str, Any]
    events: tuple[dict[str, Any], ...]
    finalization_record: dict[str, Any] | None = None


class PlanEditStore(Protocol):
    """Internal persistence seam; append is compare-and-swap atomic."""

    def create(self, plan_id: str, primary_plan: Mapping[str, Any]) -> None: ...
    def read(self, plan_id: str) -> StoredPlanEdits | None: ...
    def append(self, plan_id: str, expected_sequence: int, event: Mapping[str, Any]) -> None: ...
    def finalize(self, plan_id: str, expected_sequence: int, record: Mapping[str, Any]) -> None: ...
    def create_successor(
        self,
        prior_plan_id: str,
        successor_plan_id: str,
        primary_plan: Mapping[str, Any],
        record: Mapping[str, Any],
    ) -> None: ...
    def read_supersession(self, prior_plan_id: str) -> dict[str, Any] | None: ...


class InMemoryPlanEditStore:
    def __init__(self) -> None:
        self._plans: dict[str, dict[str, Any]] = {}
        self._events: dict[str, list[dict[str, Any]]] = {}
        self._finalizations: dict[str, dict[str, Any]] = {}
        self._supersessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, plan_id: str, primary_plan: Mapping[str, Any]) -> None:
        with self._lock:
            if plan_id in self._plans:
                raise PlanAlreadyExists(f"plan {plan_id!r} already exists")
            self._plans[plan_id] = _json_copy(primary_plan)
            self._events[plan_id] = []

    def read(self, plan_id: str) -> StoredPlanEdits | None:
        with self._lock:
            if plan_id not in self._plans:
                return None
            return StoredPlanEdits(
                _json_copy(self._plans[plan_id]),
                tuple(_json_copy(event) for event in self._events[plan_id]),
                _json_copy(self._finalizations[plan_id]) if plan_id in self._finalizations else None,
            )

    def append(self, plan_id: str, expected_sequence: int, event: Mapping[str, Any]) -> None:
        with self._lock:
            if plan_id not in self._plans:
                raise PlanNotFound(f"plan {plan_id!r} was not found")
            if plan_id in self._finalizations:
                raise PlanFinalized("the plan is already finalized")
            if len(self._events[plan_id]) != expected_sequence:
                raise PreconditionFailed("the plan changed after it was read")
            if int(event.get("sequence", -1)) != expected_sequence + 1:
                raise InvalidEdit("Plan Edit sequence is not contiguous")
            self._events[plan_id].append(_json_copy(event))

    def finalize(self, plan_id: str, expected_sequence: int, record: Mapping[str, Any]) -> None:
        with self._lock:
            if plan_id not in self._plans:
                raise PlanNotFound(f"plan {plan_id!r} was not found")
            if plan_id in self._finalizations:
                raise PlanFinalized("the plan is already finalized")
            if len(self._events[plan_id]) != expected_sequence:
                raise PreconditionFailed("the plan changed after its safety check")
            self._finalizations[plan_id] = _json_copy(record)

    def create_successor(
        self,
        prior_plan_id: str,
        successor_plan_id: str,
        primary_plan: Mapping[str, Any],
        record: Mapping[str, Any],
    ) -> None:
        with self._lock:
            if prior_plan_id not in self._plans:
                raise PlanNotFound(f"plan {prior_plan_id!r} was not found")
            if prior_plan_id not in self._finalizations:
                raise InvalidEdit("only a finalized plan can be superseded")
            if prior_plan_id in self._supersessions:
                raise PlanSuperseded("the finalized plan already has a successor")
            if successor_plan_id in self._plans:
                raise PlanAlreadyExists(f"plan {successor_plan_id!r} already exists")
            self._plans[successor_plan_id] = _json_copy(primary_plan)
            self._events[successor_plan_id] = []
            self._supersessions[prior_plan_id] = _json_copy(record)

    def read_supersession(self, prior_plan_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._supersessions.get(prior_plan_id)
            return _json_copy(value) if value is not None else None


@dataclass(frozen=True)
class PlanView:
    primary_plan: dict[str, Any]
    plan: dict[str, Any]
    edits: tuple[PlanEditEvent, ...]
    etag: str

    @property
    def version(self) -> int:
        return len(self.edits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primaryPlan": _json_copy(self.primary_plan),
            "plan": _json_copy(self.plan),
            "edits": [edit.to_dict() for edit in self.edits],
            "version": self.version,
        }


class PlanEditLedger:
    """Register, edit, and reconstruct plans through one deep interface."""

    def __init__(
        self,
        store: PlanEditStore,
        *,
        policy_bounds: Mapping[str, PolicyBound] | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._policy_bounds = dict(policy_bounds or {})
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        for path in self._policy_bounds:
            _editable_tokens(path)

    def register_primary_plan(self, primary_plan: Mapping[str, Any]) -> PlanView:
        plan = _json_copy(primary_plan)
        plan_id = plan.get("planId")
        if not isinstance(plan_id, str) or not plan_id.strip():
            raise InvalidEdit("Primary Plan requires a nonblank planId")
        if not isinstance(plan.get("content"), dict):
            raise InvalidEdit("Primary Plan requires object content")
        if not isinstance(plan.get("safetyFindings", []), list):
            raise InvalidEdit("Primary Plan safetyFindings must be an array")
        self._store.create(plan_id, plan)
        return self.get(plan_id)

    def get(self, plan_id: str) -> PlanView:
        stored = self._store.read(plan_id)
        if stored is None:
            raise PlanNotFound(f"plan {plan_id!r} was not found")
        primary = _json_copy(stored.primary_plan)
        current = _json_copy(primary)
        events: list[PlanEditEvent] = []
        for expected_sequence, raw in enumerate(stored.events, start=1):
            event = PlanEditEvent.from_dict(raw)
            if event.plan_id != plan_id or event.sequence != expected_sequence:
                raise InvalidEdit("stored Plan Edit stream is not contiguous")
            actual_before = _apply_pointer(current, event.operation, event.path, event.after)
            if actual_before != event.before:
                raise InvalidEdit("stored Plan Edit before value does not match replay state")
            events.append(event)
        return PlanView(primary, current, tuple(events), _etag(primary, len(events)))

    def edit(
        self,
        plan_id: str,
        *,
        expected_etag: str | None,
        actor_id: str,
        session_id: str,
        path: str,
        operation: str,
        after: Any = None,
        reason: str | None = None,
    ) -> PlanView:
        if expected_etag is None or not expected_etag.strip():
            raise PreconditionRequired("If-Match is required")
        if not str(actor_id).strip() or not str(session_id).strip():
            raise InvalidEdit("actor and session identifiers are required")
        if operation not in {"add", "replace", "remove"}:
            raise InvalidEdit("operation must be add, replace, or remove")
        tokens = _editable_tokens(path)
        view = self.get(plan_id)
        if expected_etag != view.etag:
            raise PreconditionFailed("If-Match does not match the current plan")

        working = _json_copy(view.plan)
        before = _apply_pointer(working, operation, path, _json_copy(after))
        category = self._category(view, tokens, operation, after)
        normalized_reason = str(reason).strip() if reason is not None else ""
        if category is not EditCategory.ROUTINE and not normalized_reason:
            raise ReasonRequired(f"{category.value} requires a nonblank reason")

        edited_at = self._clock()
        if edited_at.tzinfo is None:
            edited_at = edited_at.replace(tzinfo=timezone.utc)
        event = PlanEditEvent(
            edit_id=self._id_factory(),
            plan_id=plan_id,
            actor_id=str(actor_id).strip(),
            session_id=str(session_id).strip(),
            edited_at=edited_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            sequence=view.version + 1,
            path=path,
            operation=operation,
            before=before,
            after=None if operation == "remove" else _json_copy(after),
            category=category,
            reason=normalized_reason or None,
        )
        self._store.append(plan_id, view.version, event.to_dict())
        if category is not EditCategory.ROUTINE:
            current_observability().metric(
                "tp_override_total",
                labels={"category": category.value, "outcome": "success"},
            )
        return self.get(plan_id)

    def commit_finalization(
        self,
        plan_id: str,
        *,
        expected_etag: str | None,
        record: Mapping[str, Any],
    ) -> dict[str, Any]:
        if expected_etag is None or not expected_etag.strip():
            raise PreconditionRequired("If-Match is required")
        view = self.get(plan_id)
        if expected_etag != view.etag:
            raise PreconditionFailed("If-Match does not match the current plan")
        stored_record = _json_copy(record)
        self._store.finalize(plan_id, view.version, stored_record)
        return stored_record

    def get_finalization(self, plan_id: str) -> dict[str, Any] | None:
        stored = self._store.read(plan_id)
        if stored is None:
            raise PlanNotFound(f"plan {plan_id!r} was not found")
        return _json_copy(stored.finalization_record) if stored.finalization_record else None

    def commit_supersession(
        self,
        prior_plan_id: str,
        *,
        successor_primary_plan: Mapping[str, Any],
        record: Mapping[str, Any],
    ) -> dict[str, Any]:
        plan = _json_copy(successor_primary_plan)
        successor_plan_id = plan.get("planId")
        if not isinstance(successor_plan_id, str) or not successor_plan_id.strip():
            raise InvalidEdit("successor Primary Plan requires a nonblank planId")
        stored_record = _json_copy(record)
        self._store.create_successor(
            prior_plan_id, successor_plan_id, plan, stored_record
        )
        return stored_record

    def get_supersession(self, prior_plan_id: str) -> dict[str, Any] | None:
        if self._store.read(prior_plan_id) is None:
            raise PlanNotFound(f"plan {prior_plan_id!r} was not found")
        value = self._store.read_supersession(prior_plan_id)
        return _json_copy(value) if value is not None else None

    def _category(
        self,
        view: PlanView,
        tokens: Sequence[str],
        operation: str,
        after: Any,
    ) -> EditCategory:
        finding = _finding_for_pointer(view.plan, tokens)
        if finding and finding.get("category") == "interaction" and finding.get("severity") in {"high", "critical"}:
            overrides_status = len(tokens) >= 3 and tokens[2] == "status" and after in {"overridden", "resolved"}
            if operation == "remove" or overrides_status:
                return EditCategory.SEVERE_DDI_OVERRIDE
        if tokens[0] == "safetyFindings" and operation == "remove":
            return EditCategory.WARNING_REMOVAL
        if tokens == ["content", "setting"] and after != view.primary_plan.get("content", {}).get("setting"):
            if _has_active_urgent_recommendation(view.plan):
                return EditCategory.URGENT_SETTING_OVERRIDE
        bound = self._policy_bounds.get("/" + "/".join(_encode_token(token) for token in tokens))
        if operation != "remove" and bound is not None and bound.exceeded_by(after):
            return EditCategory.POLICY_BOUND_OVERRIDE
        return EditCategory.ROUTINE


def _etag(primary_plan: Mapping[str, Any], sequence: int) -> str:
    seed = _canonical_json(primary_plan) + ":" + str(sequence)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
    return f'"plan-{digest}"'


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise InvalidEdit("plan and edit values must be finite JSON values") from exc


def _json_copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _editable_tokens(path: str) -> list[str]:
    tokens = _pointer_tokens(path)
    if not tokens or tokens[0] not in {"content", "safetyFindings"}:
        raise InvalidEdit("edits are limited to /content and /safetyFindings")
    return tokens


def _pointer_tokens(path: str) -> list[str]:
    if not isinstance(path, str) or not path.startswith("/"):
        raise InvalidEdit("path must be an absolute JSON Pointer")
    tokens: list[str] = []
    for raw in path[1:].split("/"):
        decoded = ""
        index = 0
        while index < len(raw):
            if raw[index] != "~":
                decoded += raw[index]
                index += 1
                continue
            if index + 1 >= len(raw) or raw[index + 1] not in {"0", "1"}:
                raise InvalidEdit("path contains an invalid JSON Pointer escape")
            decoded += "~" if raw[index + 1] == "0" else "/"
            index += 2
        tokens.append(decoded)
    return tokens


def _encode_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _list_index(token: str, length: int, *, allow_end: bool) -> int:
    if token == "-" and allow_end:
        return length
    if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
        raise InvalidEdit("array path segments must be canonical nonnegative indexes")
    index = int(token)
    limit = length if allow_end else length - 1
    if index < 0 or index > limit:
        raise InvalidEdit("JSON Pointer array index is out of range")
    return index


def _resolve_parent(document: Any, tokens: Sequence[str]) -> tuple[Any, str]:
    if not tokens:
        raise InvalidEdit("the document root is not editable")
    current = document
    for token in tokens[:-1]:
        if isinstance(current, dict):
            if token not in current:
                raise InvalidEdit("JSON Pointer does not resolve")
            current = current[token]
        elif isinstance(current, list):
            current = current[_list_index(token, len(current), allow_end=False)]
        else:
            raise InvalidEdit("JSON Pointer traverses a scalar value")
    return current, tokens[-1]


def _apply_pointer(document: dict[str, Any], operation: str, path: str, after: Any) -> Any:
    tokens = _editable_tokens(path)
    parent, token = _resolve_parent(document, tokens)
    if isinstance(parent, dict):
        exists = token in parent
        if operation == "add":
            before = deepcopy(parent[token]) if exists else None
            parent[token] = deepcopy(after)
            return before
        if not exists:
            raise InvalidEdit("JSON Pointer does not resolve")
        before = deepcopy(parent[token])
        if operation == "replace":
            parent[token] = deepcopy(after)
        else:
            del parent[token]
        return before
    if isinstance(parent, list):
        if operation == "add":
            index = _list_index(token, len(parent), allow_end=True)
            parent.insert(index, deepcopy(after))
            return None
        index = _list_index(token, len(parent), allow_end=False)
        before = deepcopy(parent[index])
        if operation == "replace":
            parent[index] = deepcopy(after)
        else:
            parent.pop(index)
        return before
    raise InvalidEdit("JSON Pointer parent is not an object or array")


def _finding_for_pointer(plan: Mapping[str, Any], tokens: Sequence[str]) -> Mapping[str, Any] | None:
    if len(tokens) < 2 or tokens[0] != "safetyFindings" or not tokens[1].isdigit():
        return None
    findings = plan.get("safetyFindings", [])
    index = int(tokens[1])
    if not isinstance(findings, list) or index >= len(findings) or not isinstance(findings[index], dict):
        return None
    return findings[index]


def _has_active_urgent_recommendation(plan: Mapping[str, Any]) -> bool:
    findings = plan.get("safetyFindings", [])
    return isinstance(findings, list) and any(
        isinstance(finding, dict)
        and finding.get("category") == "urgent-risk"
        and finding.get("severity") in {"high", "critical"}
        and finding.get("status", "open") in {"open", "acknowledged"}
        for finding in findings
    )



