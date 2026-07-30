"""Approval-gated PHI redaction with audit-record preservation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Collection, Literal


REQUIRED_APPROVER_ROLES = frozenset({"privacy_officer", "clinical_safety_officer"})


class RetentionApprovalRequired(PermissionError):
    pass


@dataclass(frozen=True)
class RetentionPolicy:
    policy_id: str
    approver_roles: frozenset[str]
    approved_at: datetime

    @classmethod
    def approved(
        cls, policy_id: str, approver_roles: Collection[str], approved_at: datetime
    ) -> "RetentionPolicy":
        roles = frozenset(role.strip() for role in approver_roles if role.strip())
        missing = REQUIRED_APPROVER_ROLES - roles
        if not policy_id.strip():
            raise RetentionApprovalRequired("retention policy identifier is required")
        if approved_at.tzinfo is None or approved_at.utcoffset() is None:
            raise RetentionApprovalRequired("retention approval time must include a timezone")
        if missing:
            raise RetentionApprovalRequired(
                "retention policy requires approval roles: " + ", ".join(sorted(missing))
            )
        return cls(policy_id.strip(), roles, approved_at)


@dataclass(frozen=True)
class RetentionResult:
    snapshots_redacted: int
    plans_redacted: int
    plan_versions_redacted: int
    plan_items_redacted: int
    safety_findings_redacted: int
    evidence_links_redacted: int
    plan_edits_preserved: int
    provenance_records_preserved: int


def apply_retention(
    connection: Any,
    dialect: Literal["sqlite", "postgres"],
    policy: RetentionPolicy,
    now: datetime,
) -> RetentionResult:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("retention time must include a timezone")
    if not REQUIRED_APPROVER_ROLES <= policy.approver_roles:
        raise RetentionApprovalRequired("retention policy approval is incomplete")
    if policy.approved_at > now:
        raise RetentionApprovalRequired("retention policy approval cannot be in the future")
    placeholder = "?" if dialect == "sqlite" else "%s"
    cutoff: Any = now.isoformat() if dialect == "sqlite" else now
    expiry = (
        lambda column: f"datetime({column}) <= datetime({placeholder})"
        if dialect == "sqlite"
        else f"{column} <= {placeholder}"
    )

    snapshot_cursor = connection.execute(
        "UPDATE input_snapshots SET snapshot_envelope = NULL, deleted_at = "
        f"{placeholder} WHERE {expiry('phi_expires_at')} AND deleted_at IS NULL",
        (cutoff, cutoff),
    )
    expired_plans = "SELECT plan_id FROM plans WHERE " + expiry("phi_expires_at")
    version_cursor = connection.execute(
        "UPDATE plan_versions SET plan_envelope = NULL WHERE plan_id IN ("
        + expired_plans
        + ") AND plan_envelope IS NOT NULL",
        (cutoff,),
    )
    item_cursor = connection.execute(
        "UPDATE plan_items SET item_envelope = NULL WHERE version_id IN ("
        "SELECT version_id FROM plan_versions WHERE plan_id IN ("
        + expired_plans
        + ")) AND item_envelope IS NOT NULL",
        (cutoff,),
    )
    finding_cursor = connection.execute(
        "UPDATE safety_findings SET finding_envelope = NULL WHERE version_id IN ("
        "SELECT version_id FROM plan_versions WHERE plan_id IN ("
        + expired_plans
        + ")) AND finding_envelope IS NOT NULL",
        (cutoff,),
    )
    evidence_cursor = connection.execute(
        "UPDATE evidence_links SET evidence_reference = NULL, evidence_envelope = NULL "
        "WHERE (plan_item_id IN (SELECT item_id FROM plan_items WHERE version_id IN ("
        "SELECT version_id FROM plan_versions WHERE plan_id IN ("
        + expired_plans
        + "))) OR safety_finding_id IN (SELECT finding_id FROM safety_findings "
        "WHERE version_id IN (SELECT version_id FROM plan_versions WHERE plan_id IN ("
        + expired_plans
        + ")))) AND (evidence_reference IS NOT NULL OR evidence_envelope IS NOT NULL)",
        (cutoff, cutoff),
    )
    plan_cursor = connection.execute(
        "UPDATE plans SET deleted_at = "
        f"{placeholder} WHERE {expiry('phi_expires_at')} AND deleted_at IS NULL",
        (cutoff, cutoff),
    )
    edits = connection.execute("SELECT COUNT(*) FROM plan_edits").fetchone()[0]
    provenance = connection.execute("SELECT COUNT(*) FROM clinical_provenance").fetchone()[0]
    connection.commit()
    return RetentionResult(
        snapshot_cursor.rowcount,
        plan_cursor.rowcount,
        version_cursor.rowcount,
        item_cursor.rowcount,
        finding_cursor.rowcount,
        evidence_cursor.rowcount,
        int(edits),
        int(provenance),
    )
