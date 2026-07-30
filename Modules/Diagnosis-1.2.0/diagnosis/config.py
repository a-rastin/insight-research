"""Settings adapter for the diagnosis module.

Single source of truth for every previously hard-coded knob the module
needs to integrate with the larger Insight app:

  * ``db_path``          — SQLite location (was ``DIAGNOSIS_DB_PATH``)
  * ``auth_url``         — Insight auth service base URL (was ``AUTH_BASE_URL``)
  * ``auth_timeout_s``   — auth HTTP timeout (was ``AUTH_TIMEOUT_S``)
  * ``patient_url``      — patient registry base URL (was ``PATIENT_BASE_URL``)
  * ``patient_timeout_s``— registry HTTP timeout (was ``PATIENT_TIMEOUT_S``)
  * ``patient_lookup``   — opt-in canonical id lookup (was
                           ``DIAGNOSIS_PATIENT_LOOKUP == "1"``)
  * ``cors_origins``     — CORS allow-origins for the standalone app (was the
                           hard-coded ``["*"]`` in ``app.py`` — comma-separated
                           via ``DIAGNOSIS_CORS_ORIGINS``)
  * ``mock_auth``        — the in-process self-check / offline-tests bypass
                           shim (was ``DIAGNOSIS_AUTH_BYPASS == "1"``).
                           Renamed surface, same env var so existing tooling
                           keeps working.
  * ``csrf_secret``      — pinned HMAC secret for multi-worker (was
                           ``DIAGNOSIS_CSRF_SECRET``)
  * ``csrf_secure``      — cookie ``Secure`` flag (was
                           ``DIAGNOSIS_CSRF_SECURE == "1"``)
  * ``module_base_path`` — the URL prefix the larger Insight app mounts the
                           router under (was hard-coded ``"/diagnosis"`` in
                           ``dashboard.MODULE_ID``'s launch href + the README
                           mount example). Read-only contract: the REST paths
                           themselves stay prefix-less so the mount prefix is
                           the parent app's choice; this knob only feeds the
                           Dashboard discovery descriptor's ``launch.href``
                           so the host dashboard links to the right place.
  * ``host`` / ``port``  — uvicorn bind address (was hard-coded in
                           ``__main__.py``'s argparse defaults).

Design (HANDOFF §3, deep-module ethos):
  - One ``Settings`` read at import time, frozen afterwards. The env is the
    only input; there is no second config file, no CLI override of the data
    plane (CLI ``--host/--port`` still override the bind address only — that
    is wiring, not a settings value the routes consume).
  - The other modules read ``settings.foo`` rather than re-fetching the env
    themselves, so the knob list is exhaustive here and the rest of the
    package stops scattering ``os.environ.get(...)`` calls.
  - Tests that need to mutate state still do it the way they always have:
    by flipping the module-level constants on ``auth.AUTH_BASE_URL`` /
    ``patient.PATIENT_BASE_URL`` / ``csrf._SECRET`` (the test-only
    ``reset_*_for_tests`` hooks). Those constants are initialised from
    ``settings`` but stay mutable module globals for the test surface — the
    settings singleton itself is read-only to production code.
  - Never logs, never raises on a missing value: every field carries the
    same default the prior hard-coded constant held so importing the module
    without any env set behaves identically to before.

This file is the only place to add a new integration knob. Anything that
grows the ``os.environ.get`` scatter in another module defeats the adapter.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field



def _env_truthy(name: str) -> bool:
    return os.environ.get(name) == "1"


def _env_list(name: str, default: list[str]) -> list[str]:
    """Comma-separated list env var. Empty / unset -> ``default``.

    A single ``*`` keeps the permissive localdev default so operators don't
    have to enumerate loopback origins by hand for the standalone boot.
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return list(default)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or list(default)


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of every integration knob the module reads.

    Frozen so a route handler can't accidentally mutate the shared singleton
    and have the change leak into another request's view of the world. The
    test-only reset hooks on ``auth`` / ``patient`` / ``csrf`` mutate *their*
    module globals, NOT this instance — production code never needs to write.
    """

    # Persistence.
    db_path: str

    # Auth delegation.
    auth_url: str
    auth_timeout_s: float

    # Patient identity adapter.
    patient_url: str
    patient_timeout_s: float
    patient_lookup: bool

    # Standalone app CORS.
    cors_origins: tuple[str, ...]

    # Self-check / offline-test bypass — production MUST leave this off.
    mock_auth: bool

    # CSRF.
    csrf_secret: bytes | None
    csrf_secure: bool

    # Mount path inside the larger Insight app (Dashboard discovery only).
    module_base_path: str

    # Standalone uvicorn bind address.
    host: str
    port: int

    @property
    def module_id(self) -> str:
        """Stable id this module advertises to Dashboard discovery.

        Derived from ``module_base_path`` so the launch href and the mount
        prefix never drift — the prefix's last path segment is the id the
        host dashboard looks up. For the default ``/diagnosis`` mount this
        stays ``"diagnosis"``; a mount under ``/tools/dx`` would surface
        ``"dx"``.
        """
        seg = self.module_base_path.rstrip("/").rsplit("/", 1)[-1]
        return seg or "diagnosis"

    @property
    def launch_href(self) -> str:
        """``/modules/<id>`` href the Dashboard descriptor points at.

        Stays aligned with ``module_id`` so the host dashboard links the
        user to the page the larger Insight app actually serves the module
        UI under.
        """
        return f"/modules/{self.module_id}"


def _load() -> Settings:
    """Read the env once at import time. Pure; never raises on absence —
    every field carries the prior hard-coded default so a bare import
    behaves identically to the pre-adapter module."""
    secret_raw = os.environ.get("DIAGNOSIS_CSRF_SECRET")
    return Settings(
        db_path=os.environ.get("DIAGNOSIS_DB_PATH") or "diagnosis_store.db",
        auth_url=os.environ.get("AUTH_BASE_URL") or "http://localhost:9000",
        auth_timeout_s=float(os.environ.get("AUTH_TIMEOUT_S") or "2.0"),
        patient_url=os.environ.get("PATIENT_BASE_URL") or "http://localhost:9000",
        patient_timeout_s=float(os.environ.get("PATIENT_TIMEOUT_S") or "2.0"),
        patient_lookup=_env_truthy("DIAGNOSIS_PATIENT_LOOKUP"),
        cors_origins=tuple(_env_list("DIAGNOSIS_CORS_ORIGINS", ["*"])),
        mock_auth=_env_truthy("DIAGNOSIS_AUTH_BYPASS"),
        csrf_secret=secret_raw.encode("utf-8") if secret_raw else None,
        csrf_secure=_env_truthy("DIAGNOSIS_CSRF_SECURE"),
        module_base_path=os.environ.get("DIAGNOSIS_MODULE_BASE_PATH") or "/diagnosis",
        host=os.environ.get("DIAGNOSIS_HOST") or "0.0.0.0",
        port=int(os.environ.get("DIAGNOSIS_PORT") or "8000"),
    )


# Singleton — imported by every consumer. Tests that need a different
# snapshot rebind the consumer module globals (the existing pattern), they
# don't reconstruct this instance.
settings = _load()


__all__ = ["Settings", "settings"]


# --- ponytail: one runnable self-check. No framework. Fail = bug. ----------
def _config_selfcheck() -> None:
    """Self-verify the adapter. Covers:
    - every previously hard-coded default surfaces unchanged when the env
      is blank
    - ``module_id`` derives from ``module_base_path`` and the launch href
      tracks it
    - ``cors_origins`` parses a comma list and honours ``*``
    - ``mock_auth`` reflects ``DIAGNOSIS_AUTH_BYPASS == "1"``
    - ``patient_lookup`` reflects ``DIAGNOSIS_PATIENT_LOOKUP == "1"``
    - a custom env set rebuilds a Settings with the operator's values

    Run: ``python -m diagnosis.config``
    """
    import os as _os

    saved = {
        k: _os.environ.get(k)
        for k in (
            "DIAGNOSIS_DB_PATH", "AUTH_BASE_URL", "AUTH_TIMEOUT_S",
            "PATIENT_BASE_URL", "PATIENT_TIMEOUT_S",
            "DIAGNOSIS_PATIENT_LOOKUP", "DIAGNOSIS_CORS_ORIGINS",
            "DIAGNOSIS_AUTH_BYPASS", "DIAGNOSIS_CSRF_SECRET",
            "DIAGNOSIS_CSRF_SECURE", "DIAGNOSIS_MODULE_BASE_PATH",
            "DIAGNOSIS_HOST", "DIAGNOSIS_PORT",
        )
    }
    try:
        # 1. Blank env -> prior hard-coded defaults verbatim.
        for k in saved:
            _os.environ.pop(k, None)
        s = _load()
        assert s.db_path == "diagnosis_store.db", s.db_path
        assert s.auth_url == "http://localhost:9000", s.auth_url
        assert s.auth_timeout_s == 2.0, s.auth_timeout_s
        assert s.patient_url == "http://localhost:9000", s.patient_url
        assert s.patient_timeout_s == 2.0, s.patient_timeout_s
        assert s.patient_lookup is False, s.patient_lookup
        assert s.cors_origins == ("*",), s.cors_origins
        assert s.mock_auth is False, s.mock_auth
        assert s.csrf_secret is None, s.csrf_secret
        assert s.csrf_secure is False, s.csrf_secure
        assert s.module_base_path == "/diagnosis", s.module_base_path
        assert s.module_id == "diagnosis", s.module_id
        assert s.launch_href == "/modules/diagnosis", s.launch_href
        assert s.host == "0.0.0.0", s.host
        assert s.port == 8000, s.port

        # 2. module_base_path under a nested prefix derives the last segment.
        _os.environ["DIAGNOSIS_MODULE_BASE_PATH"] = "/tools/dx"
        s = _load()
        assert s.module_base_path == "/tools/dx", s.module_base_path
        assert s.module_id == "dx", s.module_id
        assert s.launch_href == "/modules/dx", s.launch_href

        # 3. CORS parses a comma list; bare ``*`` survives.
        _os.environ["DIAGNOSIS_CORS_ORIGINS"] = (
            "https://insight.local, https://insight.test"
        )
        s = _load()
        assert s.cors_origins == (
            "https://insight.local", "https://insight.test",
        ), s.cors_origins
        _os.environ["DIAGNOSIS_CORS_ORIGINS"] = "*"
        assert _load().cors_origins == ("*",)

        # 4. mock_auth + patient_lookup are truthy gates.
        _os.environ["DIAGNOSIS_AUTH_BYPASS"] = "1"
        _os.environ["DIAGNOSIS_PATIENT_LOOKUP"] = "1"
        s = _load()
        assert s.mock_auth is True, s.mock_auth
        assert s.patient_lookup is True, s.patient_lookup

        # 5. CSRF secret pin + secure flag.
        _os.environ["DIAGNOSIS_CSRF_SECRET"] = "shared-secret"
        _os.environ["DIAGNOSIS_CSRF_SECURE"] = "1"
        s = _load()
        assert s.csrf_secret == b"shared-secret", s.csrf_secret
        assert s.csrf_secure is True, s.csrf_secure

        # 6. host / port override.
        _os.environ["DIAGNOSIS_HOST"] = "127.0.0.1"
        _os.environ["DIAGNOSIS_PORT"] = "9999"
        s = _load()
        assert s.host == "127.0.0.1", s.host
        assert s.port == 9999, s.port

        # 7. Unknown-but-set env values we'd inherit are honoured verbatim.
        _os.environ["DIAGNOSIS_DB_PATH"] = "/tmp/custom.db"
        _os.environ["AUTH_BASE_URL"] = "http://auth.internal:7000"
        _os.environ["PATIENT_BASE_URL"] = "http://patients.internal:7000"
        s = _load()
        assert s.db_path == "/tmp/custom.db", s.db_path
        assert s.auth_url == "http://auth.internal:7000", s.auth_url
        assert s.patient_url == "http://patients.internal:7000", s.patient_url

        # 8. Settings is frozen — mutating a field raises FrozenInstanceError.
        s = _load()
        try:
            s.host = "evil"  # type: ignore[misc]
            raise AssertionError("Settings should be frozen")
        except AttributeError:
            pass
    finally:
        for k, v in saved.items():
            if v is None:
                _os.environ.pop(k, None)
            else:
                _os.environ[k] = v

    print("OK: diagnosis config self-check passed")


if __name__ == "__main__":
    _config_selfcheck()
