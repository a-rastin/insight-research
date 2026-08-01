from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _read_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
    request = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            return error.code, json.loads(error.read().decode("utf-8"))
        finally:
            error.close()


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("data")
    return value if isinstance(value, dict) else payload


async def _fetch(url: str, timeout: float) -> tuple[int, dict[str, Any]] | None:
    if not url:
        return None
    try:
        return await asyncio.to_thread(_read_json, url, timeout)
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return None


async def ddi_status(readiness_url: str, timeout: float) -> dict[str, Any]:
    result = await _fetch(readiness_url, timeout)
    if result is None:
        return _unavailable("DDI readiness endpoint is unavailable.")
    status, payload = result
    body = _data(payload)
    reason = str(body.get("reason") or "Provider readiness check failed.")
    ready = 200 <= status < 300 and body.get("status") in {"ready", "healthy"}
    return {
        "readiness": {"state": "ready" if ready else "not-ready", "reason": "Provider reports ready." if ready else reason},
        "clinicalUse": {
            "state": "unknown" if ready else "blocked",
            "reason": "DDI provider does not publish clinical-use status." if ready else reason,
        },
    }


async def bn_status(readiness_url: str, status_url: str, timeout: float) -> dict[str, Any]:
    readiness_result, models_result = await asyncio.gather(
        _fetch(readiness_url, timeout),
        _fetch(status_url, timeout),
    )
    if readiness_result is None:
        readiness = {"state": "unavailable", "reason": "BN Manager readiness endpoint is unavailable."}
    else:
        status, payload = readiness_result
        body = _data(payload)
        ready = 200 <= status < 300 and body.get("status") == "ready"
        readiness = {
            "state": "ready" if ready else "not-ready",
            "reason": "Provider reports ready." if ready else str(body.get("reason") or "Provider readiness check failed."),
        }

    clinical_use = {"state": "unavailable", "reason": "BN Manager clinical-use status is unavailable."}
    if models_result is not None and 200 <= models_result[0] < 300:
        models = _data(models_result[1]).get("models")
        if isinstance(models, list) and models:
            states = sorted({str(model.get("clinical_use_status", "unknown")) for model in models if isinstance(model, dict)})
            if states:
                clinical_use = {
                    "state": states[0] if len(states) == 1 else "mixed",
                    "reason": "Provider-reported model clinical-use status: " + ", ".join(states) + ".",
                }
    return {"readiness": readiness, "clinicalUse": clinical_use}


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "readiness": {"state": "unavailable", "reason": reason},
        "clinicalUse": {"state": "unavailable", "reason": "Provider clinical-use status is unavailable."},
    }
