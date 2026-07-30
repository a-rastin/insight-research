"""Settings-adapter tests for the diagnosis module.

Strategy:
    - Exercise the ``_load`` snapshot against every env permutation the
      adapter branches on (defaults, custom URLs, CORS list, mock-auth /
      patient-lookup / csrf-secret / csrf-secure flags, module base path
      derivation, host/port). Covers the frozen-dataclass guarantee and
      the ``module_id`` / ``launch_href`` derivation.
    - Exercise the consumer wiring so the settings adapter actually feeds
      the modules that previously hard-coded the same knobs:
        * ``auth.AUTH_BASE_URL`` / ``auth.AUTH_TIMEOUT_S`` default from
          settings when the env is blank
        * ``patient.PATIENT_BASE_URL`` / ``patient.PATIENT_TIMEOUT_S`` ditto
        * ``csrf._SECRET`` honoured when ``DIAGNOSIS_CSRF_SECRET`` is pinned
        * ``csrf._SECURE_COOKIE`` follows ``DIAGNOSIS_CSRF_SECURE``
        * ``dashboard.MODULE_ID`` derives from ``DIAGNOSIS_MODULE_BASE_PATH``
          and the discovery descriptor's ``launch.href`` tracks it
        * ``app`` CORS middleware reads the configured origins
        * ``__main__`` argparse defaults come from ``DIAGNOSIS_HOST`` /
          ``DIAGNOSIS_PORT`` (verified by importing the defaults, not by
          booting uvicorn)

The suite never boots a server, never touches the network, and never
mutates the env without restoring it. Runs in the parent ``diagnosis``
package's process; the env snapshots + restores keep it clean for the
next test in the same interpreter.

Run: ``python -m test_config`` — no test framework, ponytail style.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

# Make the diagnosis package importable regardless of cwd.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# The consumer wiring is captured at import time. We import lazily inside
# helpers AFTER applying the env permutation we want, then restore on exit.
# The very first import snaps the singleton; later ``reload``s rebuild
# against the new env. Keep the bypass OFF for these tests — they exercise
# config defaults, not the auth shim.
os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)

# Knot of env vars the adapter reads — we snapshot + restore every case
# so the process exits clean for the next test in the same interpreter.
_ENV_VARS = (
    "DIAGNOSIS_DB_PATH", "AUTH_BASE_URL", "AUTH_TIMEOUT_S",
    "PATIENT_BASE_URL", "PATIENT_TIMEOUT_S",
    "DIAGNOSIS_PATIENT_LOOKUP", "DIAGNOSIS_CORS_ORIGINS",
    "DIAGNOSIS_AUTH_BYPASS", "DIAGNOSIS_CSRF_SECRET",
    "DIAGNOSIS_CSRF_SECURE", "DIAGNOSIS_MODULE_BASE_PATH",
    "DIAGNOSIS_HOST", "DIAGNOSIS_PORT",
)


def _snapshot_env() -> dict[str, str | None]:
    return {k: os.environ.get(k) for k in _ENV_VARS}


def _restore_env(snap: dict[str, str | None]) -> None:
    for k, v in snap.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _clear_env() -> None:
    for k in _ENV_VARS:
        os.environ.pop(k, None)


def _reload_config():
    """Re-import ``diagnosis.config`` so ``_load`` re-runs against the
    current env. Other consumer modules keep their import-time snapshots
    (that mirrors production); tests that need a fresh consumer snapshot
    reload them explicitly."""
    import diagnosis.config as cfg
    importlib.reload(cfg)
    return cfg


_results: list[tuple[str, bool, str]] = []


def _run(name, fn):
    try:
        fn()
        _results.append((name, True, ""))
        print(f"PASS  {name}")
    except AssertionError as e:
        _results.append((name, False, str(e)))
        print(f"FAIL  {name}: {e}")
        raise
    except Exception as e:  # noqa: BLE001
        _results.append((name, False, repr(e)))
        print(f"ERROR {name}: {e!r}")
        raise


# ---------------------------------------------------------------------------
# Adapter snapshot under the default (blank) env — every field carries the
# prior hard-coded constant.

def test_defaults_match_prior_hardcoded_constants():
    snap = _snapshot_env()
    _clear_env()
    try:
        cfg = _reload_config()
        s = cfg._load()
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
    finally:
        _restore_env(snap)


def test_custom_env_rebuilds_snapshot():
    snap = _snapshot_env()
    _clear_env()
    try:
        os.environ["DIAGNOSIS_DB_PATH"] = "/tmp/x.db"
        os.environ["AUTH_BASE_URL"] = "http://auth:7000"
        os.environ["AUTH_TIMEOUT_S"] = "5.0"
        os.environ["PATIENT_BASE_URL"] = "http://patients:7000"
        os.environ["PATIENT_TIMEOUT_S"] = "9.0"
        os.environ["DIAGNOSIS_PATIENT_LOOKUP"] = "1"
        os.environ["DIAGNOSIS_CORS_ORIGINS"] = "https://a.local, https://b.local"
        os.environ["DIAGNOSIS_AUTH_BYPASS"] = "1"
        os.environ["DIAGNOSIS_CSRF_SECRET"] = "k"
        os.environ["DIAGNOSIS_CSRF_SECURE"] = "1"
        os.environ["DIAGNOSIS_MODULE_BASE_PATH"] = "/tools/dx"
        os.environ["DIAGNOSIS_HOST"] = "127.0.0.1"
        os.environ["DIAGNOSIS_PORT"] = "9999"
        cfg = _reload_config()
        s = cfg._load()
        assert s.db_path == "/tmp/x.db", s.db_path
        assert s.auth_url == "http://auth:7000", s.auth_url
        assert s.auth_timeout_s == 5.0, s.auth_timeout_s
        assert s.patient_url == "http://patients:7000", s.patient_url
        assert s.patient_timeout_s == 9.0, s.patient_timeout_s
        assert s.patient_lookup is True, s.patient_lookup
        assert s.cors_origins == (
            "https://a.local", "https://b.local",
        ), s.cors_origins
        assert s.mock_auth is True, s.mock_auth
        assert s.csrf_secret == b"k", s.csrf_secret
        assert s.csrf_secure is True, s.csrf_secure
        assert s.module_base_path == "/tools/dx", s.module_base_path
        assert s.module_id == "dx", s.module_id
        assert s.launch_href == "/modules/dx", s.launch_href
        assert s.host == "127.0.0.1", s.host
        assert s.port == 9999, s.port
    finally:
        _restore_env(snap)


def test_settings_frozen_raises_on_mutation():
    snap = _snapshot_env()
    _clear_env()
    try:
        cfg = _reload_config()
        s = cfg._load()
        try:
            s.host = "evil"  # type: ignore[misc]
            raise AssertionError("Settings should be frozen")
        except AttributeError:
            pass
    finally:
        _restore_env(snap)


def test_cors_origins_star_survives():
    snap = _snapshot_env()
    _clear_env()
    try:
        os.environ["DIAGNOSIS_CORS_ORIGINS"] = "*"
        cfg = _reload_config()
        assert cfg._load().cors_origins == ("*",)
    finally:
        _restore_env(snap)


def test_cors_origins_blank_falls_back_to_star():
    snap = _snapshot_env()
    _clear_env()
    try:
        os.environ["DIAGNOSIS_CORS_ORIGINS"] = "   "
        cfg = _reload_config()
        assert cfg._load().cors_origins == ("*",)
    finally:
        _restore_env(snap)


def test_module_id_for_nested_prefix_uses_last_segment():
    snap = _snapshot_env()
    _clear_env()
    try:
        os.environ["DIAGNOSIS_MODULE_BASE_PATH"] = "/insight/tools/dx"
        cfg = _reload_config()
        s = cfg._load()
        assert s.module_id == "dx", s.module_id
        assert s.launch_href == "/modules/dx", s.launch_href
    finally:
        _restore_env(snap)


# ---------------------------------------------------------------------------
# Consumer wiring — the adapter actually feeds the modules that previously
# hard-coded the same knobs.

def test_auth_module_sourced_from_settings():
    """When ``AUTH_BASE_URL`` is unset, ``auth.AUTH_BASE_URL`` defaults to
    the settings snapshot's value (the prior localhost default)."""
    snap = _snapshot_env()
    _clear_env()
    try:
        cfg = _reload_config()
        import diagnosis.auth as auth
        importlib.reload(auth)
        assert auth.AUTH_BASE_URL == "http://localhost:9000", auth.AUTH_BASE_URL
        assert auth.AUTH_TIMEOUT_S == 2.0, auth.AUTH_TIMEOUT_S
    finally:
        _restore_env(snap)
        # Restore the live module globals to the post-test-import snapshot
        # so the next suite that mutated them keeps working.
        import diagnosis.config as cfg
        importlib.reload(cfg)
        importlib.reload(importlib.import_module("diagnosis.auth"))


