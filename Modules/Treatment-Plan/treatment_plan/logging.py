import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Mapping

_SAFE_TOP_LEVEL = frozenset({"action", "actor_id", "correlation_id", "entity_id", "event", "labels", "metric", "outcome", "value"})
_SAFE_LABELS = frozenset({"category", "dependency", "kind", "model", "module", "outcome", "policy_version", "version"})


def _safe_fields(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"event": "unstructured.redacted"}
    result: dict[str, Any] = {}
    for key in _SAFE_TOP_LEVEL:
        item = value.get(key)
        if item is None:
            continue
        if key == "labels":
            if isinstance(item, Mapping):
                result[key] = {str(k): str(v) for k, v in item.items() if k in _SAFE_LABELS}
        elif key in {"actor_id", "correlation_id", "entity_id"} and isinstance(item, str):
            result[key] = item if item.startswith("sha256:") else "sha256:" + hashlib.sha256(item.encode("utf-8")).hexdigest()
        elif isinstance(item, (str, int, float, bool)):
            result[key] = item
    return result or {"event": "unstructured.redacted"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        structured = _safe_fields(getattr(record, "tp_structured", None))
        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            **structured,
        }, separators=(",", ":"), sort_keys=True)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)

