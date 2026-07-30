"""Embeddable module UI tests for the diagnosis module.

Issue: replace the standalone HTML shell with an embeddable module UI
matching the "Add New Patient" pattern: ``createDiagnosisModule({root,
apiBaseUrl})``. The previous page baked a full standalone shell with a
"Back to dashboard" placeholder at index.html line 224. The new contract
makes the page an embeddable fn the host mounts with {root, apiBaseUrl};
the standalone GET / route bootstraps the same fn against ``document.body``.

This harness locks the embeddable UI contract:

1. served page bytes expose ``window.createDiagnosisModule`` (the host
   calls it; in embedded mode this is the only contract entry point);
2. served page no longer bakes a standalone shell header / topbar body
   markup at first paint — the .dm-topbar chrome is built ONLY by the
   function, gated on the ``embedded`` flag, so an embedded host does
   not get a second copy of the Insight topbar;
3. the served page no longer contains the placeholder "Back to dashboard"
   button text nor the standalone-shell body chrome that owned host
   navigation (host owns the back link / dashboard route);
4. ``page._read_page()`` still returns the same single string source
   of truth the page seam stamps the CSRF meta into (byte-clean under
   ``DIAGNOSIS_AUTH_BYPASS=1``); the route-order + pathset invariants
   (HANDOFF §9.4) are untouched — the route layer was not modified;
5. the standalone bootstrap path is self-contained: there is exactly one
   ``#diagnosis-root`` mount point in the served page, and the bootstrap
   calls ``createDiagnosisModule({root, apiBaseUrl: "", embedded: false})``
   against it.

We also exercise the function-level contract by extracting the JS source
from the served page and asserting on the parsed contract string — light,
no JS engine needed (a heuristic guard; the existing ponytail harnesses +
``test_routes`` cover the HTTP surface).

No test framework — ponytail style, mirrors ``test_routes.py`` /
``test_csrf.py``. Run: ``python -m test_embed``.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Make the diagnosis package importable regardless of cwd.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# The byte-clean assertions on `_read_page()` need the bypass ON so the
# page seam short-circuits CSRF-cookie stamping (matches test_csrf.py /
# test_unittest.py). Toggle before any diagnosis import.
os.environ["DIAGNOSIS_AUTH_BYPASS"] = "1"
os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)

from diagnosis import page                  # noqa: E402
from diagnosis.api import _read_page       # noqa: E402 — back-compat re-export


def _served_page() -> str:
    """The exact bytes ``GET /`` returns under the auth bypass (the
    byte-clean path — no CSRF meta / cookie stamping). Mirrors the path
    test_csrf.py uses to assert the meta-tag injection."""
    return _read_page()


def test_read_page_is_embeddable_shell():
    """The served bytes are a single-page standalone shell that hosts
    an embeddable module. There must be exactly one mount point
    (``#diagnosis-root``) that the bootstrap fn mounts against."""
    html = _served_page()
    # Exactly one mount point. Multiple would let two bootstraps collide.
    count = html.count('id="diagnosis-root"')
    assert count == 1, ("expected exactly one #diagnosis-root mount", count)


def test_served_page_exposes_createDiagnosisModule():
    """The host grabs the entry point via
    ``window.createDiagnosisModule``. Lock the global assignment AND
    the fn declaration so a refactor that renames either fails loud."""
    html = _served_page()
    assert "function createDiagnosisModule" in html, "fn declaration missing"
    assert "window.createDiagnosisModule = createDiagnosisModule" in html, (
        "global assignment missing"
    )


def test_contract_signature_takes_root_and_apiBaseUrl():
    """The fn signature must read ``{root, apiBaseUrl}`` per the issue.
    The body destructures the two documented params (with `embedded` /
    `initialCode` optional). Assert the named keys surface in the fn
    body so a bare ``(opts)`` rename slips past nobody: project the
    closure-local reads that wire the embedded contract."""
    html = _served_page()
    # The fn must read opts.root and opts.apiBaseUrl.
    assert "opts.root" in html, "createDiagnosisModule must read opts.root"
    assert "opts.apiBaseUrl" in html, (
        "createDiagnosisModule must read opts.apiBaseUrl"
    )
    # apiBaseUrl must be strip-tolerant (a trailing slash from the host
    # like "/diagnosis/" must not double up). The fn body clips trailing
    # slashes — assert the regex is present.
    assert re.search(r"apiBaseUrl[^;]*replace\([^)]*\\\\?/\+", html) or \
           "replace(/\\\\?/+$/" in html or "/\\+" in html.replace("\\/", "/"), (
        "apiBaseUrl must strip trailing slash (host may pass '/diagnosis/')"
    )


def test_served_page_drops_back_to_dashboard_placeholder():
    """The previous shell baked a ``<button ... id="back-btn">Back to
    dashboard</button>`` placeholder (HANDOFF §4 pre-fix). The host
    owns navigation now; the embedded module must NOT bake any host
    navigation chrome."""
    html = _served_page()
    assert "Back to dashboard" not in html, (
        "embedded module must not own host navigation; remove 'Back to dashboard'"
    )
    assert 'id="back-btn"' not in html, (
        "the back-btn placeholder element must be gone"
    )
    # No "history.replaceState" outside the createDiagnosisModule closure,
    # and the closure only mutates history under embedded==false. Assert
    # the guard so a future edit doesn't silently leak host URL mutations.
    assert "history.replaceState" in html, (
        "standalone shell still owns URL ?code=... under embedded=false"
    )
    # history.replaceState must be gated by ``!embedded`` (the host case).
    # Find the call site and confirm there's no path that bypasses the
    # embedded-guard. We assert the guard text sits in the same function
    # block as the call.
    block = html[html.find("function _setInitialCode"):]
    block_end = block.find("\n      }")
    fn_block = block[:block_end if block_end != -1 else len(block)]
    assert "history.replaceState" in fn_block, (
        "_setInitialCode should own the standalone-only URL write"
    )
    # The fn must early-return when embedded so the host URL is preserved.
    assert "if (!embedded)" in fn_block or "if (embedded)" in fn_block, (
        "_setInitialCode must gate host history on the embedded flag"
    )


def test_served_page_does_not_bake_standalone_topbar_in_body_markup():
    """The previous shell baked ``<header class="topbar"><h1>Insight</h1>...``
    directly into ``<body>`` at first paint. The new contract moves that
    chrome into ``createDiagnosisModule.buildDom()``, gated by ``!embedded``,
    so an embedded host never gets a second topbar baked by the served
    page. Assert the served body markup no longer has the inline header
    chrome — the only baked markup is the mount point."""
    html = _served_page()
    # The standalone body must no longer bake `<header class="topbar">`
    # at first paint; the function builds `.dm-topbar` not `.topbar`.
    assert '<header class="topbar">' not in html, (
        "old standalone topbar markup still baked in body — host gets a second topbar"
    )
    assert '<h1>Insight</h1>' not in html.split("function createDiagnosisModule")[0], (
        "standalone shell still bakes <h1>Insight</h1> in body before the fn — "
        "move it inside createDiagnosisModule (gated on !embedded)"
    )
    # .dm-topbar (the new class built inside the fn) is allowed; .topbar
    # (the old baked class) is gone. Mirror that in the bytes.
    assert "dm-topbar" in html, "fn should build the standalone topbar (.dm-topbar)"
    assert "class=\"topbar\"" not in html, "old topbar class still referenced"


def test_embedded_flag_skips_topbar_chrome():
    """When opts.embedded is true, the fn must NOT render the
    ``<header class="dm-topbar">`` chrome — the Insight dashboard
    already shows its own page header. Assert the buildDom branch is
    gated on ``!embedded`` (``if (!embedded)``)."""
    html = _served_page()
    # The CSS rule `.dm-topbar { ... }` shows first; the actual JS
    # usage appears inside `function buildDom()`. Restrict the search to
    # the JS body so the guard substring we assert on is the buildDom
    # branch, not the style block.
    bd_idx = html.find("function buildDom")
    assert bd_idx != -1, "buildDom not found"
    # Slice the buildDom body — end at the next ws "function" line.
    js = html[bd_idx:]
    # The .dm-topbar create-at branch must sit inside buildDom.
    dm_idx = js.find(".dm-topbar")
    assert dm_idx != -1, "dm-topbar chrome entry not found inside buildDom"
    js_pre = js[:dm_idx]
    assert "if (!embedded)" in js_pre, (
        ".dm-topbar must be built only when !embedded — host supplies its own header"
    )


def test_fn_returns_mount_unmount_handle():
    """The host needs to mount AND unmount the module cleanly (a
    dashboard that swaps patient panels must tearDown listeners + DOM).
    Assert the fn returns an object with ``mount`` + ``unmount`` keys."""
    html = _served_page()
    assert re.search(r"return\s*\{\s*mount[^,]*,\s*unmount[^,]*", html), (
        "createDiagnosisModule must return { mount, unmount } for clean teardown"
    )


def test_csrf_meta_token_still_read_via_meta_tag():
    """The page seam stamps ``<meta name="csrf-token">`` on serve (the
    byte-clean path under ``DIAGNOSIS_AUTH_BYPASS=1`` skips the stamp).
    The embedded fn must still read the CSRF token from that meta tag —
    it never re-implements the CSRF mint. Assert the JS reads
    ``meta[name="csrf-token"]``. The contract stays identical (HANDOFF
    §9.8); the embedded host must stamp the meta tag itself on its
    host page if it loads only the JS, OR call /diagnosis/_csrf first."""
    html = _served_page()
    assert 'meta[name="csrf-token"]' in html, (
        "createDiagnosisModule must still read the CSRF token from the meta tag"
    )
    assert "X-CSRF-Token" in html, (
        "createDiagnosisModule must stamp the X-CSRF-Token header on writes"
    )


def test_read_page_back_compat_reexport():
    """The page seam + ``diagnosis.api`` keep ``_read_page`` re-exported
    for tests + Insight callers (HANDOFF §9.10). The embeddable refactor
    must not break that re-export — existing routes wiring already locks
    it via ``test_routes.test_back_compat_reexports_from_api_seam``; here
    we add the page-module mirror assertion so a future split stays
    consistent."""
    assert page._read_page is _read_page, (
        "page._read_page must be the same callable re-exported from api"
    )
    assert page._read_page() is _read_page() or page._read_page() == _read_page(), (
        "_read_page must return the same source-of-truth bytes"
    )


def test_route_layer_unchanged():
    """The embeddable refactor touches ONLY ``static/index.html`` (the
    page bytes). Assert the route pathset + literal-before-/{code} order
    invariant (HANDOFF §9.4) is untouched — the standalone ``/`` route
    is still alive on the page seam, alongside the dashboard seam, the
    diagnosis REST seam, and the standalone ``/health`` + ``/ready``."""
    from diagnosis.app import app
    expected_paths = {
        "/",
        "/diagnosis/_meta",
        "/diagnosis/_csrf",
        "/internal/dashboard/module-routes/{moduleId}",
        # The audit-log seam (dashboard.py) exposes the persisted local
        # audit trail for the future Logs module — added in the audit-
        # event-seam issue. Under ``/internal/...`` so its ``{code}`` param
        # does NOT collide with the per-patient ``/{code}`` family.
        "/internal/diagnosis/audit/{code}",
        "/diagnosis/{code}/init",
        "/diagnosis/{code}",
        "/health",
        "/ready",
    }
    got = set(app.openapi()["paths"].keys())
    assert got == expected_paths, ("pathset changed — the embeddable refactor must touch only HTML", expected_paths, got)
    # Literal-before-/{code} ordering still holds.
    ordered = list(app.openapi()["paths"].keys())
    code_idx = ordered.index("/diagnosis/{code}")
    assert ordered.index("/diagnosis/_meta") < code_idx
    assert ordered.index("/diagnosis/_csrf") < code_idx
    assert ordered.index("/internal/dashboard/module-routes/{moduleId}") < code_idx
    # The audit-log seam lives under ``/internal/...`` so its ``{code}``
    # does NOT collide with ``/{code}``; still precede ``/{code}`` for the
    # literal-before-parameterized invariant (dashboard seam -> diagnosis
    # seam registration order).
    assert ordered.index("/internal/diagnosis/audit/{code}") < code_idx


def test_bypass_serve_path_is_byte_clean():
    """The page seam under ``DIAGNOSIS_AUTH_BYPASS=1`` returns the raw
    bytes (no CSRF meta stamp) — the contract ``test_csrf`` /
    ``test_unittest`` rely on. Lock the bypass path: normalized ``\\n``
    must equal the raw bytes _read_page() returns, so a future edit that
    accidentally injects the meta tag inside the bypass short fails."""
    raw = _read_page()
    from fastapi.testclient import TestClient
    from diagnosis.app import app
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200, r.text
    assert r.text == raw, (
        "bypass GET / must serve _read_page() byte-clean (no meta stamp under bypass)"
    )


def main() -> None:
    cases = [
        ("test_read_page_is_embeddable_shell",
         test_read_page_is_embeddable_shell),
        ("test_served_page_exposes_createDiagnosisModule",
         test_served_page_exposes_createDiagnosisModule),
        ("test_contract_signature_takes_root_and_apiBaseUrl",
         test_contract_signature_takes_root_and_apiBaseUrl),
        ("test_served_page_drops_back_to_dashboard_placeholder",
         test_served_page_drops_back_to_dashboard_placeholder),
        ("test_served_page_does_not_bake_standalone_topbar_in_body_markup",
         test_served_page_does_not_bake_standalone_topbar_in_body_markup),
        ("test_embedded_flag_skips_topbar_chrome",
         test_embedded_flag_skips_topbar_chrome),
        ("test_fn_returns_mount_unmount_handle",
         test_fn_returns_mount_unmount_handle),
        ("test_csrf_meta_token_still_read_via_meta_tag",
         test_csrf_meta_token_still_read_via_meta_tag),
        ("test_read_page_back_compat_reexport",
         test_read_page_back_compat_reexport),
        ("test_route_layer_unchanged",
         test_route_layer_unchanged),
        ("test_bypass_serve_path_is_byte_clean",
         test_bypass_serve_path_is_byte_clean),
    ]
    failures = []
    for name, fn in cases:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures.append((name, repr(e)))
            print(f"FAIL  {name}: {e}")

    if failures:
        print(f"\n{len(failures)}/{len(cases)} FAILED")
        sys.exit(1)
    print(f"\nOK: {len(cases)}/{len(cases)} embeddable-UI tests passed")


if __name__ == "__main__":
    main()