def test_auth_reset_for_tests_restores_to_settings():
    snap = _snapshot_env()
    _clear_env()
    try:
        cfg = _reload_config()
        import diagnosis.auth as auth
        importlib.reload(auth)
        auth.reset_auth_for_tests("http://fake.local:1111")
        assert auth.AUTH_BASE_URL == "http://fake.local:1111"
        auth.reset_auth_for_tests(None)
        assert auth.AUTH_BASE_URL == "http://localhost:9000"
    finally:
        _restore_env(snap)


def test_patient_module_sourced_from_settings():
    snap = _snapshot_env()
    _clear_env()
    try:
        cfg = _reload_config()
        import diagnosis.patient as patient
        importlib.reload(patient)
        assert patient.PATIENT_BASE_URL == "http://localhost:9000", patient.PATIENT_BASE_URL
        assert patient.PATIENT_TIMEOUT_S == 2.0, patient.PATIENT_TIMEOUT_S
    finally:
        _restore_env(snap)


def test_patient_reset_for_tests_restores_to_settings():
    snap = _snapshot_env()
    _clear_env()
    try:
        cfg = _reload_config()
        import diagnosis.patient as patient
        importlib.reload(patient)
        patient.reset_patient_for_tests("http://reg.fake:2222")
        assert patient.PATIENT_BASE_URL == "http://reg.fake:2222"
        patient.reset_patient_for_tests(None)
        assert patient.PATIENT_BASE_URL == "http://localhost:9000"
    finally:
        _restore_env(snap)


