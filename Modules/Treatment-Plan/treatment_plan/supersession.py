"""Follow-up supersession seam (TP-18).

The public interface is :class:`PlanSuperseder`. It coordinates a fresh source
snapshot and a revalidated successor Primary Plan while leaving the signed prior
Final Plan untouched. The immutable relationship is stored separately from both
plans so a supersession never rewrites clinical history.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol
from uuid import UUID

from .edit_ledger import PlanEditLedger, PlanSuperseded


_SECTIONS = ("setting", "pharmacotherapy", "nextAppointment")
_DELTA_FIELDS = frozenset({
    "schemaVersion", "deltaId", "patientId", "priorEncounterId", "encounterId",
    "priorFinalPlanId", "recordedAt", "changes",
})
_CHANGE_FIELDS = frozenset({"domain", "summary", "sourceResourceId"})
_CHANGE_DOMAINS = frozenset({
    "diagnosis", "severity", "medical-history", "medication", "encounter",
})
_PRIMARY_PLAN_FIELDS = frozenset({
    "schemaVersion", "planId", "runId", "patientId", "encounterId", "status",
    "createdAt", "content", "rationale", "safetyFindings",
})
_SNAPSHOT_FIELDS = (
    "snapshotId", "patientId", "encounterId", "capturedAt", "diagnosis",
    "severity", "medicalHistory", "currentMedications", "sources",
)


class SupersessionError(ValueError):
    pass


@dataclass(frozen=True)
class RevalidatedPrimaryPlan:
    """Fresh generation plus an evidence-bearing revalidation reason per section."""

    primary_plan: Mapping[str, Any]
    section_revalidations: Mapping[str, str]


class FollowUpSnapshotProvider(Protocol):
    async def gather(self, patient_id: str, encounter_id: str) -> Mapping[str, Any]: ...


class SuccessorPlanGenerator(Protocol):
    async def generate(
        self,
        snapshot: Mapping[str, Any],
        prior_final_plan: Mapping[str, Any],
    ) -> RevalidatedPrimaryPlan: ...


@dataclass(frozen=True)
class SupersessionResult:
    primary_plan: dict[str, Any]
    supersession: dict[str, Any]


class PlanSuperseder:
    """Create one linked successor from a finalized plan and a Follow-up Delta."""

    def __init__(
        self,
        ledger: PlanEditLedger,
        snapshot_provider: FollowUpSnapshotProvider,
        generator: SuccessorPlanGenerator,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ledger = ledger
        self._snapshot_provider = snapshot_provider
        self._generator = generator
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def supersede(
        self,
        prior_primary_plan_id: str,
        follow_up_delta: Mapping[str, Any],
    ) -> SupersessionResult:
        delta = _json_copy(follow_up_delta)
        self._validate_delta(delta)

        existing = self._ledger.get_supersession(prior_primary_plan_id)
        if existing is not None:
            if existing.get("followUpDelta") != delta:
                raise PlanSuperseded("the finalized plan already has a different successor")
            successor = self._ledger.get(str(existing["successorPrimaryPlanId"]))
            return SupersessionResult(successor.primary_plan, existing)

        finalization = self._ledger.get_finalization(prior_primary_plan_id)
        if finalization is None:
            raise SupersessionError("only a finalized plan can be superseded")
        prior = _json_copy(finalization.get("finalPlan"))
        self._validate_prior(prior, delta)

        snapshot_value = self._snapshot_provider.gather(
            str(delta["patientId"]), str(delta["encounterId"])
        )
        snapshot = _json_copy(await _await_if_needed(snapshot_value))
        self._validate_snapshot(snapshot, delta)

        generated_value = self._generator.generate(snapshot, _json_copy(prior))
        generated = await _await_if_needed(generated_value)
        if not isinstance(generated, RevalidatedPrimaryPlan):
            raise SupersessionError("successor generator must return RevalidatedPrimaryPlan")

        successor = _json_copy(generated.primary_plan)
        self._validate_successor(successor, delta)
        comparisons = self._compare_sections(
            prior,
            successor,
            generated.section_revalidations,
            str(snapshot["snapshotId"]),
        )
        successor["rationale"] = [
            self._rationale(item, str(prior["planId"])) for item in comparisons
        ]

        created_at = _instant(self._clock(), "supersession time")
        record = {
            "schemaVersion": "1.0.0",
            "priorPrimaryPlanId": prior_primary_plan_id,
            "priorFinalPlanId": prior["planId"],
            "successorPrimaryPlanId": successor["planId"],
            "patientId": delta["patientId"],
            "priorEncounterId": delta["priorEncounterId"],
            "encounterId": delta["encounterId"],
            "snapshotId": snapshot["snapshotId"],
            "createdAt": created_at,
            "followUpDelta": delta,
            "sourceSnapshot": {
                "snapshotId": snapshot["snapshotId"],
                "capturedAt": snapshot["capturedAt"],
                "sources": _json_copy(snapshot["sources"]),
            },
            "sectionComparisons": comparisons,
        }
        record["contentHash"] = _hash_json(record)
        try:
            self._ledger.commit_supersession(
                prior_primary_plan_id,
                successor_primary_plan=successor,
                record=record,
            )
        except PlanSuperseded:
            committed = self._ledger.get_supersession(prior_primary_plan_id)
            if committed is None or committed.get("followUpDelta") != delta:
                raise
            committed_plan = self._ledger.get(
                str(committed["successorPrimaryPlanId"])
            ).primary_plan
            return SupersessionResult(committed_plan, committed)
        return SupersessionResult(_json_copy(successor), _json_copy(record))

    @staticmethod
    def _validate_delta(delta: Mapping[str, Any]) -> None:
        if set(delta) != _DELTA_FIELDS:
            raise SupersessionError("Follow-up Delta fields do not match schema 1.0.0")
        if delta.get("schemaVersion") != "1.0.0":
            raise SupersessionError("Follow-up Delta schemaVersion must be 1.0.0")
        for field in (
            "deltaId", "patientId", "priorEncounterId", "encounterId", "priorFinalPlanId"
        ):
            _required_uuid(delta.get(field), field)
        if delta["priorEncounterId"] == delta["encounterId"]:
            raise SupersessionError("a follow-up must use a new encounter")
        _parse_instant(delta.get("recordedAt"), "recordedAt")
        changes = delta.get("changes")
        if not isinstance(changes, list) or not changes:
            raise SupersessionError("Follow-up Delta changes must be a non-empty array")
        for index, change in enumerate(changes):
            if not isinstance(change, Mapping) or set(change) != _CHANGE_FIELDS:
                raise SupersessionError(f"Follow-up Delta change {index} is invalid")
            if change.get("domain") not in _CHANGE_DOMAINS:
                raise SupersessionError(f"Follow-up Delta change {index} has an unsupported domain")
            _nonblank(change.get("summary"), f"changes[{index}].summary")
            _nonblank(change.get("sourceResourceId"), f"changes[{index}].sourceResourceId")

    @staticmethod
    def _validate_prior(prior: Mapping[str, Any], delta: Mapping[str, Any]) -> None:
        if not isinstance(prior, Mapping):
            raise SupersessionError("stored finalization does not contain a Final Plan")
        if prior.get("schemaVersion") != "1.0.0" or prior.get("status") != "finalized":
            raise SupersessionError("prior plan must be a finalized Final Plan 1.0.0")
        for field in ("planId", "primaryPlanId", "patientId", "encounterId"):
            _required_uuid(prior.get(field), f"prior {field}")
        if prior["planId"] != delta["priorFinalPlanId"]:
            raise SupersessionError("Follow-up Delta priorFinalPlanId does not match the prior Final Plan")
        if prior["patientId"] != delta["patientId"]:
            raise SupersessionError("Follow-up Delta patientId does not match the prior Final Plan")
        if prior["encounterId"] != delta["priorEncounterId"]:
            raise SupersessionError("Follow-up Delta priorEncounterId does not match the prior Final Plan")
        content = prior.get("content")
        if not isinstance(content, Mapping) or any(section not in content for section in _SECTIONS):
            raise SupersessionError("prior Final Plan content is incomplete")
        expected_hash = prior.get("contentHash")
        payload = _json_copy(prior)
        payload.pop("contentHash", None)
        if expected_hash != _hash_json(payload):
            raise SupersessionError("prior Final Plan contentHash is invalid")

    @staticmethod
    def _validate_snapshot(snapshot: Mapping[str, Any], delta: Mapping[str, Any]) -> None:
        if snapshot.get("schemaVersion") != "1.0.0":
            raise SupersessionError("source snapshot schemaVersion must be 1.0.0")
        for field in _SNAPSHOT_FIELDS:
            if field not in snapshot:
                raise SupersessionError(f"source snapshot requires {field}")
        _required_uuid(snapshot.get("snapshotId"), "snapshotId")
        if snapshot["patientId"] != delta["patientId"] or snapshot["encounterId"] != delta["encounterId"]:
            raise SupersessionError("source snapshot patient and encounter must match the Follow-up Delta")
        _parse_instant(snapshot.get("capturedAt"), "capturedAt")
        sources = snapshot.get("sources")
        if not isinstance(sources, list) or not sources:
            raise SupersessionError("source snapshot requires authoritative source references")
        identities: set[tuple[str, str]] = set()
        for index, source in enumerate(sources):
            if not isinstance(source, Mapping):
                raise SupersessionError(f"source snapshot reference {index} is invalid")
            for field in ("module", "resourceId", "schemaVersion", "retrievedAt", "contentHash"):
                _nonblank(source.get(field), f"sources[{index}].{field}")
            identity = (str(source["module"]), str(source["resourceId"]))
            if identity in identities:
                raise SupersessionError("source snapshot references must be unique")
            identities.add(identity)
            _parse_instant(source["retrievedAt"], f"sources[{index}].retrievedAt")
            value = str(source["contentHash"])
            digest = value.removeprefix("sha256:")
            if (
                not value.startswith("sha256:")
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise SupersessionError("source snapshot contentHash must be a sha256 digest")
        source_ids = {resource_id for _, resource_id in identities}
        missing = sorted(
            str(change["sourceResourceId"])
            for change in delta["changes"]
            if str(change["sourceResourceId"]) not in source_ids
        )
        if missing:
            raise SupersessionError(
                "Follow-up Delta changes are absent from the new source snapshot: "
                + ", ".join(missing)
            )

    @staticmethod
    def _validate_successor(plan: Mapping[str, Any], delta: Mapping[str, Any]) -> None:
        if set(plan) != _PRIMARY_PLAN_FIELDS:
            raise SupersessionError("generated successor fields do not match Primary Plan 1.0.0")
        if plan.get("schemaVersion") != "1.0.0" or plan.get("status") != "generated":
            raise SupersessionError("successor must be a generated Primary Plan 1.0.0")
        for field in ("planId", "runId", "patientId", "encounterId"):
            _required_uuid(plan.get(field), f"successor {field}")
        if plan["patientId"] != delta["patientId"] or plan["encounterId"] != delta["encounterId"]:
            raise SupersessionError("successor patient and encounter must match the Follow-up Delta")
        _parse_instant(plan.get("createdAt"), "successor createdAt")
        content = plan.get("content")
        if not isinstance(content, Mapping) or set(content) != set(_SECTIONS):
            raise SupersessionError("successor content must contain exactly the three plan sections")
        _nonblank(content.get("setting"), "successor setting")
        medications = content.get("pharmacotherapy")
        if not isinstance(medications, list):
            raise SupersessionError("successor pharmacotherapy must be an array")
        for index, medication in enumerate(medications):
            if not isinstance(medication, Mapping):
                raise SupersessionError(f"successor pharmacotherapy item {index} is invalid")
            for field in ("medicationCode", "codeSystem", "dose", "route", "frequency"):
                _nonblank(
                    medication.get(field),
                    f"successor pharmacotherapy item {index} {field}",
                )
        appointment = content.get("nextAppointment")
        if not isinstance(appointment, Mapping):
            raise SupersessionError("successor nextAppointment must be an object")
        interval = _nonblank(appointment.get("interval"), "successor appointment interval")
        timezone_name = _nonblank(
            appointment.get("timezone"), "successor appointment timezone"
        )
        if not interval.startswith("P") or "/" not in timezone_name:
            raise SupersessionError("successor nextAppointment fields are invalid")
        if not isinstance(plan.get("safetyFindings"), list):
            raise SupersessionError("successor safetyFindings must be an array")

    @staticmethod
    def _compare_sections(
        prior: Mapping[str, Any],
        successor: dict[str, Any],
        reasons: Mapping[str, str],
        snapshot_id: str,
    ) -> list[dict[str, Any]]:
        if not isinstance(reasons, Mapping) or set(reasons) != set(_SECTIONS):
            raise SupersessionError("every Primary Plan section requires a revalidation reason")
        prior_content = prior["content"]
        current_content = successor["content"]
        comparisons: list[dict[str, Any]] = []
        for section in _SECTIONS:
            reason = _nonblank(reasons.get(section), f"{section} revalidation reason")
            unchanged = current_content[section] == prior_content[section]
            if unchanged:
                current_content[section] = _json_copy(prior_content[section])
            comparisons.append({
                "section": section,
                "status": "unchanged" if unchanged else "changed",
                "reason": reason,
                "prior": _json_copy(prior_content[section]),
                "current": _json_copy(current_content[section]),
                "revalidatedAgainstSnapshotId": snapshot_id,
            })
        return comparisons

    @staticmethod
    def _rationale(comparison: Mapping[str, Any], prior_final_plan_id: str) -> str:
        status = comparison["status"]
        verb = "remained unchanged after revalidation" if status == "unchanged" else "changed"
        return (
            f"{comparison['section']} {verb} from Final Plan {prior_final_plan_id} "
            f"against source snapshot {comparison['revalidatedAgainstSnapshotId']}: "
            f"{comparison['reason']}"
        )


async def _await_if_needed(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _json_copy(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
        )
    except (TypeError, ValueError) as exc:
        raise SupersessionError("supersession inputs must be finite JSON values") from exc


def _hash_json(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _nonblank(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SupersessionError(f"{field} is required")
    return value.strip()


def _required_uuid(value: Any, field: str) -> str:
    text = _nonblank(value, field)
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError) as exc:
        raise SupersessionError(f"{field} must be a UUID") from exc
    if parsed.int == 0 or str(parsed) != text:
        raise SupersessionError(f"{field} must be a canonical non-nil UUID")
    return text


def _parse_instant(value: Any, field: str) -> str:
    text = _nonblank(value, field)
    if not text.endswith("Z"):
        raise SupersessionError(f"{field} must be an RFC 3339 UTC instant")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise SupersessionError(f"{field} must be an RFC 3339 UTC instant") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise SupersessionError(f"{field} must be UTC")
    return parsed.isoformat().replace("+00:00", "Z")


def _instant(value: datetime, field: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SupersessionError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
