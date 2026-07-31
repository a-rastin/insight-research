import asyncio
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

import httpx

from treatment_plan.clinical_context import (
    ClinicalContextAssembler,
    ContextErrorCode,
    Dependency,
    OutboundRequestContext,
    ServiceAuthConfig,
)


PATIENT = "00000000-0000-4000-8000-000000000002"
ENCOUNTER = "00000000-0000-4000-8000-000000000003"
SEVERITY = "00000000-0000-4000-8000-000000000004"
DIAGNOSIS = "00000000-0000-4000-8000-000000000005"
HISTORY = "00000000-0000-4000-8000-000000000006"
INTAKE = "00000000-0000-4000-8000-000000000007"
RISK = "00000000-0000-4000-8000-000000000008"
ACTOR = "00000000-0000-4000-8000-000000000009"
REQUEST = "00000000-0000-4000-8000-000000000010"
CORRELATION = "00000000-0000-4000-8000-000000000011"
NOW = datetime(2026, 7, 31, 0, 0, tzinfo=timezone.utc)
STAMP = "2026-07-31T00:00:00Z"


def payloads():
    item_scores = {**{f"P{index}": 1 for index in range(1, 8)},
                   **{f"N{index}": 1 for index in range(1, 8)},
                   **{f"G{index}": 1 for index in range(1, 17)}}
    return {
        Dependency.PATIENT: {
            "intakeSnapshotId": INTAKE,
            "patientId": PATIENT,
            "encounterId": ENCOUNTER,
            "schemaVersion": "2.0.0",
            "resourceVersion": 3,
            "presentingComplaint": "Structured complaint",
            "provisionalDiagnosis": "Clinician-entered provisional diagnosis",
            "treatmentHistory": [],
            "allergies": [],
            "currentMedications": [],
            "riskFlags": {"suicidality": "suicidality_none", "substanceUse": False},
            "provenance": {"sourceModule": "add-new-patient", "createdByUserId": "actor",
                           "createdAt": STAMP, "updatedAt": STAMP},
        },
        Dependency.DIAGNOSIS: {
            "assessmentId": DIAGNOSIS,
            "patientId": PATIENT,
            "encounterId": ENCOUNTER,
            "checkedCriteria": ["A1", "A2", "A6", "B1", "C1", "D1"],
            "evaluation": {"met": True, "aCount": 2, "coreCount": 2, "failures": [],
                           "reason": "Criteria met for decision support", "checkedCriteria": ["A1", "A2", "A6", "B1", "C1", "D1"],
                           "ruleVersion": "diagnosis-rules-1.0.0"},
            "clinicianDecision": {"type": "confirmed", "actorUserId": "actor", "recordedAt": STAMP},
            "ruleVersion": "diagnosis-rules-1.0.0",
            "schemaVersion": "2.0.0",
            "status": "decided",
            "resourceVersion": 4,
            "createdAt": STAMP,
            "updatedAt": STAMP,
            "provenance": {"sourceModule": "diagnosis", "createdByUserId": "actor", "lastUpdatedByUserId": "actor"},
        },
        Dependency.SEVERITY: {
            "interfaceVersion": "2.0.0",
            "schemaVersion": "2.0.0",
            "assessmentId": SEVERITY,
            "patientId": PATIENT,
            "encounterId": ENCOUNTER,
            "assessmentType": "PANSS",
            "status": "completed",
            "itemScores": item_scores,
            "scores": {"positive": 7, "negative": 7, "general": 16, "total": 30},
            "evaluation": {"state": "completed", "missingItemCodes": [],
                           "scores": {"positive": 7, "negative": 7, "general": 16, "total": 30},
                           "scaleVersion": "PANSS-30-1.0.0", "ruleVersion": "PANSS-SUM-2.0.0"},
            "resourceVersion": 5,
            "provenance": {"sourceModule": "severity", "createdAt": STAMP, "updatedAt": STAMP,
                           "createdRequestId": REQUEST, "updatedRequestId": REQUEST,
                           "scaleVersion": "PANSS-30-1.0.0", "ruleVersion": "PANSS-SUM-2.0.0"},
        },
        Dependency.MEDICAL_HISTORY: {
            "interfaceVersion": "2.0.0",
            "schemaVersion": "2.0.0",
            "assessmentId": HISTORY,
            "patientId": PATIENT,
            "encounterId": ENCOUNTER,
            "status": "completed",
            "pastMedicalHistory": [],
            "medications": [],
            "substantialSuicideRisk": "unknown",
            "priorAntipsychoticTherapy": "no",
            "priorAntipsychoticTherapySuccessful": "not-assessed",
            "antipsychotic": None,
            "clozapineContraindication": "no",
            "clozapineContraindications": [],
            "recurrentNonAdherenceDeterioration": "no",
            "actor": {"actorId": ACTOR, "role": "psychiatrist"},
            "createdAt": STAMP,
            "updatedAt": STAMP,
            "resourceVersion": 6,
            "provenance": {"sourceModule": "medical-history", "optionSetVersion": "2.0.0",
                           "createdRequestId": REQUEST, "updatedRequestId": REQUEST},
        },
        Dependency.SUICIDE_RISK: {
            "interfaceVersion": "1.0.0",
            "schemaVersion": "1.0.0",
            "snapshotType": "suicide-risk-encounter-snapshot",
            "patientId": PATIENT,
            "encounterId": ENCOUNTER,
            "source": {"owner": "suicide-risk", "assessmentId": RISK, "resourceVersion": 2,
                       "etag": f'"suicide-risk-assessment-{RISK}-v2"', "contentSha256": "a" * 64},
            "assessment": {
                "interfaceVersion": "1.0.0", "schemaVersion": "1.0.0", "assessmentId": RISK,
                "patientId": PATIENT, "encounterId": ENCOUNTER,
                "assessmentType": "psychiatrist-suicide-risk-assertion",
                "instrument": {"name": "C-SSRS", "completionClaimed": False, "sourceLicensingStatus": "unavailable",
                               "questionsDefined": False, "scoringDefined": False},
                "riskState": "unknown", "riskScore": None,
                "safetyDisposition": {"outcome": "blocked", "code": "TP_SUICIDE_RISK_UNAVAILABLE",
                                      "routinePlanningAllowed": False, "overrideAllowed": False,
                                      "persistentUntilResolved": True, "guidance": "Resolve before routine planning."},
                "actor": {"actorId": ACTOR, "role": "psychiatrist"},
                "createdAt": STAMP, "updatedAt": STAMP, "resourceVersion": 2,
                "provenance": {"sourceModule": "suicide-risk",
                               "policyVersion": "insight.treatment-plan-safety-policy/1.0.0",
                               "governanceVersion": "insight.clinical-ownership/1.0.0",
                               "createdRequestId": REQUEST, "updatedRequestId": REQUEST},
            },
        },
    }


