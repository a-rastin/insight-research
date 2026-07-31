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

export TP_DATABASE_PATH="${TP_DATABASE_PATH:-/var/lib/insight/treatment-plan/treatment-plan.db}"
export TP_AUTHENTICATION_SESSION_URL="${TP_AUTHENTICATION_SESSION_URL:-http://127.0.0.1:8101/api/auth/v2/session}"
export TP_TRUSTED_INTERNAL_ORIGINS="${TP_TRUSTED_INTERNAL_ORIGINS:-http://127.0.0.1:8101}"
export TP_AUTH_STUB_ENABLED="false"

cd /opt/insight/Modules/Treatment-Plan
/opt/venv/bin/python -m treatment_plan.deployment migration-gate
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
