"""diagnosis module — DSM-5-TR schizophrenia criteria checklist for Insight.

Deep module: small REST interface (GET/PUT by patient code) hides the
DSM-5-TR evaluation logic. Standalone web app via `python -m diagnosis`.
Mountable as an APIRouter inside the larger Insight app.

ponytail: SQLite-backed repository adapter (`store.DiagnosisStore`) replaces
the prior in-memory dict; single-process, WAL journal, route contract stable.

Authentication: every protected route calls the Insight auth service at
``AUTH_BASE_URL/api/auth/v2/session`` and enforces role membership there —
this module never decodes JWTs and never reads the auth DB. Writes
require ``psychiatrist``; reads accept ``psychiatrist`` or ``admin``.
See ``auth.py`` for the contract and ``api.py`` for the wire-up.

Patient identity: write routes bind ``sessions.patient_id`` to the
canonical INSIGHT ``patient.id`` via internal REST lookup against the
"Add New Patient" registry (``patient.py``). No DB imports, no
primitives-app imports — the adapter forwards the incoming ``Cookie``
and reads the JSON back, mirroring ``auth.py``. Opt-in via
``DIAGNOSIS_PATIENT_LOOKUP=1``; default disabled preserves the prior
diagnosis-local identity for the self-check and offline tests.
"""
from .api import router
from .criteria import evaluate, get_criteria, meta_contract
from .readiness import check_readiness

# `app` is a heavier import (FastAPI). Expose lazily so importing the criteria
# engine alone (e.g. for the self-check) never requires FastAPI at runtime.
def get_app():
    from .app import app
    return app

__all__ = ["router", "evaluate", "get_criteria", "meta_contract",
           "get_app", "check_readiness"]
