"""Shared wiring for the diagnosis route seams.

The public router was split into three seams (see ``page.py``,
``dashboard.py``, ``diagnosis_api.py``). They all share:

- the process-wide ``DiagnosisStore`` instance (one SQLite connection,
  WAL journal; override path via ``DIAGNOSIS_DB_PATH``);
- the role-enforcement + CSRF dependencies, including the
  ``DIAGNOSIS_AUTH_BYPASS=1`` shim used by the in-process self-check and
  headless tests.

Centralising both here means the three seams never drift on policy or
store identity. Tests that reset the store import ``store`` from
``diagnosis.api`` (re-exported here for back-compat) — do not
instantiate ``DiagnosisStore`` elsewhere.
"""
from __future__ import annotations

import os

from .auth import Session, require_role
from . import csrf as _csrf
from .store import DiagnosisStore


# Process-wide store. One SQLite connection, WAL journal. Tests reset
# state via ``store.reset()`` (mirrored from ``diagnosis.api`` for any
# caller that still imports it there).
store = DiagnosisStore()


# --- Role + CSRF dependencies ---------------------------------------------
#
# Writes (init + put_session) require ``psychiatrist``; reads (the criteria
# tree, a saved session, the audit snapshot) accept either ``psychiatrist``
# or ``admin`` — clinicians read the same data they write, admins read for
# audit/review but never mutate clinical state.
#
# ``DIAGNOSIS_AUTH_BYPASS=1`` short-circuits BOTH the role dep and the CSRF
# dep so the in-process self-check and headless tests can drive writes
# without minting tokens or running a live auth service. It must NEVER be
# set in production — the import-time warning below makes any accidental
# carry-over loud before the server binds a port.
if os.environ.get("DIAGNOSIS_AUTH_BYPASS") == "1":
    import warnings as _warnings
    _warnings.warn(
        "DIAGNOSIS_AUTH_BYPASS=1 — auth enforcement disabled",
        RuntimeWarning,
    )

    def _bypass_dep() -> Session:  # type: ignore[no-redef]
        return Session(
            user_id="selfcheck",
            roles=frozenset({"psychiatrist", "admin"}),
            session_id=None,
        )

    require_psychiatrist = _bypass_dep
    require_psychiatrist_or_admin = _bypass_dep

    def require_csrf() -> None:  # type: ignore[no-redef]
        return None
else:
    require_psychiatrist = require_role("psychiatrist")
    require_psychiatrist_or_admin = require_role("psychiatrist", "admin")
    require_csrf = _csrf.require_csrf  # pyright: ignore[reportAssignmentType]


__all__ = [
    "store",
    "require_psychiatrist",
    "require_psychiatrist_or_admin",
    "require_csrf",
]
