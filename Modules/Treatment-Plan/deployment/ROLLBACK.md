# Treatment Plan rollback

Rollback changes only the container image. Never run down-migrations automatically: finalized plans, supersession links, edits, and provenance are immutable clinical records.

Before deployment, record the current immutable image digest and create a verified database backup. Deploy only after the migration gate, standalone smoke/recovery checks, unified-route check, SBOM scan, TP-01 gate, and TP-21 human-sign-off gate pass.

If health or integration checks fail, stop the new container, restore the prior image digest in `/etc/insight/treatment-plan/container.env`, and restart `treatment-plan-container.service`. Re-run readiness, unified-route, TLS/security-header, and recovery checks. Restore a database backup only after an approved data-recovery decision; an image rollback normally keeps the forward-compatible migrated database. Record the incident, image digests, schema versions, checks, approver, and timestamps in the controlled operations record.
