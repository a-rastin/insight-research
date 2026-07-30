import asyncio
import hashlib
import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from treatment_plan.edit_ledger import (
    InMemoryPlanEditStore,
    PlanEditLedger,
    PlanNotFound,
    PlanSuperseded,
)
from treatment_plan.sqlite_edit_store import SQLitePlanEditStore
from treatment_plan.sqlite_repository import SQLiteRepository
from treatment_plan.supersession import (
    PlanSuperseder,
    RevalidatedPrimaryPlan,
    SupersessionError,
)


NOW = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)
PRIOR_PRIMARY_ID = "00000000-0000-4000-8000-000000000061"
PRIOR_FINAL_ID = "00000000-0000-4000-8000-000000000062"
PATIENT_ID = "00000000-0000-4000-8000-000000000002"
PRIOR_ENCOUNTER_ID = "00000000-0000-4000-8000-000000000003"
ENCOUNTER_ID = "00000000-0000-4000-8000-000000000063"
SUCCESSOR_ID = "00000000-0000-4000-8000-000000000064"
SNAPSHOT_ID = "00000000-0000-4000-8000-000000000065"


def hash_json(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def prior_primary_plan():
    return {
        "schemaVersion": "1.0.0",
        "planId": PRIOR_PRIMARY_ID,
        "patientId": PATIENT_ID,
        "encounterId": PRIOR_ENCOUNTER_ID,
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
            "nextAppointment": {
                "interval": "P14D",
                "timezone": "America/Los_Angeles",
            },
        },
        "safetyFindings": [],
    }


def final_plan():
    plan = {
        "schemaVersion": "1.0.0",
        "planId": PRIOR_FINAL_ID,
        "primaryPlanId": PRIOR_PRIMARY_ID,
        "patientId": PATIENT_ID,
        "encounterId": PRIOR_ENCOUNTER_ID,
        "version": 1,
        "status": "finalized",
        "finalizedAt": "2026-07-01T18:00:00Z",
        "finalizedBy": "00000000-0000-4000-8000-000000000066",
        "attestation": "Synthetic reviewed plan.",
        "content": deepcopy(prior_primary_plan()["content"]),
        "safetyFindings": [],
        "provenance": {"sources": []},
    }
    plan["contentHash"] = hash_json(plan)
    return plan


def follow_up_delta():
    return {
        "schemaVersion": "1.0.0",
        "deltaId": "00000000-0000-4000-8000-000000000067",
        "patientId": PATIENT_ID,
        "priorEncounterId": PRIOR_ENCOUNTER_ID,
        "encounterId": ENCOUNTER_ID,
        "priorFinalPlanId": PRIOR_FINAL_ID,
        "recordedAt": "2026-07-15T17:55:00Z",
        "changes": [{
            "domain": "severity",
            "summary": "Synthetic severity changed.",
            "sourceResourceId": "severity-version-2",
        }],
    }


def snapshot():
    return {
        "schemaVersion": "1.0.0",
        "snapshotId": SNAPSHOT_ID,
        "patientId": PATIENT_ID,
        "encounterId": ENCOUNTER_ID,
        "capturedAt": "2026-07-15T17:59:00Z",
        "diagnosis": {"code": "F20.9"},
        "severity": {"score": 18},
        "medicalHistory": {"allergies": []},
        "currentMedications": [],
        "sources": [{
            "module": "severity",
            "resourceId": "severity-version-2",
            "schemaVersion": "1.0.0",
            "retrievedAt": "2026-07-15T17:59:00Z",
            "contentHash": "sha256:" + "b" * 64,
        }],
    }


def successor_plan():
    content = deepcopy(prior_primary_plan()["content"])
    content["pharmacotherapy"][0]["dose"] = "15 mg"
    return {
        "schemaVersion": "1.0.0",
        "planId": SUCCESSOR_ID,
        "runId": "00000000-0000-4000-8000-000000000068",
        "patientId": PATIENT_ID,
        "encounterId": ENCOUNTER_ID,
        "status": "generated",
        "createdAt": "2026-07-15T18:00:00Z",
        "content": content,
        "rationale": ["replaced by the supersession seam"],
        "safetyFindings": [],
    }


