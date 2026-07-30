"""Browser page seam for the diagnosis module.

The single ``GET /`` route serves the standalone web app
(``static/index.html``) and stamps a fresh signed CSRF token into both a
``<meta name="csrf-token">`` tag in the page head and the matching
``csrf`` cookie on the response, so the JS can echo it back on the next
write without an extra fetch. This is the only browser-facing surface;
the diagnosis REST routes live in ``diagnosis_api.py`` and the Dashboard
discovery + audit snapshot hooks live in ``dashboard.py``.

The page is gated by the read policy (``psychiatrist`` or ``admin``) so
the SPA never loads for an unauthenticated viewer. Under the auth
bypass (self-check / headless tests) the meta/cookie injection is
skipped so the served page is byte-clean for asserts.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from .auth import Session
from . import csrf as _csrf
from .deps import require_psychiatrist_or_admin


router = APIRouter()


def _read_page() -> str:
    """Read ``static/index.html`` once per request (no build step)."""
    here = Path(__file__).parent / "static" / "index.html"
    return here.read_text(encoding="utf-8")


@router.get("/", response_class=HTMLResponse)
def page(_: Session = Depends(require_psychiatrist_or_admin)):
    """Serve the SPA. Stamp a fresh signed CSRF token into the page
    (``<meta name="csrf-token">``) AND set the matching ``csrf`` cookie
    on the response so the JS can echo it back on the next write."""
    html = _read_page()
    # If a CSRF bypass is active (self-check / in-process tests) skip
    # the meta/cookie injection so the page is byte-clean for asserts.
    if os.environ.get("DIAGNOSIS_AUTH_BYPASS") == "1":
        return HTMLResponse(html)
    token = _csrf.mint()
    # The page has a fixed <head> we can splice into without a templating dep.
    meta_tag = f'<meta name="csrf-token" content="{token}">'
    marker = '<meta name="viewport"'
    injected = html.replace(marker, meta_tag + "\n    " + marker, 1)
    resp = HTMLResponse(injected)
    _csrf.set_cookie(resp, token)
    return resp


__all__ = ["router", "page", "_read_page"]
