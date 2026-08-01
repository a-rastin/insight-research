#!/bin/sh
set -eu

for directory in \
  /var/lib/insight/authentication \
  /var/lib/insight/dashboard \
  /var/lib/insight/add-new-patient \
  /var/lib/insight/diagnosis \
  /var/lib/insight/severity \
  /var/lib/insight/medical-history \
  /var/lib/insight/ddi-checker \
  /var/lib/insight/bn-manager \
  /var/lib/insight/suicide-risk \
  /var/lib/insight/treatment-plan
do
  test -d "$directory" && test -w "$directory"
done

seed_registry() {
  source="$1"
  target="$2"
  if [ ! -e "$target" ]; then
    temporary="${target}.seed"
    rm -rf "$temporary"
    cp -R "$source" "$temporary"
    mv "$temporary" "$target"
  fi
}

seed_registry /opt/insight/Modules/DDI-Checker-1.2.0/data /var/lib/insight/ddi-checker/registry
seed_registry /opt/insight/Modules/BN-Manager-v.1.1.0/BN-Manager-v.1.1.0/bn_manager_backend/model_registry /var/lib/insight/bn-manager/registry

export TP_DATABASE_PATH="${TP_DATABASE_PATH:-/var/lib/insight/treatment-plan/treatment-plan.db}"
export TP_AUTHENTICATION_SESSION_URL="${TP_AUTHENTICATION_SESSION_URL:-http://127.0.0.1:8101/api/auth/v2/session}"
export TP_DDI_BASE_URL="${TP_DDI_BASE_URL:-http://127.0.0.1:8107}"
export TP_DDI_SERVICE_AUTH_KEY_ID="${TP_DDI_SERVICE_AUTH_KEY_ID:-tp-ddi-v1}"
: "${DDI_SERVICE_AUTH_SECRET:?set DDI_SERVICE_AUTH_SECRET}"
export TP_DDI_SERVICE_AUTH_SECRET="${TP_DDI_SERVICE_AUTH_SECRET:-$DDI_SERVICE_AUTH_SECRET}"
export TP_TRUSTED_INTERNAL_ORIGINS="${TP_TRUSTED_INTERNAL_ORIGINS:-http://127.0.0.1:8101,http://127.0.0.1:8107}"
export TP_AUTH_STUB_ENABLED="false"

cd /opt/insight/Modules/Treatment-Plan
/opt/venv/bin/python -m treatment_plan.deployment migration-gate
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