class SnapshotProvider:
    def __init__(self, value=None):
        self.value = value if value is not None else snapshot()
        self.calls = []

    async def gather(self, patient_id, encounter_id):
        self.calls.append((patient_id, encounter_id))
        return deepcopy(self.value)


class ConcurrentSnapshotProvider(SnapshotProvider):
    def __init__(self):
        super().__init__()
        self.both_gathered = asyncio.Event()
        self.release = asyncio.Event()

    async def gather(self, patient_id, encounter_id):
        value = await super().gather(patient_id, encounter_id)
        if len(self.calls) == 2:
            self.both_gathered.set()
        await self.release.wait()
        return value


class Generator:
    def __init__(self, reasons=None):
        self.reasons = reasons or {
            "setting": "Fresh severity evidence still supports outpatient care.",
            "pharmacotherapy": "Fresh severity evidence supports the revised dose.",
            "nextAppointment": "Fresh evidence still supports the fourteen-day interval.",
        }
        self.calls = []

    async def generate(self, source_snapshot, prior):
        self.calls.append((source_snapshot, prior))
        return RevalidatedPrimaryPlan(successor_plan(), self.reasons)


def finalized_ledger(store):
    ledger = PlanEditLedger(store, clock=lambda: NOW)
    view = ledger.register_primary_plan(prior_primary_plan())
    ledger.commit_finalization(
        PRIOR_PRIMARY_ID,
        expected_etag=view.etag,
        record={"schemaVersion": "1.0.0", "finalPlan": final_plan()},
    )
    return ledger


