import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from treatment_plan.ddi_check import DdiMedicationChecker, Medication
from treatment_plan.edit_ledger import (
    InMemoryPlanEditStore,
    PlanEditLedger,
    PlanFinalized,
    PreconditionFailed,
)
from treatment_plan.finalization import (
    FinalizationCommand,
    FinalizationContext,
    MedicationSafetyCandidate,
    PlanFinalizer,
    SafetyRecalculationFailed,
    SourceVersion,
)
from treatment_plan.safety_policy import ProbabilisticRecommendation, SafetyFacts
from treatment_plan.sqlite_edit_store import SQLitePlanEditStore
from treatment_plan.sqlite_repository import SQLiteRepository


NOW = datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc)
PLAN_ID = "00000000-0000-4000-8000-000000000016"
ACTOR_ID = "00000000-0000-4000-8000-000000000017"
ALERT_ID = "00000000-0000-4000-8000-000000000018"


def primary_plan():
    return {
        "schemaVersion": "1.0.0",
        "planId": PLAN_ID,
        "patientId": "00000000-0000-4000-8000-000000000002",
        "encounterId": "00000000-0000-4000-8000-000000000003",
        "status": "ready-for-review",
        "content": {
            "setting": "outpatient",
            "pharmacotherapy": [{
                "medicationCode": "synthetic-a",
                "codeSystem": "synthetic",
                "dose": "10 mg",
                "route": "oral",
                "frequency": "daily",
            }],
            "nextAppointment": {"interval": "P14D", "timezone": "America/Los_Angeles"},
        },
        "safetyFindings": [],
    }


def context(*, facts=None, medication_code="synthetic-a", dose="10 mg"):
    return FinalizationContext(
        current_medications=(Medication(
            "current-a 5 mg", "current-a", "synthetic", "5 mg", "oral", "daily"
        ),),
        safety_candidates=(MedicationSafetyCandidate(
            Medication(medication_code, medication_code, "synthetic", dose, "oral", "daily"),
            ProbabilisticRecommendation(
                medication_code, .8, substances=("latex",), contraindication_codes=("condition-x",)
            ),
        ),),
        safety_facts=facts or SafetyFacts(),
        sources=(SourceVersion(
            "medical-history",
            "history-version-7",
            "1.0.0",
            "2026-07-14T19:59:00Z",
            "sha256:" + "a" * 64,
            etag='"history-7"',
        ),),
    )


def command():
    return FinalizationCommand(
        ACTOR_ID,
        "session-16",
        "I attest that I reviewed the exact final plan and its fresh safety results.",
        "00000000-0000-4000-8000-000000000019",
        "00000000-0000-4000-8000-000000000020",
        "tp17-finalize-key-0001",
    )


class RecordingPort:
    def __init__(self):
        self.requests = []

    async def check(self, request):
        self.requests.append(request)
        count = len(request["medications"])
        return {
            "schemaVersion": "1.0.0",
            "checkId": f"check-{len(self.requests)}",
            "medicationSetHash": request["medicationSetHash"],
            "knowledgeBaseId": "synthetic-kb",
            "knowledgeBaseVersion": "2026.07.14",
            "normalizedMedications": [
                {"inputIndex": index, "conceptId": f"synthetic:{index}", "display": f"Drug {index}"}
                for index in range(count)
            ],
            "unresolvedMedications": [],
            "pairsChecked": [
                {"leftInputIndex": left, "rightInputIndex": right}
                for left in range(count) for right in range(left + 1, count)
            ],
            "alerts": [],
        }


class BlockingPort(RecordingPort):
    def __init__(self):
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def check(self, request):
        self.started.set()
        await self.release.wait()
        return await super().check(request)


