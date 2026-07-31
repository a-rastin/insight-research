# INS-065 Research-Build Release Runbook

## Scope

This runbook packages and verifies the approved `research-build` mode on an
Ubuntu VPS with Docker Engine, Compose, and host nginx. It does not authorize a
controlled-clinical deployment.

## Build And Pin

1. Run all module and root tests from a clean checkout.
2. Build with `docker build --pull --tag "$REGISTRY/insight:$VERSION" .`.
3. Push with `docker push "$REGISTRY/insight:$VERSION"`.
4. Resolve and record the registry digest with `docker image inspect --format '{{index .RepoDigests 0}}' "$REGISTRY/insight:$VERSION"`.
5. Set `INSIGHT_IMAGE` to that exact `repository@sha256:<64 hex characters>` reference. Never deploy a mutable tag.

## TLS Edge

1. Keep certificate and private-key files outside source control at
   `/etc/insight/tls/fullchain.pem` and `/etc/insight/tls/privkey.pem`.
2. Render `deploy/nginx-tls.conf.template` with an approved DNS hostname:
   `INSIGHT_HOSTNAME=insight.example.org envsubst '$INSIGHT_HOSTNAME' < deploy/nginx-tls.conf.template | sudo tee /etc/nginx/conf.d/insight.conf >/dev/null`.
3. Run `sudo nginx -t && sudo systemctl reload nginx`.
4. Restrict the container gateway to `127.0.0.1:8080`; expose only host nginx ports 80 and 443.

## Release Rehearsal

Set production secrets through the deployment secret store, plus:

- `INSIGHT_IMAGE`, using the pinned registry digest;
- `INSIGHT_BASE_URL`, using the public HTTPS origin;
- `INSIGHT_BACKUP_DIR` and a mode-`0600` `INSIGHT_BACKUP_KEY` outside source control;
- approved external no-PHI `INSIGHT_E2E_FIXTURE` and `INSIGHT_FOLLOWUP_E2E_FIXTURE` files;
- `INSIGHT_E2E_RESTART_COMMAND` for the deployed service;
- `INSIGHT_RELEASES`, `INSIGHT_CURRENT_STATE`, and `INSIGHT_ROLLBACK_IMAGE` for rollback compatibility rehearsal.

Run `deploy/release.sh`. It runs root/module gates, verifies rollback
compatibility without a down-migration, pulls the pinned image, starts the
module-owned migration gate, checks TLS liveness/readiness, runs initial and
follow-up gateway E2E suites, verifies encrypted backup/restore, restarts the
deployment, and verifies readiness again. Any failed or skipped required gate
blocks publication.

## Rollback

1. Stop rollout if readiness or an E2E gate fails; do not route clinical use to the deployment.
2. Preserve current module volumes and the failed release evidence.
3. Run `deploy/operations.py rollback` against current schema state and the approved release inventory.
4. Deploy only the returned digest. The command rejects images unable to read current schemas and never performs a down-migration.
5. Repeat TLS health/readiness, E2E, backup verification, restart, and provenance checks.

## Current Limitations

- DDI deliberately fails readiness with `production-rest-seam-unavailable`; current release rehearsal must stop at readiness.
- Approved initial/follow-up fixtures and deployment credentials are external and unavailable in this repository.
- Live browser/assistive-technology evidence, named assistant-provider evidence, calibrated model approval, scope approval, and controlled-clinical release approval remain absent.
- Technical research-build success would not authorize clinical deployment. `deploy/release-policy.json` remains `blocked` until all gates and approvals have attributable evidence.
