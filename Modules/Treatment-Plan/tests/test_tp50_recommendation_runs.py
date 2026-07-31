import unittest
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from treatment_plan.app import create_app
from treatment_plan.clinical_context import ClinicalContext, OutboundRequestContext
from treatment_plan.config import Settings
from treatment_plan.eligibility import Blocker, Eligibility, EligibilityDecision, EligibilityFinding
from treatment_plan.recommendation_run import (
    RecommendationRunIdempotencyConflict,
    RecommendationRunRequest,
    RecommendationRunStore,
    RecommendationRunWorkflow,
)
from treatment_plan.repository import InMemoryRepository
from treatment_plan.security import InMemoryAuthenticationAdapter, Security, Session


PATIENT = "00000000-0000-4000-8000-000000000002"
ENCOUNTER = "00000000-0000-4000-8000-000000000003"
SEVERITY = "00000000-0000-4000-8000-000000000004"
RUN = "00000000-0000-4000-8000-000000000005"
SNAPSHOT = "00000000-0000-4000-8000-000000000006"
PLAN = "00000000-0000-4000-8000-000000000007"
ACTOR = "00000000-0000-4000-8000-000000000008"
REQUEST = "00000000-0000-4000-8000-000000000009"
CORRELATION = "00000000-0000-4000-8000-000000000010"
NOW = datetime(2026, 7, 31, 1, 0, tzinfo=timezone.utc)


class Assembler:
    def __init__(self):
        self.calls = 0

    async def assemble(self, patient_id, encounter_id, severity_assessment_id, request_context):
        self.calls += 1
        return ClinicalContext(patient_id, encounter_id, {}, (), ())


class EligibilityPolicy:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.calls = 0

    def evaluate(self, context, pathway_id):
        self.calls += 1
        if self.allowed:
            return EligibilityDecision(pathway_id, Eligibility.ELIGIBLE, ())
        return EligibilityDecision(
            pathway_id,
            Eligibility.BLOCKED,
            (EligibilityFinding("required-fact-missing", Blocker.HARD, "severity", "severity is unavailable"),),
        )


class Stages:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.calls = []

    async def evaluate_bn(self, context, snapshot_id):
        self.calls.append("bn")
        if self.fail_at == "bn":
            raise RuntimeError("BN unavailable")
        return {"snapshotId": snapshot_id}

    def synthesize(self, context, bn_result, *, timezone):
        self.calls.append("synthesis")
        return {"timezone": timezone, "bn": bn_result}

    async def check_ddi(self, context, plan):
        self.calls.append("ddi")
        if self.fail_at == "ddi":
            raise RuntimeError("DDI unavailable")
        return {"coverage": "complete"}

    def persist(self, context, run_id, plan, ddi_result):
        self.calls.append("persistence")
        return PLAN


def command(patient_id=PATIENT):
    return RecommendationRunRequest(patient_id, ENCOUNTER, SEVERITY, "America/Los_Angeles")


def outbound():
    return OutboundRequestContext("opaque", REQUEST, CORRELATION)


def workflow(*, allowed=True, fail_at=None, repository=None):
    repository = repository or InMemoryRepository()
    repository.migrate()
    assembler = Assembler()
    policy = EligibilityPolicy(allowed)
    stages = Stages(fail_at)
    ids = iter((RUN, SNAPSHOT))
    value = RecommendationRunWorkflow(
        RecommendationRunStore(repository), assembler, policy, stages,
        clock=lambda: NOW, id_factory=lambda: next(ids),
    )
    return value, assembler, policy, stages


class RecommendationWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_runs_context_eligibility_bn_ddi_synthesis_and_persistence_in_order(self):
        service, assembler, policy, stages = workflow()
        result = await service.create(
            command(), actor_id=ACTOR, idempotency_key="recommendation-key-0001", outbound_context=outbound()
        )
        self.assertEqual("generated", result.status)
        self.assertEqual(PLAN, result.primary_plan_id)
        self.assertEqual(["bn", "synthesis", "ddi", "persistence"], stages.calls)
        self.assertEqual(1, assembler.calls)
        self.assertEqual(1, policy.calls)
        self.assertEqual(result, service.read(RUN, ACTOR))

    async def test_blocked_inputs_are_explicit_and_skip_model_generation(self):
        service, _, _, stages = workflow(allowed=False)
        result = await service.create(
            command(), actor_id=ACTOR, idempotency_key="recommendation-key-0002", outbound_context=outbound()
        )
        self.assertEqual("inputs-incomplete", result.status)
        self.assertEqual("required-fact-missing", result.findings[0].code)
        self.assertEqual([], stages.calls)

    async def test_exact_retry_replays_and_conflicting_reuse_is_rejected(self):
        service, assembler, _, _ = workflow()
        first = await service.create(
            command(), actor_id=ACTOR, idempotency_key="recommendation-key-0003", outbound_context=outbound()
        )
        replay = await service.create(
            command(), actor_id=ACTOR, idempotency_key="recommendation-key-0003", outbound_context=outbound()
        )
        self.assertEqual(first, replay)
        self.assertEqual(1, assembler.calls)
        with self.assertRaises(RecommendationRunIdempotencyConflict):
            await service.create(
                command("00000000-0000-4000-8000-000000000099"), actor_id=ACTOR,
                idempotency_key="recommendation-key-0003", outbound_context=outbound(),
            )

    async def test_dependency_failure_persists_terminal_failure_without_partial_plan(self):
        service, _, _, stages = workflow(fail_at="ddi")
        result = await service.create(
            command(), actor_id=ACTOR, idempotency_key="recommendation-key-0004", outbound_context=outbound()
        )
        self.assertEqual("generation-failed", result.status)
        self.assertEqual(["bn", "synthesis", "ddi"], stages.calls)
        self.assertIsNone(result.primary_plan_id)


class RecommendationRouteTests(unittest.TestCase):
    def test_authenticated_create_replay_status_and_actor_scope(self):
        repository = InMemoryRepository()
        service, assembler, _, _ = workflow(repository=repository)
        session = Session(
            ACTOR, frozenset({"psychiatrist"}), NOW + timedelta(hours=1), "csrf-secret",
            session_id="00000000-0000-4000-8000-000000000011",
        )
        other = Session(
            "00000000-0000-4000-8000-000000000012", frozenset({"psychiatrist"}),
            NOW + timedelta(hours=1), "other-csrf", session_id="00000000-0000-4000-8000-000000000013",
        )
        security = Security(InMemoryAuthenticationAdapter({
            "session=opaque": session, "session=other": other,
        }), now=lambda: NOW)
        app = create_app(
            Settings(environment="test"), repository, security,
            recommendation_workflow=service,
        )
        headers = {
            "Cookie": "session=opaque",
            "X-CSRF-Token": "csrf-secret",
            "Idempotency-Key": "recommendation-key-0005",
            "X-Request-ID": REQUEST,
            "X-Correlation-ID": CORRELATION,
        }
        body = command().canonical()
        with TestClient(app) as client:
            created = client.post("/api/treatment-plan/v1/recommendation-runs", headers=headers, json=body)
            replay = client.post("/api/treatment-plan/v1/recommendation-runs", headers=headers, json=body)
            status = client.get(
                f"/api/treatment-plan/v1/recommendation-runs/{RUN}", headers={"Cookie": "session=opaque"}
            )
            hidden = client.get(
                f"/api/treatment-plan/v1/recommendation-runs/{RUN}", headers={"Cookie": "session=other"}
            )
        self.assertEqual(202, created.status_code)
        self.assertEqual(created.json(), replay.json())
        self.assertEqual(created.json(), status.json())
        self.assertEqual("1.1.0", created.headers["X-Schema-Version"])
        self.assertEqual(404, hidden.status_code)
        schema = json.loads((Path(__file__).parents[1] / "contracts/schemas/1.1.0/runtime-api.schema.json").read_text())
        Draft202012Validator(
            schema["$defs"]["RecommendationRun"],
            resolver=Draft202012Validator(schema).resolver,
            format_checker=FormatChecker(),
        ).validate(created.json())
        self.assertEqual(1, assembler.calls)


if __name__ == "__main__":
    unittest.main()
