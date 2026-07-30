import asyncio
import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from treatment_plan.app import create_app
from treatment_plan.config import Settings
from treatment_plan.ddi_check import DdiMedicationChecker
from treatment_plan.edit_ledger import InMemoryPlanEditStore, PlanEditLedger
from treatment_plan.finalization import (
    FinalizationCommand,
    FinalizationContext,
    FinalizationError,
    IdempotencyConflict,
    PlanFinalizer,
    SourceVersion,
)
from treatment_plan.repository import InMemoryRepository
from treatment_plan.security import InMemoryAuthenticationAdapter, Security, Session
from treatment_plan.sqlite_edit_store import SQLitePlanEditStore
from treatment_plan.sqlite_repository import SQLiteRepository
from tests.test_tp16_finalization import (
    ACTOR_ID,
    ALERT_ID,
    NOW,
    PLAN_ID,
    RecordingPort,
    command,
    context,
    primary_plan,
)


class ContextProvider:
    def __init__(self, value: FinalizationContext):
        self.value = value
        self.calls = []

    async def load(self, plan_id, patient_id, encounter_id):
        self.calls.append((plan_id, patient_id, encounter_id))
        return self.value


class ConcurrentPort(RecordingPort):
    def __init__(self):
        super().__init__()
        self.arrived = 0
        self.both_ready = asyncio.Event()
        self.release = asyncio.Event()

    async def check(self, request):
        self.arrived += 1
        if self.arrived == 2:
            self.both_ready.set()
        await self.release.wait()
        return await super().check(request)

class HighAlertPort(RecordingPort):
    async def check(self, request):
        response = await super().check(request)
        response["alerts"] = [{
            "alertId": ALERT_ID,
            "medicationInputIndexes": [0, 1],
            "severity": "high",
            "mechanism": "Synthetic mechanism",
            "evidence": [{"sourceId": "synthetic-evidence", "summary": "Synthetic evidence"}],
            "recommendedAction": "Review the combination.",
        }]
        return response