class TP16FinalizationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ledger = PlanEditLedger(InMemoryPlanEditStore(), clock=lambda: NOW)
        self.initial = self.ledger.register_primary_plan(primary_plan())

    def finalizer(self, port):
        ids = iter((
            "00000000-0000-4000-8000-000000000021",
            "00000000-0000-4000-8000-000000000022",
        ))
        return PlanFinalizer(
            self.ledger,
            DdiMedicationChecker(port),
            clock=lambda: NOW,
            id_factory=lambda: next(ids),
        )

    async def test_marks_preview_stale_for_identity_dose_allergy_and_contraindication_changes(self):
        edit_cases = (
            ("/content/pharmacotherapy/0/medicationCode", "synthetic-b"),
            ("/content/pharmacotherapy/0/dose", "20 mg"),
        )
        for path, after in edit_cases:
            with self.subTest(path=path):
                ledger = PlanEditLedger(InMemoryPlanEditStore(), clock=lambda: NOW)
                view = ledger.register_primary_plan(primary_plan())
                finalizer = PlanFinalizer(ledger, DdiMedicationChecker(RecordingPort()))
                await finalizer.preview(PLAN_ID, context())
                ledger.edit(
                    PLAN_ID, expected_etag=view.etag, actor_id=ACTOR_ID,
                    session_id="session-16", path=path, operation="replace", after=after,
                )
                self.assertTrue(finalizer.preview_status(PLAN_ID, context()).stale)

        finalizer = self.finalizer(RecordingPort())
        await finalizer.preview(PLAN_ID, context())
        self.assertTrue(finalizer.preview_status(
            PLAN_ID, context(facts=SafetyFacts(allergies=("latex",)))
        ).stale)
        self.assertTrue(finalizer.preview_status(
            PLAN_ID, context(facts=SafetyFacts(contraindications=("condition-x",)))
        ).stale)

    async def test_finalize_rechecks_and_persists_fresh_hash_then_freezes_edits(self):
        port = RecordingPort()
        finalizer = self.finalizer(port)
        preview = await finalizer.preview(PLAN_ID, context())
        final_plan = await finalizer.finalize(
            PLAN_ID,
            expected_etag=self.initial.etag,
            command=command(),
            context=context(),
        )

        self.assertEqual(2, len(port.requests), "finalization must not reuse the preview DDI result")
        self.assertEqual(preview.medication_set_hash, port.requests[1]["medicationSetHash"])
        record = self.ledger.get_finalization(PLAN_ID)
        self.assertEqual(port.requests[1]["medicationSetHash"], record["safetyBinding"]["medicationSetHash"])
        self.assertEqual("check-2", record["safetyBinding"]["ddiCheckId"])
        self.assertEqual("finalized", final_plan["status"])
        self.assertTrue(final_plan["contentHash"].startswith("sha256:"))
        with self.assertRaises(PlanFinalized):
            self.ledger.edit(
                PLAN_ID, expected_etag=self.initial.etag, actor_id=ACTOR_ID,
                session_id="session-16", path="/content/pharmacotherapy/0/dose",
                operation="replace", after="20 mg",
            )

    async def test_finalize_rejects_candidate_metadata_bound_to_an_earlier_dose(self):
        updated = self.ledger.edit(
            PLAN_ID, expected_etag=self.initial.etag, actor_id=ACTOR_ID,
            session_id="session-16", path="/content/pharmacotherapy/0/dose",
            operation="replace", after="20 mg",
        )
        finalizer = self.finalizer(RecordingPort())
        with self.assertRaisesRegex(SafetyRecalculationFailed, "dose-sensitive"):
            await finalizer.finalize(
                PLAN_ID, expected_etag=updated.etag, command=command(), context=context()
            )
        final_plan = await finalizer.finalize(
            PLAN_ID, expected_etag=updated.etag, command=command(), context=context(dose="20 mg")
        )
        self.assertEqual("20 mg", final_plan["content"]["pharmacotherapy"][0]["dose"])

    async def test_sqlite_adapter_persists_the_same_immutable_finalization_record(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "tp16.sqlite"
            SQLiteRepository(database).migrate()
            ledger = PlanEditLedger(SQLitePlanEditStore(database), clock=lambda: NOW)
            initial = ledger.register_primary_plan(primary_plan())
            ids = iter((
                "00000000-0000-4000-8000-000000000023",
                "00000000-0000-4000-8000-000000000024",
            ))
            finalizer = PlanFinalizer(
                ledger, DdiMedicationChecker(RecordingPort()),
                clock=lambda: NOW, id_factory=lambda: next(ids),
            )
            final_plan = await finalizer.finalize(
                PLAN_ID, expected_etag=initial.etag, command=command(), context=context()
            )
            self.assertEqual(final_plan, ledger.get_finalization(PLAN_ID)["finalPlan"])
            reopened = PlanEditLedger(SQLitePlanEditStore(database))
            self.assertEqual(final_plan, reopened.get_finalization(PLAN_ID)["finalPlan"])
            with self.assertRaises(PlanFinalized):
                reopened.edit(
                    PLAN_ID, expected_etag=initial.etag, actor_id=ACTOR_ID,
                    session_id="session-16", path="/content/pharmacotherapy/0/dose",
                    operation="replace", after="20 mg",
                )

    async def test_edit_during_final_ddi_check_prevents_signing_earlier_version(self):
        port = BlockingPort()
        finalizer = self.finalizer(port)
        attempt = asyncio.create_task(finalizer.finalize(
            PLAN_ID,
            expected_etag=self.initial.etag,
            command=command(),
            context=context(),
        ))
        await port.started.wait()
        updated = self.ledger.edit(
            PLAN_ID, expected_etag=self.initial.etag, actor_id=ACTOR_ID,
            session_id="session-16", path="/content/pharmacotherapy/0/dose",
            operation="replace", after="20 mg",
        )
        port.release.set()
        with self.assertRaises(PreconditionFailed):
            await attempt
        self.assertIsNone(self.ledger.get_finalization(PLAN_ID))
        self.assertNotEqual(self.initial.etag, updated.etag)


if __name__ == "__main__":
    unittest.main()
