"""INS-024 embedded Diagnosis UI acceptance tests.

Run with ``python3 -B -m test_embed``. The v2 HTTP behavior and
server/legacy evaluation equivalence are also exercised by
``test_diagnosis_v2_contracts.py``; this suite locks the browser seam to those
v2 routes and verifies privacy, clinician authority, failure, focus, and
teardown behavior without introducing a browser framework.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ["DIAGNOSIS_AUTH_BYPASS"] = "1"
os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)

from diagnosis import page  # noqa: E402
from diagnosis.api import _read_page  # noqa: E402


def _served_page() -> str:
    return _read_page()


def test_single_embedded_entry_point() -> None:
    html = _served_page()
    assert html.count('id="diagnosis-root"') == 1
    assert "function createDiagnosisModule" in html
    assert "window.createDiagnosisModule = createDiagnosisModule" in html
    assert "opts.root" in html and "opts.apiBaseUrl" in html
    assert "opts && opts.patientId" not in html  # context is normalized in one path
    assert "patientId" in html and "encounterId" in html
    assert "return { mount, unmount, setAssessmentContext }" in html


def test_uuid_context_replaces_patient_code_state() -> None:
    html = _served_page()
    for forbidden in (
        "Patient code",
        "patient-code",
        "initialCode",
        "setPatientCode",
        "URLSearchParams",
        "location.search",
        "location.href",
        "history.replaceState",
        "?code=",
    ):
        assert forbidden not in html, f"legacy alias/navigation state remains: {forbidden}"
    assert "host-provided canonical Patient and Encounter UUIDs" in html
    assert "UUID_RE.test(context.patientId)" in html
    assert "UUID_RE.test(context.encounterId)" in html


def test_v2_http_only_and_no_alias_urls() -> None:
    html = _served_page()
    assert '"/api/diagnosis/v2/encounters/"' in html
    assert '"/assessments/latest"' in html
    assert '"/api/diagnosis/v2/assessments"' in html
    assert 'body: JSON.stringify(context)' in html
    assert '"X-Schema-Version": "2.0.0"' in html
    assert '"Idempotency-Key": createKey' in html
    assert '"If-Match": etag' in html
    assert '"X-CSRF-Token": csrfToken' in html
    assert '"/diagnosis/" + encodeURIComponent' not in html
    assert "patientId) +" not in html


def test_server_evaluation_is_the_only_ui_evaluation() -> None:
    html = _served_page()
    assert "renderLocalEvaluation" not in html
    assert "symptom_threshold" not in html
    assert "core_threshold" not in html
    assert "evaluation.aCount" in html
    assert "evaluation.coreCount" in html
    assert "evaluation.met" in html
    assert "assessment && assessment.evaluation.met" in html
    assert 'persistAssessment("confirmed")' in html
    assert 'clinicianDecision: decisionType ? {type: decisionType} : null' in html


def test_confirm_and_bypass_are_explicit_attributable_actions() -> None:
    html = _served_page()
    assert ">Confirm diagnosis</button>" in html
    assert ">Record clinician bypass</button>" in html
    assert 'window.confirm("Record an attributable clinician bypass' in html
    assert 'persistAssessment("bypass")' in html
    assert "Recorded by the authenticated psychiatrist." in html
    assert "evaluation.met ?" in html
    assert "clinicianDecision =" not in html


def test_persistence_failure_is_visible_and_focusable() -> None:
    html = _served_page()
    assert 'role="alert" tabindex="-1"' in html
    assert "error.focus()" in html
    assert 'saveState.textContent = "Not saved"' in html
    assert "if (!response.ok) throw new Error" in html
    assert "renderServer(assessment)" in html
    assert "alert(" not in html


def test_keyboard_and_focus_contract() -> None:
    html = _served_page()
    assert 'type="checkbox"' in html
    assert '<button class="btn btn-primary"' in html
    assert 'id="' + "' + UID + 'workspace-heading\" tabindex=\"-1\"" in html
    assert '$("workspace-heading").focus()' in html
    assert ".btn:focus-visible, .crit input:focus-visible" in html
    assert "min-height: 44px" in html
    assert "prefers-reduced-motion: reduce" in html


def test_teardown_removes_resources_and_root_only() -> None:
    html = _served_page()
    assert "controller.abort()" in html
    assert "clearTimeout(saveTimer)" in html
    assert "node.removeEventListener(type, handler)" in html
    assert "listeners.length = 0" in html
    assert 'root.innerHTML = ""' in html
    assert "document.body.innerHTML" not in html


def test_context_switch_restarts_aborted_bootstrap_safely() -> None:
    html = _served_page()
    assert "criteria.length ? Promise.resolve() : loadMeta()" in html
    assert "csrfToken ? Promise.resolve() : ensureCsrfToken()" in html
    assert "controller = new AbortController()" in html
    assert "context = normalized" in html
    assert "start();" in html


def test_embedded_mode_owns_no_host_navigation_or_chrome() -> None:
    html = _served_page()
    assert "if (!embedded)" in html
    assert "dm-topbar" in html
    assert '<header class="topbar">' not in html
    assert "Back to dashboard" not in html
    assert "history." not in html
    assert "location." not in html


def test_response_context_and_schema_fail_closed() -> None:
    html = _served_page()
    assert 'value.schemaVersion !== "2.0.0"' in html
    assert "value.patientId !== context.patientId" in html
    assert "value.encounterId !== context.encounterId" in html
    assert 'typeof value.evaluation.met !== "boolean"' in html
    assert "returned an incompatible assessment" in html


def test_javascript_parses_in_node() -> None:
    html = _served_page()
    script = html.split("<script>", 1)[1].split("</script>", 1)[0]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "diagnosis-ui.js"
        path.write_text(script, encoding="utf-8")
        result = subprocess.run(
            ["node", "--check", str(path)],
            text=True,
            capture_output=True,
            check=False,
        )
    assert result.returncode == 0, result.stderr


def test_read_page_back_compat_reexport() -> None:
    assert page._read_page is _read_page
    assert page._read_page() == _read_page()


def test_route_layer_unchanged() -> None:
    from diagnosis.app import app

    expected_paths = {
        "/",
        "/diagnosis/_meta",
        "/diagnosis/_csrf",
        "/internal/dashboard/module-routes/{moduleId}",
        "/internal/diagnosis/audit/{code}",
        "/api/diagnosis/v2/contract",
        "/api/diagnosis/v2/openapi.json",
        "/api/diagnosis/v2/diagnosis-assessment-v2.schema.json",
        "/api/diagnosis/v2/assessments",
        "/api/diagnosis/v2/assessments/{assessmentId}/audit",
        "/api/diagnosis/v2/assessments/{assessmentId}",
        "/api/diagnosis/v2/encounters/{encounterId}/assessment-snapshot",
        "/api/diagnosis/v2/encounters/{encounterId}/assessments/latest",
        "/diagnosis/{code}/init",
        "/diagnosis/{code}",
        "/health",
        "/ready",
    }
    paths = list(app.openapi()["paths"])
    assert set(paths) == expected_paths
    code_index = paths.index("/diagnosis/{code}")
    assert paths.index("/diagnosis/_meta") < code_index
    assert paths.index("/diagnosis/_csrf") < code_index


def test_bypass_serve_path_is_byte_clean() -> None:
    from fastapi.testclient import TestClient
    from diagnosis.app import app

    response = TestClient(app).get("/")
    assert response.status_code == 200, response.text
    assert response.text == _read_page()


def main() -> None:
    cases = [
        value for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    failures = []
    for case in cases:
        try:
            case()
            print(f"PASS  {case.__name__}")
        except Exception as error:  # noqa: BLE001 - standalone harness reports all cases
            failures.append((case.__name__, repr(error)))
            print(f"FAIL  {case.__name__}: {error}")
    if failures:
        print(f"\n{len(failures)}/{len(cases)} FAILED")
        raise SystemExit(1)
    print(f"\nOK: {len(cases)}/{len(cases)} INS-024 embed tests passed")


if __name__ == "__main__":
    main()