class TP18SupersessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_changed_and_unchanged_sections_are_explained_and_prior_is_immutable(self):
        ledger = finalized_ledger(InMemoryPlanEditStore())
        before = ledger.get_finalization(PRIOR_PRIMARY_ID)
        provider = SnapshotProvider()
        generator = Generator()

        result = await PlanSuperseder(
            ledger, provider, generator, clock=lambda: NOW
        ).supersede(PRIOR_PRIMARY_ID, follow_up_delta())

        self.assertEqual([(PATIENT_ID, ENCOUNTER_ID)], provider.calls)
        comparisons = {
            item["section"]: item for item in result.supersession["sectionComparisons"]
        }
        self.assertEqual("unchanged", comparisons["setting"]["status"])
        self.assertEqual("changed", comparisons["pharmacotherapy"]["status"])
        self.assertEqual("unchanged", comparisons["nextAppointment"]["status"])
        self.assertEqual(
            before["finalPlan"]["content"]["setting"],
            result.primary_plan["content"]["setting"],
        )
        self.assertEqual(3, len(result.primary_plan["rationale"]))
        self.assertTrue(all("source snapshot " + SNAPSHOT_ID in item for item in result.primary_plan["rationale"]))
        self.assertTrue(all(
            status in text
            for status, text in zip(
                ("remained unchanged", "changed", "remained unchanged"),
                result.primary_plan["rationale"],
            )
        ))
        self.assertEqual(before, ledger.get_finalization(PRIOR_PRIMARY_ID))
        self.assertEqual(before["finalPlan"]["contentHash"], hash_json({
            key: value for key, value in before["finalPlan"].items() if key != "contentHash"
        }))
        self.assertEqual(
            result.supersession,
            ledger.get_supersession(PRIOR_PRIMARY_ID),
        )
        self.assertEqual(
            result.primary_plan,
            ledger.get(SUCCESSOR_ID).primary_plan,
        )

    async def test_identical_retry_reuses_successor_without_gathering_again(self):
        ledger = finalized_ledger(InMemoryPlanEditStore())
        provider = SnapshotProvider()
        superseder = PlanSuperseder(ledger, provider, Generator(), clock=lambda: NOW)

        first = await superseder.supersede(PRIOR_PRIMARY_ID, follow_up_delta())
        second = await superseder.supersede(PRIOR_PRIMARY_ID, follow_up_delta())

        self.assertEqual(first, second)
        self.assertEqual(1, len(provider.calls))
        changed = follow_up_delta()
        changed["deltaId"] = "00000000-0000-4000-8000-000000000069"
        with self.assertRaises(PlanSuperseded):
            await superseder.supersede(PRIOR_PRIMARY_ID, changed)

    async def test_concurrent_identical_requests_converge_on_one_successor(self):
        ledger = finalized_ledger(InMemoryPlanEditStore())
        provider = ConcurrentSnapshotProvider()
        superseder = PlanSuperseder(ledger, provider, Generator(), clock=lambda: NOW)

        first = asyncio.create_task(
            superseder.supersede(PRIOR_PRIMARY_ID, follow_up_delta())
        )
        second = asyncio.create_task(
            superseder.supersede(PRIOR_PRIMARY_ID, follow_up_delta())
        )
        await provider.both_gathered.wait()
        provider.release.set()
        results = await asyncio.gather(first, second)

        self.assertEqual(results[0], results[1])
        self.assertEqual(
            SUCCESSOR_ID,
            ledger.get_supersession(PRIOR_PRIMARY_ID)["successorPrimaryPlanId"],
        )

    async def test_every_section_requires_a_revalidation_reason_before_persistence(self):
        ledger = finalized_ledger(InMemoryPlanEditStore())
        reasons = {
            "setting": "Still supported.",
            "pharmacotherapy": "Changed after fresh review.",
        }
        with self.assertRaisesRegex(SupersessionError, "every Primary Plan section"):
            await PlanSuperseder(
                ledger, SnapshotProvider(), Generator(reasons), clock=lambda: NOW
            ).supersede(PRIOR_PRIMARY_ID, follow_up_delta())

        self.assertIsNone(ledger.get_supersession(PRIOR_PRIMARY_ID))
        with self.assertRaisesRegex(PlanNotFound, "was not found"):
            ledger.get(SUCCESSOR_ID)

    async def test_delta_and_snapshot_cannot_mix_encounters(self):
        ledger = finalized_ledger(InMemoryPlanEditStore())
        delta = follow_up_delta()
        delta["encounterId"] = PRIOR_ENCOUNTER_ID
        provider = SnapshotProvider()
        with self.assertRaisesRegex(SupersessionError, "new encounter"):
            await PlanSuperseder(
                ledger, provider, Generator(), clock=lambda: NOW
            ).supersede(PRIOR_PRIMARY_ID, delta)
        self.assertEqual([], provider.calls)

    async def test_delta_change_must_be_present_in_the_new_snapshot_sources(self):
        ledger = finalized_ledger(InMemoryPlanEditStore())
        unrelated = snapshot()
        unrelated["sources"][0]["resourceId"] = "different-severity-version"
        with self.assertRaisesRegex(SupersessionError, "absent from the new source snapshot"):
            await PlanSuperseder(
                ledger, SnapshotProvider(unrelated), Generator(), clock=lambda: NOW
            ).supersede(PRIOR_PRIMARY_ID, follow_up_delta())
        self.assertIsNone(ledger.get_supersession(PRIOR_PRIMARY_ID))

    async def test_sqlite_atomically_links_successor_and_rejects_record_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "tp18.sqlite"
            SQLiteRepository(database).migrate()
            ledger = finalized_ledger(SQLitePlanEditStore(database))
            before = ledger.get_finalization(PRIOR_PRIMARY_ID)

            result = await PlanSuperseder(
                ledger, SnapshotProvider(), Generator(), clock=lambda: NOW
            ).supersede(PRIOR_PRIMARY_ID, follow_up_delta())

            self.assertEqual(before, ledger.get_finalization(PRIOR_PRIMARY_ID))
            self.assertEqual(result.primary_plan, ledger.get(SUCCESSOR_ID).primary_plan)
            connection = sqlite3.connect(database)
            try:
                with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                    connection.execute(
                        "UPDATE plan_supersessions SET supersession_record_json = '{}' WHERE prior_plan_id = ?",
                        (PRIOR_PRIMARY_ID,),
                    )
                connection.rollback()
                with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                    connection.execute(
                        "DELETE FROM plan_supersessions WHERE prior_plan_id = ?",
                        (PRIOR_PRIMARY_ID,),
                    )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
