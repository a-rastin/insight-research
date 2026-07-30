"""Unittest test suite for the diagnosis module.

Replaces the assert-based smoke checks in ``criteria._demo()`` and
``api._http_selfcheck()`` with ``unittest`` cases (stdlib only — no new
dependency). The smoke-check shims in those modules now run the matching
``TestCase`` sets so the boot-time fail-fast contract (HANDOFF §9.5)
still holds without duplicating the assertions.

Coverage (per issue "Replace assert smoke checks with test suite"):
  - rules              -> ``TestCriteriaRules``          (pure ``evaluate``)
  - REST contract      -> ``TestRestContract``           (full api via TestClient)
  - audit seam         -> ``TestAuditSeam``              (PUT persists local audit event + ``GET /internal/diagnosis/audit/{code}`` trail)
  - auth rejection     -> ``TestAuthRejection``         (role dep fail-closed)
  - CSRF               -> ``TestCSRF``                   (verify + require_csrf)
  - persistence        -> ``TestPersistence``           (DiagnosisStore end-to-end)
  - clinician authority-> ``TestClinicianAuthority``   (model ``met`` never auto-decides / bypass invariant)
  - patient identity   -> ``TestPatientIdentity``       (resolve_patient + _build_patient)

Existing ponytail harnesses (``test_auth``, ``test_csrf``,
``test_discovery``, ``test_patient``, ``test_readiness``,
``test_routes``) cover the *integration* paths through fake auth/patient
servers at the HTTP level; this suite locks the *unit* contracts the
smoke checks guarded. They complement, not duplicate.

Run: ``python -m test_unittest``.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

# Make the diagnosis package importable regardless of cwd.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# The REST-contract + persistence + auth-shim tests need the bypass ON at
# ``deps.py`` import time (the module wires the dep callables once, at
# import, per HANDOFF §10). We set it before any ``diagnosis`` import so
# the ``_bypass_dep`` shim is bound for the whole suite. The pure-unit
# tests (criteria, csrf, patient) read their env at call time and don't
# care; the auth-rejection cases exercise ``auth.require_role`` directly
# so they're independent of the deps wiring.
os.environ["DIAGNOSIS_AUTH_BYPASS"] = "1"
os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)

from fastapi.testclient import TestClient  # noqa: E402

from diagnosis import auth as diag_auth          # noqa: E402
from diagnosis import csrf as diag_csrf          # noqa: E402
from diagnosis import patient as diag_patient   # noqa: E402
from diagnosis import store as diag_store       # noqa: E402
from diagnosis.app import app                   # noqa: E402
from diagnosis.api import _dump_for_audit, store as api_store  # noqa: E402
from diagnosis.criteria import (                # noqa: E402
    CRITERIA, Evaluation, evaluate, get_criteria,
)
from diagnosis.patient import (
    Patient, _build_patient, resolve_patient,
)


# ---------------------------------------------------------------------------
# Shared helpers
def _fake_request(*, cookies: dict | None = None, headers: dict | None = None):
    """Minimal stand-in for ``fastapi.Request`` for dep-level unittests.
    ``auth.require_role`` + ``csrf.require_csrf`` only read
    ``request.headers.get(...)`` / ``request.cookies.get(...)``, so a
    SimpleNamespace with dict-backed lookups is enough — no ASGI trip."""
    return types.SimpleNamespace(
        cookies=cookies or {},
        headers=headers or {},
    )


# ===========================================================================
# Rules — pure ``evaluate()``. Mirrors ``criteria._demo()`` + extras that
# lock the duration-vs-symptom semantics and the dedupe/order contract.
class TestCriteriaRules(unittest.TestCase):
    def test_empty_not_met(self):
        r = evaluate([])
        self.assertFalse(r.met)
        self.assertEqual(r.a_count, 0)
        self.assertEqual(r.core_count, 0)
        self.assertTrue(r.failures, "empty check must list failures")

    def test_one_symptom_not_met(self):
        r = evaluate(["A1"])
        self.assertFalse(r.met)
        self.assertEqual(r.a_count, 1)

    def test_two_symptoms_no_duration_no_guards_not_met(self):
        r = evaluate(["A1", "A4"])
        self.assertFalse(r.met)
        joined = " ".join(r.failures)
        self.assertIn("duration", joined)
        # Each guard not satisfied must surface separately.
        self.assertIn("Criterion B unmet", joined)
        self.assertIn("Schizoaffective not excluded", joined)
        self.assertIn("Substance/medical not excluded", joined)

    def test_two_symptoms_core_duration_all_guards_met(self):
        r = evaluate(["A1", "A5", "A6", "B1", "C1", "D1"])
        self.assertTrue(r.met, r.to_dict())
        self.assertEqual(r.core_count, 1)
        self.assertEqual(r.a_count, 2)
        self.assertEqual(r.failures, [])

    def test_two_non_core_symptoms_not_met_requires_core(self):
        r = evaluate(["A4", "A5", "A6", "B1", "C1", "D1"])
        self.assertFalse(r.met)
        self.assertIn("core triad", " ".join(r.failures))

    def test_missing_one_guard_not_met(self):
        r = evaluate(["A1", "A5", "A6", "B1", "C1"])  # D1 missing
        self.assertFalse(r.met)
        self.assertIn("Substance/medical", " ".join(r.failures))

    def test_a6_duration_does_not_count_as_symptom(self):
        # Two symptoms but A6 (duration) is one of them + only one true
        # symptom -> a_count must be 1, not 2.
        r = evaluate(["A1", "A6"])
        self.assertEqual(r.a_count, 1, r.to_dict())
        self.assertFalse(r.met)

    def test_a6_required_even_with_two_symptoms_and_core(self):
        # Per DSM-5-TR: 1-month duration must be established.
        r = evaluate(["A1", "A5", "B1", "C1", "D1"])
        self.assertFalse(r.met)
        self.assertIn("duration", " ".join(r.failures))

    def test_unknown_ids_kept_in_checked_but_not_counted(self):
        # Unknown ids stay in ``checked_ids`` (clinician-facing record)
        # but never inflate the A-symptom or core counts.
        r = evaluate(["A1", "A5", "A6", "B1", "C1", "D1", "X-nope", "Z"])
        self.assertTrue(r.met)
        self.assertIn("X-nope", r.checked_ids)
        self.assertEqual(r.a_count, 2)

    def test_duplicate_ids_dont_inflate_counts(self):
        once = evaluate(["A1", "A5", "A6", "B1", "C1", "D1"])
        dup = evaluate(["A1", "A1", "A5", "A5", "A6", "B1", "C1", "D1", "D1"])
        self.assertEqual(once.a_count, dup.a_count, (once, dup))
        self.assertTrue(dup.met)

    def test_get_criteria_returns_copies(self):
        tree = get_criteria()
        tree[0]["text"] = "MUTATED"
        fresh = get_criteria()
        self.assertNotEqual(fresh[0]["text"], "MUTATED")
        self.assertEqual(len(fresh), 9)

    def test_criteria_ids_stable(self):
        ids = [c["id"] for c in CRITERIA]
        self.assertEqual(ids, ["A1", "A2", "A3", "A4", "A5", "A6",
                                "B1", "C1", "D1"])

    def test_evaluation_to_dict_shape_matches_result_fields(self):
        # RESULT_FIELDS invariant: every key the API returns on GET/PUT
        # must be present in ``Evaluation.to_dict``.
        d = evaluate([]).to_dict()
        for field in ("met", "a_count", "core_count",
                      "failures", "reason", "checked"):
            self.assertIn(field, d, ("missing field", field))

    def test_met_contract_only_failures_drives_met(self):
        # met == (not failures). Definitional; do not add side logic.
        self.assertEqual(evaluate([]).met, False)
        self.assertEqual(
            evaluate(["A1", "A5", "A6", "B1", "C1", "D1"]).met, True)

    def test_meta_rules_match_engine_every_subset(self):
        # The optimistic UI derives its displayed numbers ONLY from
        # ``meta_contract()`` + the checked ids (see index.html
        # renderLocalEvaluation). This locks the contract against the
        # engine for every subset of the 9 criteria ids, so a rule change
        # in ``evaluate()`` can never silently drift from the UI — the
        # contract dict is the single source of truth. If this assert
        # fails after a rule edit, ship the new primitive in
        # ``meta_contract`` FIRST, not a JS constant.
        import itertools
        from diagnosis.criteria import meta_contract
        c = meta_contract()
        all_ids = [d["id"] for d in CRITERIA]
        for n in range(len(all_ids) + 1):
            for subset in itertools.combinations(all_ids, n):
                e = evaluate(list(subset))
                set_ids = set(subset)
                symptom_count = len(
                    [i for i in c["symptom_ids"] if i in set_ids])
                core_count = len(
                    [i for i in c["core_ids"] if i in set_ids])
                a_met = (symptom_count >= c["symptom_threshold"]
                         and core_count >= c["core_threshold"]
                         and c["duration_id"] in set_ids)
                # The numbers surfaced by the UI must equal the engine's.
                self.assertEqual(symptom_count, e.a_count, (subset, c, e.to_dict()))
                self.assertEqual(core_count, e.core_count, (subset,))
                # A-met (confirm-button enable) is a Criterion-A-only
                # projection; the engine also folds guards into ``met``.
                # Lock that the UI's aMet is EXACTLY the engine's A-rule
                # satisfaction, met independently of guards.
                engine_a_met = e.a_count >= 2 and e.core_count >= 1 and c["duration_id"] in set_ids
                self.assertEqual(a_met, engine_a_met, (subset, e.to_dict()))


# ===========================================================================
# REST contract — full ``api.py`` via TestClient under the bypass shim.
# Mirrors ``api._http_selfcheck()`` + persistence + patient-identity
# (disabled-env short) at the HTTP layer.
class TestRestContract(unittest.TestCase):
    """One TestClient for the class so the bypass-shimmed store is reset
    between tests."""

    @classmethod
    def setUpClass(cls):
        api_store.reset()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        api_store.reset()

    def test_health_alive(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True, "module": "diagnosis"})

    def test_ready_reports_bypass_alarm(self):
        # Running under the bypass shim -> readiness MUST surface
        # ``auth.bypass == True`` and ok == False (the same alarm a
        # production readiness gate would fire if the shim were left on).
        r = self.client.get("/ready")
        body = r.json()
        self.assertEqual(body["module"], "diagnosis")
        self.assertTrue(body["checks"]["db"]["ok"])
        self.assertTrue(body["checks"]["auth"]["bypass"])
        self.assertFalse(body["ok"])
        self.assertEqual(r.status_code, 503)

    def test_meta_returns_nine_criteria(self):
        r = self.client.get("/diagnosis/_meta")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["criteria"]), 9)

    def test_meta_serves_rule_contract(self):
        # The browser page's optimistic display derives its displayed
        # numbers from ``rules`` (criteria.meta_contract), served here —
        # not from a mirrored second copy of the DSM logic in JS. Every
        # primitive the engine reads must appear; a missing key breaks
        # the UI contract. If a rule edit needs a new primitive, add it
        # to ``criteria.meta_contract`` FIRST and update this shape.
        from diagnosis.criteria import meta_contract
        r = self.client.get("/diagnosis/_meta")
        self.assertEqual(r.status_code, 200)
        rules = r.json().get("rules")
        self.assertIsNotNone(rules, "_meta must ship a rules contract")
        expected = meta_contract()
        for key in ("symptom_ids", "core_ids", "duration_id",
                    "guard_ids", "symptom_threshold", "core_threshold"):
            self.assertEqual(rules.get(key), expected[key],
                             ("rules mismatch", key))

    def test_api_contract_doc_lists_every_live_route(self):
        # Lock the published REST contract (docs/api-contract.md §2 route
        # catalogue) against the live router's (method, path) set. If a
        # route is added / removed / renamed and the contract doc isn't
        # updated in the same change, this fails — the README summary is
        # NOT the canonical spec; docs/api-contract.md is (issue: "Write
        # canonical REST contract docs").
        doc = HERE / "docs" / "api-contract.md"
        self.assertTrue(doc.exists(),
                        "docs/api-contract.md is the canonical REST contract "
                        "— it must ship alongside the code")
        text = doc.read_text(encoding="utf-8")
        # Pull the catalogue rows: ``| METHOD | path | ...`` under §2.
        import re
        catalogue = set()
        for m in re.finditer(r"^\|\s*(GET|POST|PUT|DELETE|PATCH)\s*\|\s*`([^`]+)`",
                             text, re.MULTILINE):
            catalogue.add((m.group(1), m.group(2)))
        self.assertTrue(catalogue, "api-contract.md §2 route catalogue is empty")
        # The live router surface (the composed router in api.py + the two
        # standalone probes in app.py).
        from diagnosis.api import router as _composed
        from diagnosis.app import app as _app
        live = set()
        for r in _composed.routes:
            live.add((r.methods and next(iter(r.methods)) or "GET", r.path))
        # ``/health`` and ``/ready`` are declared directly on the standalone
        # app (``@app.get``), not on the composed router, so scrape them by
        # route path from the parent app's flat route list rather than the
        # included sub-router (which has no ``.path``).
        for path in ("/health", "/ready"):
            for r in _app.routes:
                if getattr(r, "path", None) == path:
                    live.add((next(iter(r.methods)), path))
                    break
        # Every live route MUST appear in the contract catalogue. The doc
        # may list MORE than the live set (e.g. deprecated siblings we
        # document for integrators); the contract is a superset, not a
        # 1:1 mapping, so we assert the subset direction.
        missing = sorted(live - catalogue)
        self.assertFalse(
            missing,
            ("live route(s) missing from docs/api-contract.md §2 "
             "catalogue: %r" % (missing,)),
        )

    def test_dashboard_discovery_descriptor_shape(self):
        r = self.client.get("/internal/dashboard/module-routes/diagnosis")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["moduleId"], "diagnosis")
        self.assertEqual(d["launch"]["href"], "/modules/diagnosis")

    def test_dashboard_discovery_unknown_module_404(self):
        r = self.client.get("/internal/dashboard/module-routes/not-a-module")
        self.assertEqual(r.status_code, 404)

    def test_full_init_get_put_contract(self):
        code = "__unittest__"

        # init creates the session.
        r = self.client.post(f"/diagnosis/{code}/init")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["created"])

        # get returns the empty session, decision None.
        r = self.client.get(f"/diagnosis/{code}")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["decision"])
        # patient_id falls back to the free-text code under the disabled
        # patient-lookup env (the bypass / self-check path).
        self.assertEqual(r.json()["patient_id"], code)

        # put with a not-met state -> evaluation.met False.
        r = self.client.put(f"/diagnosis/{code}",
                            json={"checked": ["A1"], "decision": None})
        self.assertFalse(r.json()["evaluation"]["met"])

        # put met path -> met True, decision confirmed persisted.
        r = self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1", "A5", "A6", "B1", "C1", "D1"],
            "decision": "confirmed",
        })
        e = r.json()
        self.assertTrue(e["evaluation"]["met"])
        self.assertEqual(e["decision"], "confirmed")

        # Subsequent GET reflects the persisted state.
        r = self.client.get(f"/diagnosis/{code}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["decision"], "confirmed")

    def test_bypass_decision_accepted_on_unmet_criteria(self):
        # Clinician-authority rule (HANDOFF §6): 'definite' is valid even
        # when ``met`` is false. The PUT MUST accept it.
        code = "__bypass_unit__"
        self.client.post(f"/diagnosis/{code}/init")
        r = self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1"], "decision": "definite",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["decision"], "definite")
        self.assertFalse(r.json()["evaluation"]["met"])

    def test_put_dedupe_preserves_order_at_api_layer(self):
        # The diagnosis_api.put_session handler dedupes via
        # ``dict.fromkeys(body.checked)`` before reaching the store.
        code = "__dedupe_unit__"
        self.client.post(f"/diagnosis/{code}/init")
        r = self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1", "A1", "A5", "A5"],
            "decision": None,
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["evaluation"]["checked"], ["A1", "A5"])

    def test_unknown_code_get_is_404(self):
        r = self.client.get("/diagnosis/__never_inited__")
        self.assertEqual(r.status_code, 404)

    def test_audit_snapshot_records_and_is_json(self):
        code = "__audit_unit__"
        self.client.post(f"/diagnosis/{code}/init")
        self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1", "A5", "A6", "B1", "C1", "D1"],
            "decision": "confirmed",
        })
        snap = _dump_for_audit(code)
        parsed = json.loads(snap)
        self.assertEqual(parsed["code"], code)
        self.assertEqual(parsed["decision"], "confirmed")


# ===========================================================================
# Audit seam (issue: "Add audit event seam"). ``put_session`` NOW persists a
# local audit event on every decision-bearing PUT via ``_dump_for_audit`` ->
# ``store.audit_snapshot`` (HANDOFF §10 invariant: the audit hook lives in
# the dashboard seam). The dashboard seam exposes the persisted trail through
# ``GET /internal/diagnosis/audit/{code}`` so the future Insight Logs module
# (and internal integrators) can READ without triggering a write. This suite
# locks: (1) every PUT adds a row; (2) ``init`` alone does NOT audit (it is
# empty-session creation, not a decision); (3) the audit route returns the
# chronological trail, oldest first; (4) snapshots carry the clinician's
# verbatim decision + checked ids and NO ``evaluation`` key (so an audit row
# can never be read as a server-derived auto-diagnosis — HANDOFF §6.1); and
# (5) a never-audited code yields an empty trail, NOT a 404.
class TestAuditSeam(unittest.TestCase):
    """PUT persists a local audit event AND the dashboard seam exposes the
    trail via ``GET /internal/diagnosis/audit/{code}``. Read policy (same as
    ``_meta`` / ``_csrf``) — admins audit, never mutate."""

    @classmethod
    def setUpClass(cls):
        api_store.reset()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        api_store.reset()

    def test_put_persists_audit_event(self):
        # A decision-bearing PUT MUST record a local audit event. The audit
        # table row's snapshot identifies the code, carries the clinician's
        # verbatim decision + the checked ids, and carries NO ``evaluation``
        # key — so the row is the source row, not a server re-evaluation (the
        # model-never-decides invariant stays intact in audit too).
        code = "__audit_put_unit__"
        self.client.post(f"/diagnosis/{code}/init")
        self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1", "A5", "A6", "B1", "C1", "D1"],
            "decision": "confirmed",
        })
        audits = api_store.list_audits(code)
        self.assertGreaterEqual(len(audits), 1,
                               "PUT must persist at least one audit event")
        snap = json.loads(audits[-1])
        self.assertEqual(snap["code"], code)
        self.assertEqual(snap["decision"], "confirmed")
        self.assertEqual(snap["checked"],
                         ["A1", "A5", "A6", "B1", "C1", "D1"])
        self.assertNotIn("evaluation", snap,
                         "audit snapshot must not embed a derived evaluation "
                         "that could be read as an automatic diagnosis")

    def test_init_alone_does_not_audit(self):
        # ``init`` is empty-session creation, not a clinician decision —
        # auditing it would pollute the future Logs trail with empty rows.
        code = "__audit_init_only__"
        self.client.post(f"/diagnosis/{code}/init")
        self.assertEqual(api_store.list_audits(code), [])

    def test_each_put_adds_an_audit_row_in_order(self):
        # Two decision-bearing PUTs MUST append two audit rows (N + N audit
        # events, oldest first). The route then reflects that order so the
        # Logs module reads a chronological trail, not a snapshot deduped by
        # the server.
        code = "__audit_order_unit__"
        self.client.post(f"/diagnosis/{code}/init")
        self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1"], "decision": "definite",
        })
        self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1", "A5", "A6", "B1", "C1", "D1"],
            "decision": "confirmed",
        })
        audits = api_store.list_audits(code)
        self.assertEqual(len(audits), 2, audits)
        self.assertEqual(json.loads(audits[0])["decision"], "definite")
        self.assertEqual(json.loads(audits[-1])["decision"], "confirmed")

    def test_audit_route_returns_chronological_trail(self):
        # ``GET /internal/diagnosis/audit/{code}`` exposes the persisted
        # trail to the future Logs module. It READS, never writes a
        # snapshot on demand — so the trail seen through the route equals
        # the trail persisted by the preceding PUTs, oldest first.
        code = "__audit_route_unit__"
        self.client.post(f"/diagnosis/{code}/init")
        self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1"], "decision": "definite",
        })
        self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1", "A5", "A6", "B1", "C1", "D1"],
            "decision": "confirmed",
        })
        r = self.client.get(f"/internal/diagnosis/audit/{code}")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["code"], code)
        snaps = body["snapshots"]
        self.assertEqual(len(snaps), 2, snaps)
        self.assertEqual(snaps[0]["decision"], "definite")
        self.assertEqual(snaps[-1]["decision"], "confirmed")
        # The snapshot exposes the clinician's voice + checked ids, NOT a
        # derived evaluation — invariant extends through the audit trail too.
        self.assertNotIn("evaluation", snaps[-1])

    def test_audit_route_unknown_code_returns_empty_trail(self):
        # ``code`` is the free-text local session key. A code with no
        # recorded audit events is a legitimate state — the route returns
        # an empty trail (status 200), NOT a 404. The Logs module treats
        # that as "no audit history yet".
        r = self.client.get("/internal/diagnosis/audit/__never_audited__")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {
            "code": "__never_audited__",
            "snapshots": [],
        })


# ===========================================================================
# Clinician-authority invariant (HANDOFF §6). The model's ``met`` is decision
# *support*, never a decision. The server MUST NOT:
#   - auto-set ``decision`` from ``evaluate(...).met`` on PUT;
#   - reject ``decision: "definite"`` (the bypass path) just because ``met`` is
#     false — clinician authority supersedes the checklist (institutional
#     protocol; the bypass button is always enabled in the UI);
#   - convert ``met == True`` into an automatic ``decision: "confirmed"`` —
#     the psychiatrist must explicitly send that affirmation; nor
#   - silently coerce a stored decision back toward what ``met`` would imply.
# All four cases lock here. They are grouped in one TestCase so they share the
# same TestClient fixtures and the boot self-check can load them as one unit
# (see ``diagnosis/api.py::_http_selfcheck``).
class TestClinicianAuthority(unittest.TestCase):
    """Pure-rule + REST contract mix: locks the no-auto-diagnosis invariant."""

    # ---------------------------------------------------------------- pure rule
    def test_met_false_never_implies_a_decision(self):
        # ``evaluate`` returns ``met`` as a boolean fact about the checklist;
        # it never returns a decision. A not-met evaluation must NOT be a
        # usable surrogate for ``decision``. Lock the shape: there is no
        # field on ``Evaluation`` whose name or presence could be mistaken
        # for a final call.
        r = evaluate([])
        self.assertFalse(r.met)
        for offlimits in ("decision", "diagnosis", "verdict", "confirmed",
                          "definite", "bypass"):
            self.assertFalse(hasattr(r, offlimits),
                             f"Evaluation must not expose {offlimits!r} — "
                             "that would invite auto-diagnosis logic")

    def test_met_true_is_not_a_confirmed_diagnosis(self):
        # Even a fully satisfied checklist is NOT a diagnosis on its own.
        # ``met`` is decision SUPPORT; the confirm button being enabled is
        # a UI affordance, not an automatic commit. ``evaluate`` carries no
        # path that turns met into a clinician decision.
        r = evaluate(["A1", "A5", "A6", "B1", "C1", "D1"])
        self.assertTrue(r.met)
        self.assertFalse(hasattr(r, "decision"))
        self.assertFalse(hasattr(r, "confirmed"))
        self.assertFalse(hasattr(r, "definite"))

    # ---------------------------------------------------------- REST contract
    @classmethod
    def setUpClass(cls):
        api_store.reset()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        api_store.reset()

    def _init(self, code: str):
        r = self.client.post(f"/diagnosis/{code}/init")
        self.assertEqual(r.status_code, 200, r.text)

    def test_bypass_accepted_when_criteria_unmet(self):
        # HANDOFF §6: ``decision: "definite"`` is ALWAYS a valid bypass —
        # the model's ``met`` is NOT consulted for the bypass path. PUT must
        # accept + persist it even when ``met`` is false.
        code = "__authority_bypass_unmet__"
        self._init(code)
        r = self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1"], "decision": "definite",
        })
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["decision"], "definite")
        self.assertFalse(body["evaluation"]["met"], body)
        # The bypass survives a fresh GET — server did not "fix" it.
        got = self.client.get(f"/diagnosis/{code}").json()
        self.assertEqual(got["decision"], "definite")
        self.assertFalse(got["evaluation"]["met"])

    def test_bypass_accepted_when_criteria_met(self):
        # Symmetric: a bypass is also valid when the checklist WOULD mark
        # ``met == True``. The clinician may still override to record that
        # the model's positive ``met`` is not the basis of the diagnosis.
        code = "__authority_bypass_met__"
        self._init(code)
        r = self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1", "A5", "A6", "B1", "C1", "D1"],
            "decision": "definite",
        })
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["decision"], "definite")
        # The exposed evaluation still reports the honest DSM result — the
        # API does NOT rewrite ``met`` to match the bypass.
        self.assertTrue(body["evaluation"]["met"], body)

    def test_no_auto_confirmation_from_met_true(self):
        # A PUT with checklist met but ``decision: null`` MUST NOT cause the
        # server to flip decision into "confirmed". The psychiatrist must
        # explicitly send that decision; the model is not allowed to commit
        # the diagnosis on their behalf.
        code = "__authority_no_auto_confirm__"
        self._init(code)
        r = self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1", "A5", "A6", "B1", "C1", "D1"],
            "decision": None,
        })
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["evaluation"]["met"], body)
        self.assertIsNone(body["decision"],
                          "met=True must not coerce decision to 'confirmed'")
        # GET confirms the no-decision state round-trips; no auto-commit fired.
        got = self.client.get(f"/diagnosis/{code}").json()
        self.assertIsNone(got["decision"])
        self.assertTrue(got["evaluation"]["met"])

    def test_confirmed_requires_explicit_clinician_decision(self):
        # ``decision: "confirmed"`` is the psychiatrist's明确的 affirmation
        # of a met checklist. The server records it verbatim AND reports the
        # honest DSM ``met`` — it never silently downgrades a confirmed row
        # to bypass, nor upgrades a bypass to confirmed.
        code = "__authority_confirm_explicit__"
        self._init(code)
        r = self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1", "A5", "A6", "B1", "C1", "D1"],
            "decision": "confirmed",
        })
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["decision"], "confirmed")
        self.assertTrue(body["evaluation"]["met"])
        # Audit snapshot persists the clinician's verbatim decision + the
        # checked ids that produced ``met``; it does NOT persist a derived
        # ``met`` (the snapshot is the source row, not a re-evaluation).
        snap = json.loads(_dump_for_audit(code))
        self.assertEqual(snap["decision"], "confirmed")
        self.assertEqual(snap["checked"], ["A1", "A5", "A6", "B1", "C1", "D1"])
        # The snapshot carries NO ``evaluation`` key — it cannot be mistaken
        # for a server-side auto-diagnosis. The decision is the voice here.
        self.assertNotIn("evaluation", snap,
                         "audit snapshot must not embed a derived evaluation "
                         "that could be read as an automatic diagnosis")

    def test_decision_not_rewritten_on_later_met_toggle(self):
        # A bypass captured earlier must NOT be retro-converted when a
        # later PUT happens to satisfy the checklist. Each PUT persists the
        # body's own decision verbatim; no server-side "reconcile" logic
        # is allowed to contradict the clinician's explicit last word.
        code = "__authority_no_rewrite__"
        self._init(code)
        bypass = self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1"], "decision": "definite",
        })
        self.assertEqual(bypass.json()["decision"], "definite")
        self.assertFalse(bypass.json()["evaluation"]["met"])

        # Later PUT now meets the checklist, decision still bypass.
        r = self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1", "A5", "A6", "B1", "C1", "D1"],
            "decision": "definite",
        })
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["decision"], "definite",
                         "server must not rewrite clinician's explicit decision")
        # The honest DSM projection surfaces as met=True while the recorded
        # decision stays bypass — exactly the open-and-shut clinician-authority
        # posture the invariant protects.
        self.assertTrue(body["evaluation"]["met"])

    def test_confirmed_unchanged_when_checklist_later_unmet(self):
        # Symmetric: a ``confirmed`` recorded earlier is NOT retro-rewritten
        # by a subsequent PUT whose checklist no longer meets A. The
        # decision is the clinician's record; the model's updated projection
        # is independent of it.
        code = "__authority_confirmed_no_downgrade__"
        self._init(code)
        self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1", "A5", "A6", "B1", "C1", "D1"],
            "decision": "confirmed",
        })
        r = self.client.put(f"/diagnosis/{code}", json={
            "checked": ["A1"], "decision": "confirmed",
        })
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["decision"], "confirmed")
        self.assertFalse(body["evaluation"]["met"],
                         "met may go False without demoting the recorded decision")


# ===========================================================================
# Auth rejection — ``auth.require_role`` fail-closed paths exercised
# directly (no fake auth server). The end-to-end role coverage lives in
# ``test_auth.py``; here we lock the dep-level contract.
def _v2_auth_payload(role="psychiatrist"):
    return {
        "authenticated": True,
        "authorized": True,
        "interfaceVersion": "2.0.0",
        "session": {"id": "22222222-2222-4222-8222-222222222222", "active": True, "expiresAt": "2999-01-01T00:00:00Z"},
        "user": {"id": "11111111-1111-4111-8111-111111111111", "username": "test-user", "role": role},
        "gates": {"passwordChangeRequired": False, "disclaimerRequired": False, "disclaimerVersion": "test-v1"},
        "compatibility": {"legacyUserId": 1, "legacyRole": "user"},
    }


class TestAuthRejection(unittest.TestCase):
    def setUp(self):
        # Make ``_fetch_session`` cheap and deterministic — point it at a
        # dead loopback port so ``urllib`` faults fast into the 401
        # transport-collapse branch. Each test picks the payload it wants
        # by monkeypatching instead of dialing a real socket.
        self._saved_url = diag_auth.AUTH_BASE_URL
        diag_auth.AUTH_BASE_URL = "http://127.0.0.1:1"  # unroutable

    def tearDown(self):
        diag_auth.AUTH_BASE_URL = self._saved_url

    def _dep(self, *allowed):
        return diag_auth.require_role(*allowed)

    def test_no_cookie_transport_fault_maps_to_401(self):
        # No cookie -> _fetch_session will fail to reach the dead URL
        # -> _AuthUnavailable -> 401 "Not authenticated" (fail closed,
        # no transport detail leak).
        dep = self._dep("psychiatrist")
        req = _fake_request(headers={})
        with self.assertRaises(diag_auth.HTTPException) as cm:
            dep(req)
        self.assertEqual(cm.exception.status_code, 401)

    def test_unauthenticated_payload_rejected_401(self):
        dep = self._dep("psychiatrist")
        req = _fake_request(headers={"cookie": "insight_session=x"})
        with mock.patch.object(diag_auth, "_fetch_session",
                               return_value=({"authenticated": False}, "2.0.0")):
            with self.assertRaises(diag_auth.HTTPException) as cm:
                dep(req)
        self.assertEqual(cm.exception.status_code, 401)

    def test_noncanonical_role_rejected_401(self):
        dep = self._dep("psychiatrist")
        req = _fake_request(headers={"cookie": "insight_session=x"})
        payload = _v2_auth_payload(role="nurse")
        with mock.patch.object(diag_auth, "_fetch_session",
                               return_value=(payload, "2.0.0")):
            with self.assertRaises(diag_auth.HTTPException) as cm:
                dep(req)
        self.assertEqual(cm.exception.status_code, 401)

    def test_matching_role_passes(self):
        dep = self._dep("psychiatrist", "admin")
        req = _fake_request(headers={"cookie": "insight_session=x"})
        payload = _v2_auth_payload(role="admin")
        with mock.patch.object(diag_auth, "_fetch_session",
                               return_value=(payload, "2.0.0")):
            session = dep(req)
        self.assertIn("admin", session.roles)

    def test_missing_user_id_fails_closed_401(self):
        dep = self._dep("psychiatrist")
        req = _fake_request(headers={"cookie": "insight_session=x"})
        payload = _v2_auth_payload(role="psychiatrist")
        payload["user"]["id"] = None
        with mock.patch.object(diag_auth, "_fetch_session", return_value=(payload, "2.0.0")):
            with self.assertRaises(diag_auth.HTTPException) as cm:
                dep(req)
        self.assertEqual(cm.exception.status_code, 401)


# ===========================================================================
# CSRF — sign / verify / require_csrf mechanism. End-to-end HTTP paths
# live in ``test_csrf.py``; here we lock the ``_verify`` + ``require_csrf``
# contract at the unit level.
class TestCSRF(unittest.TestCase):
    def setUp(self):
        diag_csrf.reset_secret_for_tests(b"unit-test-secret")

    def tearDown(self):
        diag_csrf.reset_secret_for_tests()

    def test_sign_and_verify_round_trip(self):
        tok = diag_csrf.mint()
        self.assertIn(".", tok)
        self.assertTrue(diag_csrf._verify(tok))

    def test_empty_or_no_dot_rejected(self):
        self.assertFalse(diag_csrf._verify(""))
        self.assertFalse(diag_csrf._verify("nodot"))
        self.assertFalse(diag_csrf._verify("trailing."))
        self.assertFalse(diag_csrf._verify(".leadingsig"))

    def test_bad_signature_rejected(self):
        raw = "0" * 32
        bad = f"{raw}.deadbeef"
        self.assertFalse(diag_csrf._verify(bad))

    def test_require_csrf_missing_both_blocks(self):
        # Bypass must be off in the env for the dep to enforce — the suite
        # sets ``DIAGNOSIS_AUTH_BYPASS=1`` at import time, but
        # ``require_csrf`` reads the env at *call* time, so pop it here.
        saved = os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
        try:
            req = _fake_request(cookies={}, headers={})
            with self.assertRaises(diag_csrf.HTTPException) as cm:
                diag_csrf.require_csrf(req)
            self.assertEqual(cm.exception.status_code, 403)
            self.assertIn("CSRF", cm.exception.detail)
        finally:
            if saved is not None:
                os.environ["DIAGNOSIS_AUTH_BYPASS"] = saved

    def test_require_csrf_header_only_blocks(self):
        saved = os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
        try:
            tok = diag_csrf.mint()
            req = _fake_request(cookies={}, headers={"X-CSRF-Token": tok})
            with self.assertRaises(diag_csrf.HTTPException) as cm:
                diag_csrf.require_csrf(req)
            self.assertEqual(cm.exception.status_code, 403)
        finally:
            if saved is not None:
                os.environ["DIAGNOSIS_AUTH_BYPASS"] = saved

    def test_require_csrf_cookie_only_blocks(self):
        saved = os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
        try:
            tok = diag_csrf.mint()
            req = _fake_request(cookies={"csrf": tok}, headers={})
            with self.assertRaises(diag_csrf.HTTPException) as cm:
                diag_csrf.require_csrf(req)
            self.assertEqual(cm.exception.status_code, 403)
        finally:
            if saved is not None:
                os.environ["DIAGNOSIS_AUTH_BYPASS"] = saved

    def test_require_csrf_mismatch_blocks(self):
        saved = os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
        try:
            cookie_tok = diag_csrf.mint()
            header_tok = diag_csrf.mint()
            req = _fake_request(
                cookies={"csrf": cookie_tok},
                headers={"X-CSRF-Token": header_tok},
            )
            with self.assertRaises(diag_csrf.HTTPException) as cm:
                diag_csrf.require_csrf(req)
            self.assertEqual(cm.exception.status_code, 403)
        finally:
            if saved is not None:
                os.environ["DIAGNOSIS_AUTH_BYPASS"] = saved

    def test_require_csrf_matching_valid_passes(self):
        saved = os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
        try:
            tok = diag_csrf.mint()
            req = _fake_request(
                cookies={"csrf": tok},
                headers={"X-CSRF-Token": tok},
            )
            # Must not raise.
            self.assertIsNone(diag_csrf.require_csrf(req))
        finally:
            if saved is not None:
                os.environ["DIAGNOSIS_AUTH_BYPASS"] = saved

    def test_bypass_env_skips_csrf(self):
        # The shim is already on for the suite; assert it short-circuits.
        self.assertIsNone(diag_csrf.require_csrf(_fake_request()))


# ===========================================================================
# Persistence — ``DiagnosisStore`` end-to-end on a temp DB. Mirrors
# ``store._store_selfcheck``; never touches the real store.
class TestPersistence(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(prefix="diagnosis_unit_test_",
                                         suffix=".db")
        os.close(fd)
        self.store = diag_store.DiagnosisStore(self.path)

    def tearDown(self):
        if self.store._conn is not None:
            try:
                self.store._conn.close()
            except Exception:
                pass
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_init_creates_then_idempotent(self):
        self.assertTrue(self.store.init("P-0042-A", patient_id="P-0042-A"))
        self.assertFalse(self.store.init("P-0042-A", patient_id="P-0042-A"))

    def test_get_returns_empty_session_after_init(self):
        self.store.init("P-0042-A", patient_id="P-0042-A")
        row = self.store.get("P-0042-A")
        self.assertIsNotNone(row)
        self.assertEqual(row["code"], "P-0042-A")
        self.assertEqual(row["patient_id"], "P-0042-A")
        self.assertEqual(row["checked"], [])
        self.assertIsNone(row["decision"])

    def test_get_unknown_is_none(self):
        self.assertIsNone(self.store.get("nope"))

    def test_put_persists_checked_decision_and_returns_row(self):
        self.store.init("P-0042-A", patient_id="P-0042-A")
        checked = ["A1", "A5", "A6", "B1", "C1", "D1"]
        out = self.store.put("P-0042-A", patient_id="P-0042-A",
                             checked=checked, decision="confirmed")
        self.assertEqual(out["checked"], checked)
        self.assertEqual(out["decision"], "confirmed")
        self.assertEqual(out["code"], "P-0042-A")

    def test_put_creates_row_when_missing(self):
        # put on an un-init code must create the row, not 500.
        out = self.store.put("P-NEW", patient_id="P-NEW",
                             checked=["A1"], decision=None)
        self.assertEqual(out["code"], "P-NEW")
        self.assertEqual(out["checked"], ["A1"])

    def test_put_preserves_checked_order_and_duplicates_at_store_layer(self):
        # The store is a dumb persistence layer — dedupe/order happens in
        # ``diagnosis_api.put_session`` (via ``dict.fromkeys``). Store must
        # round-trip whatever it is handed so the API contract test stands.
        sent = ["A1", "A1", "A5", "A5"]
        out = self.store.put("P-DUP", patient_id="P-DUP",
                             checked=sent, decision=None)
        self.assertEqual(out["checked"], sent)

    def test_bypass_decision_accepted_on_unmet(self):
        self.store.init("P-B", patient_id="P-B")
        out = self.store.put("P-B", patient_id="P-B",
                             checked=["A1"], decision="definite")
        self.assertEqual(out["decision"], "definite")

    def test_timestamps_monotonic(self):
        self.store.init("P-T", patient_id="P-T")
        row1 = self.store.get("P-T")
        out = self.store.put("P-T", patient_id="P-T",
                             checked=["A1"], decision=None)
        self.assertGreaterEqual(out["updated_at"], row1["updated_at"])
        self.assertGreaterEqual(row1["updated_at"], row1["created_at"])

    def test_audit_snapshot_records_and_round_trips(self):
        self.store.init("P-A", patient_id="P-A")
        self.store.put("P-A", patient_id="P-A",
                       checked=["A1"], decision="confirmed")
        snap = self.store.audit_snapshot("P-A")
        parsed = json.loads(snap)
        self.assertEqual(parsed["code"], "P-A")
        self.assertEqual(parsed["decision"], "confirmed")
        audits = self.store.list_audits("P-A")
        self.assertTrue(any(snap == a for a in audits))

    def test_audit_snapshot_missing_code_does_not_crash(self):
        snap = self.store.audit_snapshot("never")
        self.assertEqual(json.loads(snap)["code"], "never")

    def test_durability_across_new_store_instance(self):
        self.store.init("P-D", patient_id="P-D")
        self.store.put("P-D", patient_id="P-D",
                       checked=["A1"], decision="definite")
        s2 = diag_store.DiagnosisStore(self.path)
        row = s2.get("P-D")
        self.assertIsNotNone(row)
        self.assertEqual(row["checked"], ["A1"])
        self.assertEqual(row["decision"], "definite")
        try:
            if s2._conn is not None:
                s2._conn.close()
        except Exception:
            pass

    def test_reset_clears_rows(self):
        self.store.init("P-R", patient_id="P-R")
        self.store.reset()
        self.assertIsNone(self.store.get("P-R"))


# ===========================================================================
# Patient identity — ``resolve_patient`` + ``_build_patient`` direct.
# End-to-end happy/fault paths live in ``test_patient.py``; here we lock
# the adapter contract without a fake HTTP server.
class TestPatientIdentity(unittest.TestCase):
    def setUp(self):
        self._saved_lookup = os.environ.get("DIAGNOSIS_PATIENT_LOOKUP")

    def tearDown(self):
        if self._saved_lookup is None:
            os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)
        else:
            os.environ["DIAGNOSIS_PATIENT_LOOKUP"] = self._saved_lookup

    def test_empty_code_400(self):
        with self.assertRaises(diag_patient.HTTPException) as cm:
            resolve_patient("", None)
        self.assertEqual(cm.exception.status_code, 400)

    def test_whitespace_only_code_400(self):
        with self.assertRaises(diag_patient.HTTPException) as cm:
            resolve_patient("   ", None)
        self.assertEqual(cm.exception.status_code, 400)

    def test_lookup_disabled_short_uses_free_text(self):
        os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)
        p = resolve_patient("P-SELF", None)
        self.assertEqual(p.id, "P-SELF")
        self.assertEqual(p.patient_code, "P-SELF")
        self.assertEqual(p.display_name, "P-SELF")

    def test_build_patient_missing_id_422(self):
        with self.assertRaises(diag_patient.HTTPException) as cm:
            _build_patient({"patient_code": "x", "display_name": "y"}, "x")
        self.assertEqual(cm.exception.status_code, 422)
        self.assertIn("no canonical id", cm.exception.detail)

    def test_build_patient_falls_back_patient_code_to_free_text(self):
        p = _build_patient({"id": "pid-9"}, "P-LOOKUP")
        self.assertEqual(p.id, "pid-9")
        self.assertEqual(p.patient_code, "P-LOOKUP")
        self.assertIsNone(p.display_name)

    def test_build_patient_display_name_passes_through(self):
        self.assertEqual(
            _build_patient({"id": "1", "display_name": "Ada"}, "c").display_name,
            "Ada")
        self.assertIsNone(
            _build_patient({"id": "1", "display_name": None}, "c").display_name)
        # Non-str display_name (registry bug) collapses to None.
        self.assertIsNone(
            _build_patient({"id": "1", "display_name": 42}, "c").display_name)

    def test_lookup_enabled_unknown_code_422(self):
        os.environ["DIAGNOSIS_PATIENT_LOOKUP"] = "1"
        with mock.patch.object(diag_patient, "_fetch_patient",
                              side_effect=diag_patient._PatientNotFound()):
            with self.assertRaises(diag_patient.HTTPException) as cm:
                resolve_patient("P-X", None)
        self.assertEqual(cm.exception.status_code, 422)
        self.assertIn("Unknown patient code", cm.exception.detail)

    def test_lookup_enabled_transport_fault_422(self):
        os.environ["DIAGNOSIS_PATIENT_LOOKUP"] = "1"
        with mock.patch.object(diag_patient, "_fetch_patient",
                              side_effect=diag_patient._PatientUnavailable("down")):
            with self.assertRaises(diag_patient.HTTPException) as cm:
                resolve_patient("P-X", None)
        self.assertEqual(cm.exception.status_code, 422)
        self.assertIn("registry unavailable", cm.exception.detail)

    def test_lookup_enabled_happy_returns_canonical(self):
        os.environ["DIAGNOSIS_PATIENT_LOOKUP"] = "1"
        with mock.patch.object(diag_patient, "_fetch_patient",
                              return_value={"id": "insight-pid-1",
                                            "patient_code": "P-1",
                                            "display_name": "Ada"}):
            p = resolve_patient("P-1", "insight_session=x")
        self.assertEqual(p.id, "insight-pid-1")
        self.assertEqual(p.patient_code, "P-1")
        self.assertEqual(p.display_name, "Ada")


# ---------------------------------------------------------------------------
# Runner — ponytail style, mirrors the existing ``test_*.py`` main().
if __name__ == "__main__":
    # ``unittest.main`` exits non-zero on failure -> the smoke-check
    # shims that delegate here pick up the same fail-fast signal.
    unittest.main(verbosity=2)