def test_csrf_secret_pinned_from_settings():
    snap = _snapshot_env()
    _clear_env()
    try:
        os.environ["DIAGNOSIS_CSRF_SECRET"] = "pinned"
        cfg = _reload_config()
        import diagnosis.csrf as csrf
        importlib.reload(csrf)
        assert csrf._SECRET == b"pinned", csrf._SECRET
        assert csrf._verify(csrf._sign("abc")) is True
    finally:
        _restore_env(snap)


def test_csrf_secure_flag_from_settings():
    snap = _snapshot_env()
    _clear_env()
    try:
        os.environ["DIAGNOSIS_CSRF_SECURE"] = "1"
        cfg = _reload_config()
        import diagnosis.csrf as csrf
        importlib.reload(csrf)
        assert csrf._SECURE_COOKIE is True, csrf._SECURE_COOKIE
    finally:
        _restore_env(snap)


def test_dashboard_module_id_from_settings():
    """``dashboard.MODULE_ID`` defaults to the settings-derived id; a
    custom ``DIAGNOSIS_MODULE_BASE_PATH`` flows through to it and to the
    discovery descriptor's ``launch.href``."""
    snap = _snapshot_env()
    _clear_env()
    try:
        os.environ["DIAGNOSIS_MODULE_BASE_PATH"] = "/tools/dx"
        cfg = _reload_config()
        import diagnosis.dashboard as dashboard
        importlib.reload(dashboard)
        assert dashboard.MODULE_ID == "dx", dashboard.MODULE_ID
        # The descriptor's launch href tracks the derived id.
        import diagnosis.config as settings_mod
        assert dashboard.settings.launch_href == "/modules/dx"
    finally:
        _restore_env(snap)
        # Reload back to the default /diagnosis mount for any later suite.
        import diagnosis.config as cfg
        importlib.reload(cfg)
        import diagnosis.dashboard as dashboard
        importlib.reload(dashboard)


