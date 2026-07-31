from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AssistantError(RuntimeError):
    pass


class AssistantUnavailable(AssistantError):
    pass


class InvalidAssistantRequest(AssistantError):
    pass


class AssistantProvider(Protocol):
    def advise(self, payload: Mapping[str, Any]) -> str: ...


_REDACTION_PATTERNS = (
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"),
    re.compile(r"\bMRN[- :]*[A-Za-z0-9-]+\b", re.IGNORECASE),
    re.compile(r"\bPT-[A-Za-z0-9-]+\b", re.IGNORECASE),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\w)"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ][0-9:.+-Z]+)?\b"),
    re.compile(r"\b\d+\s+(?:[A-Za-z]+\s+){0,4}(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln)\b", re.IGNORECASE),
    re.compile(r"\b(?:Patient\s+)?[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"),
)


def scrub_text(value: str) -> str:
    scrubbed = value
    for pattern in _REDACTION_PATTERNS:
        scrubbed = pattern.sub("[REDACTED]", scrubbed)
    return scrubbed


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items()}
    return value


def _text(source: Mapping[str, Any], key: str) -> str | None:
    value = source.get(key)
    return value if isinstance(value, str) else None


def project_treatment_plan_context(plan_view: Mapping[str, Any]) -> dict[str, Any]:
    primary = plan_view.get("primaryPlan")
    plan = plan_view.get("plan")
    if not isinstance(primary, Mapping) or not isinstance(plan, Mapping):
        raise InvalidAssistantRequest("the treatment plan view is invalid")
    content = plan.get("content")
    if not isinstance(content, Mapping):
        raise InvalidAssistantRequest("the treatment plan content is invalid")

    projected_content: dict[str, Any] = {}
    setting = _text(content, "setting")
    if setting is not None:
        projected_content["setting"] = setting

    medications = content.get("pharmacotherapy")
    if isinstance(medications, list):
        projected_content["pharmacotherapy"] = [
            {
                key: value
                for key in ("medicationCode", "codeSystem", "dose", "route", "frequency")
                if (value := _text(item, key)) is not None
            }
            for item in medications
            if isinstance(item, Mapping)
        ]

    appointment = content.get("nextAppointment")
    if isinstance(appointment, Mapping):
        projected_content["nextAppointment"] = {
            key: value
            for key in ("interval", "timezone")
            if (value := _text(appointment, key)) is not None
        }

    findings = plan.get("safetyFindings")
    projected_findings = []
    if isinstance(findings, list):
        projected_findings = [
            {
                key: value
                for key in ("category", "severity", "status", "summary")
                if (value := _text(item, key)) is not None
            }
            for item in findings
            if isinstance(item, Mapping)
        ]

    rationale = primary.get("rationale")
    projected_rationale = [item for item in rationale if isinstance(item, str)] if isinstance(rationale, list) else []
    return _scrub(
        {
            "page": "treatment-plan-review",
            "plan": {"content": projected_content, "safetyFindings": projected_findings},
            "rationale": projected_rationale,
        }
    )


@dataclass(frozen=True)
class HttpAssistantProvider:
    url: str
    timeout_seconds: float = 10.0

    def advise(self, payload: Mapping[str, Any]) -> str:
        request = Request(
            self.url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                result = json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise AssistantUnavailable("assistant provider is unavailable") from exc
        advisory = result.get("advisory") if isinstance(result, dict) else None
        if not isinstance(advisory, str) or not advisory.strip() or len(advisory) > 8000:
            raise AssistantUnavailable("assistant provider returned an invalid response")
        return advisory


class ReadOnlyAssistant:
    def __init__(self, provider: AssistantProvider):
        self._provider = provider

    def advise(self, plan_view: Mapping[str, Any], prompt: str) -> dict[str, str]:
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 1000:
            raise InvalidAssistantRequest("prompt must contain 1 to 1000 characters")
        payload = {
            "schemaVersion": "1.0.0",
            "instruction": (
                "Provide advisory decision-support text only. Do not diagnose, prescribe, "
                "approve, sign, finalize, or request tools. Psychiatrist review is required."
            ),
            "prompt": scrub_text(prompt.strip()),
            "pageContext": project_treatment_plan_context(plan_view),
            "tools": [],
            "providerUse": {"retain": False, "train": False},
        }
        advisory = scrub_text(self._provider.advise(payload).strip())
        return {
            "schemaVersion": "1.0.0",
            "status": "available",
            "label": "Advisory assistant. Psychiatrist review required.",
            "advisory": advisory,
        }