def content_hash(value):
    payload = dict(value)
    actual = payload.pop("contentHash")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return actual, "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class TP17FinalizationVersioningTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ledger = PlanEditLedger(InMemoryPlanEditStore(), clock=lambda: NOW)
        self.initial = self.ledger.register_primary_plan(primary_plan())
        self.port = RecordingPort()
        ids = iter((
            "00000000-0000-4000-8000-000000000031",
            "00000000-0000-4000-8000-000000000032",
        ))
        self.finalizer = PlanFinalizer(
            self.ledger,
            DdiMedicationChecker(self.port),
            clock=lambda: NOW,
            id_factory=lambda: next(ids),
        )

    async def test_retry_is_idempotent_and_changed_payload_conflicts(self):
        first = await self.finalizer.finalize(
            PLAN_ID, expected_etag=self.initial.etag, command=command(), context=context()
        )
        retry = await self.finalizer.finalize(
            PLAN_ID, expected_etag=self.initial.etag, command=command(), context=context()
        )
        self.assertEqual(first, retry)
        self.assertEqual(1, len(self.port.requests))

        changed = FinalizationCommand(
            ACTOR_ID,
            "session-16",
            "A different attestation cannot reuse the same key.",
            "00000000-0000-4000-8000-000000000019",
            "00000000-0000-4000-8000-000000000020",
            "tp17-finalize-key-0001",
        )
        with self.assertRaises(IdempotencyConflict):
            await self.finalizer.finalize(
                PLAN_ID, expected_etag=self.initial.etag, command=changed, context=context()
            )

    async def test_concurrent_identical_retries_converge_on_one_immutable_version(self):
        ledger = PlanEditLedger(InMemoryPlanEditStore(), clock=lambda: NOW)
        initial = ledger.register_primary_plan(primary_plan())
        port = ConcurrentPort()
        finalizer = PlanFinalizer(
            ledger,
            DdiMedicationChecker(port),
            clock=lambda: NOW,
            id_factory=iter((
                "00000000-0000-4000-8000-000000000071",
                "00000000-0000-4000-8000-000000000072",
                "00000000-0000-4000-8000-000000000073",
                "00000000-0000-4000-8000-000000000074",
            )).__next__,
        )
        first = asyncio.create_task(finalizer.finalize(
            PLAN_ID, expected_etag=initial.etag, command=command(), context=context()
        ))
        second = asyncio.create_task(finalizer.finalize(
            PLAN_ID, expected_etag=initial.etag, command=command(), context=context()
        ))
        await port.both_ready.wait()
        port.release.set()
        results = await asyncio.gather(first, second)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], ledger.get_finalization(PLAN_ID)["finalPlan"])
    async def test_audit_proves_author_exact_source_version_and_content_hash(self):
        final_plan = await self.finalizer.finalize(
            PLAN_ID, expected_etag=self.initial.etag, command=command(), context=context()
        )
        record = self.ledger.get_finalization(PLAN_ID)
        self.assertEqual(ACTOR_ID, final_plan["finalizedBy"])
        self.assertEqual(ACTOR_ID, final_plan["provenance"]["actorId"])
        self.assertEqual('"history-7"', final_plan["provenance"]["sources"][0]["etag"])
        self.assertEqual("sha256:" + "a" * 64, final_plan["provenance"]["sources"][0]["contentHash"])
        self.assertEqual("current", record["sourceVersions"][0]["status"])
        self.assertEqual(content_hash(final_plan)[0], content_hash(final_plan)[1])

    async def test_noncurrent_source_and_changed_signing_session_fail_closed(self):
        stale = context()
        stale = FinalizationContext(
            stale.current_medications,
            stale.safety_candidates,
            stale.safety_facts,
            (SourceVersion(
                "medical-history", "history-version-7", "1.0.0",
                "2026-07-14T19:59:00Z", "sha256:" + "a" * 64, status="stale",
            ),),
        )
        with self.assertRaisesRegex(FinalizationError, "not current"):
            await self.finalizer.finalize(
                PLAN_ID, expected_etag=self.initial.etag, command=command(), context=stale
            )
        self.assertEqual([], self.port.requests)

        changed_session = Session(
            ACTOR_ID,
            frozenset({"psychiatrist"}),
            NOW + timedelta(hours=1),
            "csrf",
            session_id="different-session",
        )
        with self.assertRaisesRegex(FinalizationError, "session changed"):
            await self.finalizer.finalize(
                PLAN_ID,
                expected_etag=self.initial.etag,
                command=command(),
                context=context(),
                reauthorize=lambda: changed_session,
            )
        self.assertIsNone(self.ledger.get_finalization(PLAN_ID))

    async def test_high_severity_override_requires_exact_attributable_reason(self):
        async def attempt(rationale, edit_reason):
            plan = primary_plan()
            plan["safetyFindings"] = [{
                "findingId": ALERT_ID,
                "category": "interaction",
                "severity": "high",
                "status": "open",
                "summary": "Synthetic severe interaction",
            }]
            ledger = PlanEditLedger(InMemoryPlanEditStore(), clock=lambda: NOW)
            view = ledger.register_primary_plan(plan)
            view = ledger.edit(
                PLAN_ID, expected_etag=view.etag, actor_id=ACTOR_ID, session_id="session-16",
                path="/safetyFindings/0/overrideRationale", operation="add", after=rationale,
            )
            view = ledger.edit(
                PLAN_ID, expected_etag=view.etag, actor_id=ACTOR_ID, session_id="session-16",
                path="/safetyFindings/0/overrideActorId", operation="add", after=ACTOR_ID,
            )
            view = ledger.edit(
                PLAN_ID, expected_etag=view.etag, actor_id=ACTOR_ID, session_id="session-16",
                path="/safetyFindings/0/status", operation="replace", after="overridden",
                reason=edit_reason,
            )
            finalizer = PlanFinalizer(
                ledger, DdiMedicationChecker(HighAlertPort()), clock=lambda: NOW,
                id_factory=iter((
                    "00000000-0000-4000-8000-000000000061",
                    "00000000-0000-4000-8000-000000000062",
                )).__next__,
            )
            return await finalizer.finalize(
                PLAN_ID, expected_etag=view.etag, command=command(), context=context()
            )

        with self.assertRaisesRegex(FinalizationError, "attributable override"):
            await attempt("One rationale", "A different ledger reason")
        final_plan = await attempt("Exact reviewed rationale", "Exact reviewed rationale")
        self.assertEqual("overridden", final_plan["safetyFindings"][0]["status"])
        self.assertEqual(ACTOR_ID, final_plan["safetyFindings"][0]["overrideActorId"])
    async def test_authenticated_route_uses_server_context_and_exposes_audit(self):
        ledger = PlanEditLedger(InMemoryPlanEditStore(), clock=lambda: NOW)
        initial = ledger.register_primary_plan(primary_plan())
        provider = ContextProvider(context())
        finalizer = PlanFinalizer(
            ledger,
            DdiMedicationChecker(RecordingPort()),
            clock=lambda: NOW,
            id_factory=iter((
                "00000000-0000-4000-8000-000000000041",
                "00000000-0000-4000-8000-000000000042",
            )).__next__,
            context_provider=provider,
        )
        session = Session(
            ACTOR_ID,
            frozenset({"psychiatrist"}),
            NOW + timedelta(hours=1),
            "csrf-secret",
            session_id="session-16",
        )
        security = Security(InMemoryAuthenticationAdapter({"sid=trusted": session}), now=lambda: NOW)
        app = create_app(
            Settings(environment="test"),
            InMemoryRepository(),
            security,
            ledger,
            finalizer,
        )
        headers = {
            "Cookie": "sid=trusted",
            "X-CSRF-Token": "csrf-secret",
            "If-Match": initial.etag,
            "Idempotency-Key": "tp17-route-key-000001",
            "X-Request-ID": "00000000-0000-4000-8000-000000000043",
            "X-Correlation-ID": "00000000-0000-4000-8000-000000000044",
        }
        with TestClient(app) as client:
            response = client.post(
                f"/api/treatment-plan/v1/plans/{PLAN_ID}/finalize",
                headers=headers,
                json={"attestation": "I reviewed and attest to this exact plan."},
            )
            self.assertEqual(201, response.status_code, response.text)
            self.assertEqual(ACTOR_ID, response.json()["finalizedBy"])
            self.assertEqual(1, len(provider.calls))

            retry = client.post(
                f"/api/treatment-plan/v1/plans/{PLAN_ID}/finalize",
                headers=headers,
                json={"attestation": "I reviewed and attest to this exact plan."},
            )
            self.assertEqual(response.json(), retry.json())
            self.assertEqual(1, len(provider.calls))

            audit = client.get(
                f"/api/treatment-plan/v1/plans/{PLAN_ID}/provenance",
                headers={"Cookie": "sid=trusted"},
            )
            self.assertEqual(200, audit.status_code)
            self.assertEqual(ACTOR_ID, audit.json()[0]["actorId"])
            self.assertEqual("history-version-7", audit.json()[0]["sources"][0]["resourceId"])

            rejected = client.post(
                f"/api/treatment-plan/v1/plans/{PLAN_ID}/finalize",
                headers=headers,
                json={"attestation": "I reviewed and attest to this exact plan.", "sources": []},
            )
            self.assertEqual(422, rejected.status_code)

    async def test_sqlite_finalized_rows_reject_update_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "tp17.sqlite"
            SQLiteRepository(database).migrate()
            ledger = PlanEditLedger(SQLitePlanEditStore(database), clock=lambda: NOW)
            initial = ledger.register_primary_plan(primary_plan())
            finalizer = PlanFinalizer(
                ledger,
                DdiMedicationChecker(RecordingPort()),
                clock=lambda: NOW,
                id_factory=iter((
                    "00000000-0000-4000-8000-000000000051",
                    "00000000-0000-4000-8000-000000000052",
                )).__next__,
            )
            await finalizer.finalize(
                PLAN_ID, expected_etag=initial.etag, command=command(), context=context()
            )
            connection = sqlite3.connect(database)
            try:
                with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                    connection.execute(
                        "UPDATE finalized_plans SET finalization_record_json = '{}' WHERE plan_id = ?",
                        (PLAN_ID,),
                    )
                connection.rollback()
                with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                    connection.execute("DELETE FROM finalized_plans WHERE plan_id = ?", (PLAN_ID,))
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()