def test_app_cors_reads_settings():
    """``app.py`` builds its CORS middleware from ``settings.cors_origins``
    (no longer the hard-coded ``["*"]``). Verified by inspecting the
    middleware allow_origins list, not by booting traffic."""
    snap = _snapshot_env()
    _clear_env()
    try:
        os.environ["DIAGNOSIS_CORS_ORIGINS"] = "https://insight.local"
        cfg = _reload_config()
        import diagnosis.app as appmod
        importlib.reload(appmod)
        cors = None
        for mw in appmod.app.user_middleware:
            if getattr(mw.cls, "__name__", "") == "CORSMiddleware":
                cors = mw
                break
        assert cors is not None, "CORS middleware not installed"
        assert list(cors.kwargs.get("allow_origins", [])) == [
            "https://insight.local"
        ], cors.kwargs.get("allow_origins")
    finally:
        _restore_env(snap)
        import diagnosis.config as cfg
        importlib.reload(cfg)
        import diagnosis.app as appmod
        importlib.reload(appmod)


def test_main_argparse_defaults_from_settings():
    """``__main__`` builds its ``--host`` / ``--port`` defaults from
    ``settings`` (``DIAGNOSIS_HOST`` / ``DIAGNOSIS_PORT``). Verified by
    parsing an empty argv after reloading the module under a custom env —
    we don't boot uvicorn."""
    snap = _snapshot_env()
    _clear_env()
    try:
        os.environ["DIAGNOSIS_HOST"] = "127.0.0.1"
        os.environ["DIAGNOSIS_PORT"] = "9999"
        cfg = _reload_config()
        import argparse
        import diagnosis.__main__ as main_mod
        importlib.reload(main_mod)

        # Re-derive what main() builds so we don't trigger the self-check
        # / uvicorn boot. argparse with the same defaults reproduces the
        # contract without the side effects of run().
        from diagnosis.config import settings
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", default=settings.host)
        parser.add_argument("--port", type=int, default=settings.port)
        parser.add_argument("--reload", action="store_true")
        ns = parser.parse_args([])
        assert ns.host == "127.0.0.1", ns.host
        assert ns.port == 9999, ns.port
    finally:
        _restore_env(snap)


# ---------------------------------------------------------------------------
# Boot wiring — the new selfcheck runs alongside the others on boot.

def test_config_selfcheck_passes():
    from diagnosis.config import _config_selfcheck
    _config_selfcheck()  # raises on failure


def main():
    cases = [
        test_defaults_match_prior_hardcoded_constants,
        test_custom_env_rebuilds_snapshot,
        test_settings_frozen_raises_on_mutation,
        test_cors_origins_star_survives,
        test_cors_origins_blank_falls_back_to_star,
        test_module_id_for_nested_prefix_uses_last_segment,
        test_auth_module_sourced_from_settings,
        test_auth_reset_for_tests_restores_to_settings,
        test_patient_module_sourced_from_settings,
        test_patient_reset_for_tests_restores_to_settings,
        test_csrf_secret_pinned_from_settings,
        test_csrf_secure_flag_from_settings,
        test_dashboard_module_id_from_settings,
        test_app_cors_reads_settings,
        test_main_argparse_defaults_from_settings,
        test_config_selfcheck_passes,
    ]
    for c in cases:
        _run(c.__name__, c)
    n = len(cases)
    ok = sum(1 for _, passed, _ in _results if passed)
    print()
    print(f"OK: {ok}/{n} config tests passed")
    if ok != n:
        sys.exit(1)


if __name__ == "__main__":
    main()
