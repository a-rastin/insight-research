#!/bin/sh
set -eu

require() {
  eval "value=\${$1:-}"
  test -n "$value" || { printf '%s\n' "missing required environment variable: $1" >&2; exit 1; }
}

for variable in \
  INSIGHT_IMAGE INSIGHT_BASE_URL INSIGHT_BACKUP_DIR INSIGHT_BACKUP_KEY \
  INSIGHT_E2E_FIXTURE INSIGHT_FOLLOWUP_E2E_FIXTURE INSIGHT_E2E_RESTART_COMMAND \
  INSIGHT_RELEASES INSIGHT_CURRENT_STATE INSIGHT_ROLLBACK_IMAGE
do
  require "$variable"
done

case "$INSIGHT_IMAGE" in
  *@sha256:????????????????????????????????????????????????????????????????) ;;
  *) printf '%s\n' "INSIGHT_IMAGE must be a registry reference pinned by sha256 digest" >&2; exit 1 ;;
esac
case "$INSIGHT_BASE_URL" in
  https://*) ;;
  *) printf '%s\n' "INSIGHT_BASE_URL must use HTTPS" >&2; exit 1 ;;
esac

test -f "$INSIGHT_BACKUP_KEY"
test -f "$INSIGHT_E2E_FIXTURE"
test -f "$INSIGHT_FOLLOWUP_E2E_FIXTURE"
test -f "$INSIGHT_RELEASES"
test -f "$INSIGHT_CURRENT_STATE"
test "$(stat -c '%a' "$INSIGHT_BACKUP_KEY")" = 600

deploy/module-tests.sh
python3 -B -m unittest discover -s tests -v
python3 -B deploy/operations.py rollback \
  --releases "$INSIGHT_RELEASES" \
  --current-state "$INSIGHT_CURRENT_STATE" \
  --image "$INSIGHT_ROLLBACK_IMAGE"

docker compose -f deploy/compose.release.yaml config --quiet
docker compose -f deploy/compose.release.yaml pull
docker compose -f deploy/compose.release.yaml up -d

curl --fail --silent --show-error "$INSIGHT_BASE_URL/healthz" >/dev/null
curl --fail --silent --show-error "$INSIGHT_BASE_URL/readyz" >/dev/null

INSIGHT_E2E_BASE_URL="$INSIGHT_BASE_URL" \
  INSIGHT_E2E_FIXTURE="$INSIGHT_E2E_FIXTURE" \
  python3 -B -m unittest tests.test_ins058_gateway_e2e -v
INSIGHT_E2E_BASE_URL="$INSIGHT_BASE_URL" \
  INSIGHT_FOLLOWUP_E2E_FIXTURE="$INSIGHT_FOLLOWUP_E2E_FIXTURE" \
  INSIGHT_E2E_RESTART_COMMAND="$INSIGHT_E2E_RESTART_COMMAND" \
  python3 -B -m unittest tests.test_ins059_gateway_e2e -v

backup_result=$(docker compose -f deploy/compose.release.yaml exec -T insight \
  python deploy/operations.py backup \
  --destination /var/backups/insight \
  --key-file /run/secrets/backup-key)
manifest=$(printf '%s' "$backup_result" | python3 -c 'import json,sys; print(json.load(sys.stdin)["manifest"])')
docker compose -f deploy/compose.release.yaml exec -T insight \
  python deploy/operations.py restore \
  --manifest "$manifest" \
  --key-file /run/secrets/backup-key \
  --staging /tmp/release-restore \
  --report /var/backups/insight/restore-report_release.json \
  --verify-only

docker compose -f deploy/compose.release.yaml restart insight
curl --fail --retry 30 --retry-delay 1 --retry-all-errors --silent --show-error \
  "$INSIGHT_BASE_URL/readyz" >/dev/null

printf '%s\n' "INS-065 research-build release gates passed for $INSIGHT_IMAGE"
