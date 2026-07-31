#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

(cd "$ROOT/Modules/Auth" && python3 -B -m unittest discover -s tests -v)
(cd "$ROOT/Modules/Dashboard-1.2.0" && \
  python3 -B -m unittest -v && node test_dashboard_frontend.mjs)
(cd "$ROOT/Modules/Add-New-Patient-1.1.0" && \
  python3 -B -m unittest test_add_new_patient_backend.py test_encounter_v2_contracts.py -v && \
  node --test test_frontend.mjs)
(cd "$ROOT/Modules/Diagnosis-1.2.0" && \
  python3 -B -m test_unittest && python3 -B -m test_config && \
  python3 -B -m test_routes && python3 -B -m test_auth && \
  python3 -B -m test_csrf && python3 -B -m test_discovery && \
  python3 -B -m test_patient && python3 -B -m test_readiness && \
  python3 -B -m test_embed && \
  python3 -B -m unittest test_diagnosis_v2_contracts.py -v && \
  DIAGNOSIS_AUTH_BYPASS=0 python3 -B -m unittest test_diagnosis_v2_security.py -v)
(cd "$ROOT/Modules/Severity-1.1.0" && npm test)
(cd "$ROOT/Modules/Medical-History-1.0.0" && npm test)
(cd "$ROOT/Modules/DDI-Checker-1.2.0" && npm test)
(cd "$ROOT/Modules/BN-Manager-v.1.1.0/BN-Manager-v.1.1.0" && \
  UV_CACHE_DIR=/tmp/insight-uv-cache uv run --with httpx2 python -B -m unittest discover -s tests -v)
(cd "$ROOT/Modules/Suicide-Risk-1.0.0" && npm test)
(cd "$ROOT/Modules/Treatment-Plan" && python3 -B -m unittest discover -s tests -v)
(cd "$ROOT/Modules/Treatment-Plan/frontend" && npm test && npm run typecheck && npm run build)
