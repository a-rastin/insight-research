import asyncio
import json
import unittest
from datetime import datetime, timedelta, timezone

import httpx

from treatment_plan.clinical_context import (
    ClinicalContextAssembler, ContextErrorCode, Dependency,
)


PATIENT = "00000000-0000-4000-8000-000000000002"
ENCOUNTER = "00000000-0000-4000-8000-000000000003"


def payloads():
    base = {"schemaVersion": "1.0.0", "patientId": PATIENT, "encounterId": ENCOUNTER}
    return {
        Dependency.PATIENT: {**base, "resourceId": "patient-encounter-1", "currentMedications": []},
        Dependency.DIAGNOSIS: {**base, "assessmentId": "dx-1", "diagnosis": {"code": "F20.9"}},
        Dependency.SEVERITY: {**base, "assessmentId": "sev-1", "severity": {"score": 12}},
        Dependency.MEDICAL_HISTORY: {**base, "assessmentId": "mh-1", "medicalHistory": {"allergies": []}},
        Dependency.DDI: {**base, "checkId": "ddi-1", "knowledgeVersion": "2026.1", "findings": []},
        Dependency.BN: {**base, "evaluationId": "bn-1", "modelId": "model-1", "modelVersion": "1.2", "evaluation": {"result": "synthetic"}},
    }


def dependency_for_path(path):
    return next(dep for dep in Dependency if {
        Dependency.PATIENT: "/add-new-patient/", Dependency.DIAGNOSIS: "/diagnosis/",
        Dependency.SEVERITY: "/severity/", Dependency.MEDICAL_HISTORY: "/medical-history/",
        Dependency.DDI: "/ddi-checker/", Dependency.BN: "/bn-manager/",
    }[dep] in path)


class TP08ContractTests(unittest.IsolatedAsyncioTestCase):
    def endpoints(self):
        return {dep: "https://" + dep.value + ".internal" for dep in Dependency}

    async def make(self, handler, **options):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.addAsyncCleanup(client.aclose)
        return ClinicalContextAssembler(self.endpoints(), client, **options)

    async def test_consumer_contracts_for_all_six_dependencies_and_provenance(self):
        seen = set()
        expected = payloads()

        def handler(request):
            dependency = dependency_for_path(request.url.path)
            seen.add(dependency)
            self.assertEqual(request.headers["x-schema-version"], "1.0.0")
            return httpx.Response(200, json=expected[dependency], headers={"ETag": '"source-v1"'})

        context = await (await self.make(handler)).assemble(PATIENT, ENCOUNTER)
        self.assertEqual(seen, set(Dependency))
        self.assertTrue(context.complete)
        self.assertEqual(len(context.sources), 6)
        self.assertTrue(all(source.etag == '"source-v1"' for source in context.sources))
        self.assertTrue(all(source.content_hash.startswith("sha256:") for source in context.sources))

    async def test_invalid_contract_is_visible_and_not_used(self):
        expected = payloads()
        expected[Dependency.SEVERITY]["guessedScore"] = 99

        def handler(request):
            dep = dependency_for_path(request.url.path)
            return httpx.Response(200, json=expected[dep])

        context = await (await self.make(handler)).assemble(PATIENT, ENCOUNTER)
        self.assertNotIn(Dependency.SEVERITY, context.inputs)
        self.assertIn(ContextErrorCode.INVALID_SCHEMA, [finding.code for finding in context.findings])
        self.assertFalse(context.complete)

    async def test_missing_partial_stale_and_conflicting_data_remain_visible(self):
        expected = payloads()
        expected[Dependency.DIAGNOSIS]["encounterId"] = "00000000-0000-4000-8000-000000000099"
        expected[Dependency.MEDICAL_HISTORY]["observedAt"] = (
            datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

        def handler(request):
            dep = dependency_for_path(request.url.path)
            if dep is Dependency.DDI:
                return httpx.Response(404)
            return httpx.Response(200, json=expected[dep])

        context = await (await self.make(handler, stale_after_seconds=60)).assemble(PATIENT, ENCOUNTER)
        codes = {finding.code for finding in context.findings}
        self.assertTrue({ContextErrorCode.MISSING, ContextErrorCode.STALE, ContextErrorCode.CONFLICT} <= codes)
        self.assertNotIn(Dependency.DDI, context.inputs)
        self.assertNotIn(Dependency.DIAGNOSIS, context.inputs)
        self.assertIn(Dependency.MEDICAL_HISTORY, context.inputs)

    async def test_idempotent_reads_retry_only_within_bound(self):
        attempts = {dep: 0 for dep in Dependency}
        expected = payloads()

        def handler(request):
            dep = dependency_for_path(request.url.path)
            attempts[dep] += 1
            if dep is Dependency.BN:
                return httpx.Response(503)
            return httpx.Response(200, json=expected[dep])

        context = await (await self.make(handler, max_attempts=2)).assemble(PATIENT, ENCOUNTER)
        self.assertEqual(attempts[Dependency.BN], 2)
        self.assertEqual(attempts[Dependency.PATIENT], 1)
        self.assertIn(ContextErrorCode.UNAVAILABLE, [finding.code for finding in context.findings])

    async def test_circuit_opens_after_bounded_failures(self):
        calls = 0

        def handler(request):
            nonlocal calls
            dep = dependency_for_path(request.url.path)
            if dep is Dependency.BN:
                calls += 1
                return httpx.Response(503)
            return httpx.Response(200, json=payloads()[dep])

        assembler = await self.make(handler, max_attempts=1)
        for _ in range(4):
            last = await assembler.assemble(PATIENT, ENCOUNTER)
        self.assertEqual(calls, 3)
        self.assertIn(ContextErrorCode.CIRCUIT_OPEN, [finding.code for finding in last.findings])

    async def test_independent_reads_are_parallel_and_strictly_deadlined(self):
        async def handler(request):
            dep = dependency_for_path(request.url.path)
            if dep in {Dependency.DDI, Dependency.BN}:
                await asyncio.sleep(.3)
            return httpx.Response(200, json=payloads()[dep])

        context = await (await self.make(handler, request_deadline_seconds=.12,
                                         dependency_timeout_seconds=1, max_attempts=1)).assemble(PATIENT, ENCOUNTER)
        timed_out = {finding.dependency for finding in context.findings if finding.code is ContextErrorCode.TIMEOUT}
        self.assertEqual(timed_out, {Dependency.DDI, Dependency.BN})
        self.assertEqual(len(context.inputs), 4)


if __name__ == "__main__":
    unittest.main()

