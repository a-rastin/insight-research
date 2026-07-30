"""API seam for the diagnosis module — the composed router.

The single ``router`` exported here (and re-exported from
``diagnosis.__init__``) is composed from three focused seams so each
concern lives in its own module:

    ``page.py``         -> browser page:          ``GET /``
    ``dashboard.py``    -> discovery interface:   ``GET /diagnosis/_meta``,
                                                    ``GET /diagnosis/_csrf``,
                                                    ``GET /internal/dashboard/module-routes/{moduleId}``,
                                                    the audit-snapshot hook
                                                    ``_dump_for_audit``.
    ``diagnosis_api.py`` -> protected diagnosis REST: ``POST /diagnosis/{code}/init``,
                                                    ``GET  /diagnosis/{code}``,
                                                    ``PUT  /diagnosis/{code}``.

Shared wiring (the process-wide ``DiagnosisStore`` instance + the
role/CSRF dependencies and the ``DIAGNOSIS_AUTH_BYPASS=1`` shim) lives
in ``deps.py``; the three seams import from there so policy never drifts.

REST contract is unchanged from the prior monolith: the same paths, the
same request/response shapes, ``router`` still mounts with
``app.include_router(router, prefix="/diagnosis")``. The split is purely
about seams — see HANDOFF.md and GRAPH_REPORT.md for the layout.

Route order invariant (HANDOFF.md §9.4): literal paths MUST be matched
before the parameterized ``/{code}`` route, or FastAPI captures
``_meta``/``_csrf`` into ``{code}`` and 404s. The composed router below
includes the page seam, then the dashboard seam (with the literal
``_meta`` / ``_csrf`` routes plus the ``/internal/dashboard/module-routes/{moduleId}``
discovery route — its ``{moduleId}`` parameter does NOT collide with the
``/{code}`` family because it lives under a distinct ``/internal/...`` prefix),
then the diagnosis seam (with ``/{code}``) — preserving the required order.

Re-exports for back-compat with tests / Insight callers that import
contract symbols from ``diagnosis.api``:
    ``store`` (from ``deps``), ``Submission`` and ``RESULT_FIELDS``
    (from ``diagnosis_api``), ``_dump_for_audit`` (from ``dashboard``),
    ``_read_page`` (from ``page``), ``_http_selfcheck`` (defined below).

Authentication & patient identity: see ``deps.py``, ``auth.py``,
``patient.py`` and HANDOFF.md §3 / §9. The bypass shim
(``DIAGNOSIS_AUTH_BYPASS=1``) shorts both auth and CSRF so the
in-process self-check can drive writes without minting tokens.
"""
from __future__ import annotations

import os

from fastapi import APIRouter

from . import deps as _deps
from .dashboard import _dump_for_audit, router as _dashboard_router
from .diagnosis_api import RESULT_FIELDS, Submission, router as _diagnosis_router
from .page import _read_page, router as _page_router
from .v2 import router as _v2_router

# Compose the three seams into ONE router in the order required by the
# route-order invariant: page (``/``) -> dashboard (literals
# ``/diagnosis/_meta`` + ``/diagnosis/_csrf``) -> diagnosis
# (parameterized ``/{code}`` family). Do not reorder.
#
# We register the sub-routers' routes directly onto ``router`` (rather
# than nesting ``router.include_router(sub)``) because FastAPI only
# unwraps one level of ``include_router`` when the parent app mounts us.
# The sub-router paths are already absolute (``/diagnosis/...`` or
# ``/``) and prefix-less, so appending the ``APIRoute`` objects preserves
# the declared order, their deps, and the literal-before-``/{code}``
# matching order — without losing routes through extra nesting.
router = APIRouter()
for _sub in (_page_router, _dashboard_router, _v2_router, _diagnosis_router):
    router.routes.extend(_sub.routes)

# Back-compat re-exports: tests and Insight callers import these from
# ``diagnosis.api`` directly (e.g. ``from diagnosis.api import store``).
store = _deps.store


def _http_selfcheck():
    """Run the REST-contract unittest cases under the bypass shim.

    The inline ``assert``-based HTTP contract smoke check used to live here;
    the cases now live in ``test_unittest.py`` (stdlib ``unittest``). This shim
    keeps the boot-time fail-fast contract (HANDOFF §9.5) — ``python -m
    diagnosis`` still runs it before uvicorn binds and raises ``SystemExit(1)``
    if anything failed — without duplicating the assertions. It loads TWO
    suites:

      - ``TestRestContract`` — route/persistence contract.
      - ``TestClinicianAuthority`` — model-never-decides invariant
        (HANDOFF §6.1). Auto-diagnosis logic or a rejected ``definite``
        bypass on an unmet checklist will fail the boot self-check.

    Runs under the ``DIAGNOSIS_AUTH_BYPASS=1`` shim (so writes don't need
    live auth / CSRF tokens); the suite asserts the readiness probe
    surfaces ``bypass=True`` as the same alarm a production gate would
    fire if the shim were left on.
    """
    import os
    import sys
    import pathlib
    import unittest

    os.environ["DIAGNOSIS_AUTH_BYPASS"] = "1"
    os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)

    _here = pathlib.Path(__file__).resolve().parents[1]
    if str(_here.parent) not in sys.path:
        sys.path.insert(0, str(_here.parent))
    loader = unittest.TestLoader()
    # ``TestRestContract`` locks the route/persistence contract.
    # ``TestClinicianAuthority`` locks the model-never-decides invariant
    # (HANDOFF §6.1) so the boot self-check fails fast if someone reintroduces
    # server-side logic that turns ``evaluate(...).met`` into an automatic
    # diagnosis or rejects a valid ``definite`` bypass.
    suite = loader.loadTestsFromName("test_unittest.TestRestContract")
    suite.addTests(loader.loadTestsFromName(
        "test_unittest.TestClinicianAuthority"))
    # ``TestAuditSeam`` locks the audit-event seam (issue: "Add audit event
    # seam") — every decision-bearing PUT persists a local audit event
    # and the dashboard ``GET /internal/diagnosis/audit/{code}`` route
    # exposes the chronological trail for the future Logs module. The
    # model-never-decides invariant extends into the audit row (no
    # ``evaluation`` key on snapshots), so this suite loads alongside the
    # existing authority + REST contract guards and fails the boot
    # self-check if a future change breaks the seam.
    suite.addTests(loader.loadTestsFromName("test_unittest.TestAuditSeam"))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("OK: diagnosis API self-check passed")


__all__ = [
    "router",
    "store",
    "Submission",
    "RESULT_FIELDS",
    "_dump_for_audit",
    "_read_page",
    "_http_selfcheck",
]
