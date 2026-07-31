"""Boot the diagnosis module as a standalone web app.

    python -m diagnosis              # http://localhost:8000
    python -m diagnosis --port 8010
"""
import argparse
import os


def main():
    # Self-checks run an in-process HTTP loopback. They bypass the real auth
    # dependency so they don't need a live auth service. The bypass is
    # scoped to this process; if the operator wants to assert absence of
    # auth in production they can grep the env table.
    #
    # Set before imports so startup configuration and the bypass warning see it.
    os.environ.setdefault("DIAGNOSIS_AUTH_BYPASS", "1")

    # Bind address defaults come from the settings adapter
    # (``DIAGNOSIS_HOST`` / ``DIAGNOSIS_PORT``); CLI flags still override for
    # ad-hoc dev runs (`--port 8010`). Imported after the bypass env is set so
    # the settings snapshot sees the self-check shim.
    from .config import settings
    parser = argparse.ArgumentParser(prog="diagnosis", description="Insight diagnosis module")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--reload", action="store_true", help="Hot-reload on file change (dev)")
    args = parser.parse_args()

    # Run six self-checks first; fail fast if anything is broken.
    from .criteria import _demo
    _demo()
    from .store import _store_selfcheck
    _store_selfcheck()
    from .patient import _patient_selfcheck
    _patient_selfcheck()
    from .readiness import _readiness_selfcheck
    _readiness_selfcheck()
    from .config import _config_selfcheck
    _config_selfcheck()
    from .api import _http_selfcheck
    _http_selfcheck()

    # Once real traffic would be served, drop the bypass and reload modules
    # that captured it. uvicorn binds *after* this — production sessions
    # hit the real auth dependency.
    os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)

    import uvicorn
    uvicorn.run("diagnosis.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