VERSIONS = {Dependency.PATIENT: "2.0.0", Dependency.DIAGNOSIS: "2.0.0", Dependency.SEVERITY: "2.0.0",
            Dependency.MEDICAL_HISTORY: "2.0.0", Dependency.SUICIDE_RISK: "1.0.0"}


def dependency_for_request(request):
    return Dependency(request.url.host.split(".")[0])


class TP08ContractTests(unittest.IsolatedAsyncioTestCase):
    def endpoints(self):
        return {dependency: f"https://{dependency.value}.internal" for dependency in Dependency}

    def auth(self):
        return ServiceAuthConfig("treatment-plan", "test-key", {dependency: b"s" * 32 for dependency in Dependency})

    def request_context(self):
        return OutboundRequestContext("opaque-session", REQUEST, CORRELATION)

    async def make(self, handler, **options):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.addAsyncCleanup(client.aclose)
        return ClinicalContextAssembler(self.endpoints(), client, self.auth(), wall_clock=lambda: NOW, **options)

    async def assemble(self, assembler):
        return await assembler.assemble(PATIENT, ENCOUNTER, SEVERITY, self.request_context())

    async def test_real_provider_routes_context_and_provenance(self):
        seen = {}
        expected = payloads()

        def handler(request):
            dependency = dependency_for_request(request)
            seen[dependency] = request
            etag = expected[dependency]["source"]["etag"] if dependency is Dependency.SUICIDE_RISK else f'"{dependency.value}-v1"'
            return httpx.Response(200, json=expected[dependency],
                                  headers={"ETag": etag, "X-Schema-Version": VERSIONS[dependency]})

        context = await self.assemble(await self.make(handler))
        self.assertTrue(context.complete)
        self.assertEqual(seen[Dependency.PATIENT].url.path, f"/api/add-new-patient/v2/encounters/{ENCOUNTER}/intake-snapshot")
        self.assertEqual(seen[Dependency.DIAGNOSIS].url.path, f"/api/diagnosis/v2/encounters/{ENCOUNTER}/assessment-snapshot")
        self.assertEqual(seen[Dependency.SEVERITY].url.path, f"/api/severity/v2/assessments/{SEVERITY}")
        self.assertEqual(seen[Dependency.MEDICAL_HISTORY].url.path, f"/api/medical-history/v2/encounters/{ENCOUNTER}/assessments/latest")
        self.assertEqual(seen[Dependency.SUICIDE_RISK].url.path, f"/api/suicide-risk/v1/encounters/{ENCOUNTER}/snapshot")
        self.assertEqual({source.dependency for source in context.sources}, set(Dependency))
        self.assertTrue(all(source.retrieved_at == STAMP for source in context.sources))
        self.assertTrue(all(source.content_hash.startswith("sha256:") for source in context.sources))
        risk_source = next(source for source in context.sources if source.dependency is Dependency.SUICIDE_RISK)
        self.assertEqual(risk_source.provider_content_hash, "sha256:" + "a" * 64)
        self.assertEqual(risk_source.source_versions["policyVersion"], "insight.treatment-plan-safety-policy/1.0.0")

    async def test_forwards_only_configured_session_trace_and_service_context(self):
        requests = []

        def handler(request):
            requests.append(request)
            dependency = dependency_for_request(request)
            etag = payloads()[dependency]["source"]["etag"] if dependency is Dependency.SUICIDE_RISK else '"source-v1"'
            return httpx.Response(200, json=payloads()[dependency],
                                  headers={"ETag": etag, "X-Schema-Version": VERSIONS[dependency]})

        await self.assemble(await self.make(handler))
        self.assertEqual(len(requests), 5)
        for request in requests:
            self.assertEqual(request.headers["cookie"], "insight_session=opaque-session")
            self.assertEqual(request.headers["x-correlation-id"], CORRELATION)
            self.assertEqual(request.headers["x-causation-id"], REQUEST)
            self.assertNotEqual(request.headers["x-request-id"], REQUEST)
            self.assertEqual(request.headers["x-insight-service-id"], "treatment-plan")
            self.assertEqual(request.headers["x-insight-content-sha256"], hashlib.sha256(b"").hexdigest())
            self.assertNotIn("authorization", request.headers)
            self.assertNotIn("x-csrf-token", request.headers)
            self.assertNotIn("x-user-id", request.headers)

    async def test_invalid_schema_header_or_etag_is_visible_and_not_used(self):
        def handler(request):
            dependency = dependency_for_request(request)
            headers = {"ETag": 'W/"weak"', "X-Schema-Version": "1.0.0"} if dependency is Dependency.SEVERITY else {
                "ETag": payloads()[dependency]["source"]["etag"] if dependency is Dependency.SUICIDE_RISK else '"source-v1"',
                "X-Schema-Version": VERSIONS[dependency]}
            return httpx.Response(200, json=payloads()[dependency], headers=headers)

        context = await self.assemble(await self.make(handler))
        self.assertNotIn(Dependency.SEVERITY, context.inputs)
        self.assertIn(ContextErrorCode.INVALID_SCHEMA, [finding.code for finding in context.findings])

    async def test_missing_stale_and_conflicting_data_remain_visible(self):
        expected = payloads()
        expected[Dependency.DIAGNOSIS]["patientId"] = "00000000-0000-4000-8000-000000000099"
        expected[Dependency.MEDICAL_HISTORY]["updatedAt"] = "2026-07-30T22:00:00Z"

        def handler(request):
            dependency = dependency_for_request(request)
            if dependency is Dependency.SUICIDE_RISK:
                return httpx.Response(404)
            return httpx.Response(200, json=expected[dependency],
                                  headers={"ETag": '"source-v1"', "X-Schema-Version": VERSIONS[dependency]})

        context = await self.assemble(await self.make(handler, stale_after_seconds=60))
        codes = {finding.code for finding in context.findings}
        self.assertTrue({ContextErrorCode.MISSING, ContextErrorCode.STALE, ContextErrorCode.CONFLICT} <= codes)
        self.assertNotIn(Dependency.SUICIDE_RISK, context.inputs)
        self.assertNotIn(Dependency.DIAGNOSIS, context.inputs)
        self.assertIn(Dependency.MEDICAL_HISTORY, context.inputs)

    async def test_retries_and_circuit_are_bounded(self):
        attempts = {dependency: 0 for dependency in Dependency}

        def handler(request):
            dependency = dependency_for_request(request)
            attempts[dependency] += 1
            if dependency is Dependency.SEVERITY:
                return httpx.Response(503)
            etag = payloads()[dependency]["source"]["etag"] if dependency is Dependency.SUICIDE_RISK else '"source-v1"'
            return httpx.Response(200, json=payloads()[dependency],
                                  headers={"ETag": etag, "X-Schema-Version": VERSIONS[dependency]})

        assembler = await self.make(handler, max_attempts=1)
        for _ in range(4):
            context = await self.assemble(assembler)
        self.assertEqual(attempts[Dependency.SEVERITY], 3)
        self.assertIn(ContextErrorCode.CIRCUIT_OPEN, [finding.code for finding in context.findings])

    async def test_independent_reads_are_parallel_and_strictly_deadlined(self):
        async def handler(request):
            dependency = dependency_for_request(request)
            if dependency in {Dependency.SEVERITY, Dependency.SUICIDE_RISK}:
                await asyncio.sleep(.3)
            etag = payloads()[dependency]["source"]["etag"] if dependency is Dependency.SUICIDE_RISK else '"source-v1"'
            return httpx.Response(200, json=payloads()[dependency],
                                  headers={"ETag": etag, "X-Schema-Version": VERSIONS[dependency]})

        context = await self.assemble(await self.make(handler, request_deadline_seconds=.12,
                                                       dependency_timeout_seconds=1, max_attempts=1))
        timed_out = {finding.dependency for finding in context.findings if finding.code is ContextErrorCode.TIMEOUT}
        self.assertEqual(timed_out, {Dependency.SEVERITY, Dependency.SUICIDE_RISK})
        self.assertEqual(len(context.inputs), 3)

    async def test_rejects_noncanonical_identifiers_before_network_access(self):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(500)

        assembler = await self.make(handler)
        with self.assertRaises(ValueError):
            await assembler.assemble(PATIENT.replace("-", ""), ENCOUNTER, SEVERITY, self.request_context())
        self.assertEqual(calls, 0)


if __name__ == "__main__":
    unittest.main()
