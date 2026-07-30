import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from treatment_plan.app import create_app
from treatment_plan.config import Settings
from treatment_plan.edit_ledger import (
    EditCategory,
    InMemoryPlanEditStore,
    PlanEditLedger,
    PolicyBound,
    PreconditionFailed,
    ReasonRequired,
)
from treatment_plan.repository import InMemoryRepository
from treatment_plan.security import InMemoryAuthenticationAdapter, Security, Session
from treatment_plan.sqlite_edit_store import SQLitePlanEditStore
from treatment_plan.sqlite_repository import SQLiteRepository


NOW = datetime(2026, 7, 14, 19, 30, tzinfo=timezone.utc)
PLAN_ID = "00000000-0000-4000-8000-000000000015"


def primary_plan():
    return {
        "schemaVersion": "1.0.0",
        "planId": PLAN_ID,
        "status": "generated",
        "content": {
            "setting": "emergency",
            "pharmacotherapy": [
                {
                    "medicationCode": "synthetic-a",
                    "codeSystem": "synthetic",
                    "dose": "10 mg",
                    "route": "oral",
                    "frequency": "daily",
                }
            ],
            "nextAppointment": {"interval": "P1D", "timezone": "America/Los_Angeles"},
        },
        "safetyFindings": [
            {
                "findingId": "ddi-1",
                "category": "interaction",
                "severity": "high",
                "status": "open",
                "summary": "Synthetic severe interaction",
            },
            {
                "findingId": "urgent-1",
                "category": "urgent-risk",
                "severity": "critical",
                "status": "open",
                "summary": "Synthetic urgent setting recommendation",
            },
            {
                "findingId": "warning-1",
                "category": "data-quality",
                "severity": "moderate",
                "status": "open",
                "summary": "Synthetic warning",
            },
        ],
    }


def ledger(store=None):
    return PlanEditLedger(
        store or InMemoryPlanEditStore(),
        policy_bounds={
            "/content/pharmacotherapy/0/dose": PolicyBound(allowed_values=("10 mg", "20 mg"))
        },
        clock=lambda: NOW,
        id_factory=lambda: "00000000-0000-4000-8000-000000000099",
    )


class EditLedgerTests(unittest.TestCase):
    def test_full_plan_is_reconstructed_without_altering_primary_plan(self):
        service = ledger()
        original = primary_plan()
        view = service.register_primary_plan(original)
        view = service.edit(
            PLAN_ID,
            expected_etag=view.etag,
            actor_id="psychiatrist-1",
            session_id="session-1",
            path="/content/setting",
            operation="replace",
            after="inpatient",
            reason="Urgent recommendation override reviewed",
        )
        view = service.edit(
            PLAN_ID,
            expected_etag=view.etag,
            actor_id="psychiatrist-1",
            session_id="session-1",
            path="/content/nextAppointment/interval",
            operation="replace",
            after="P2D",
        )

        reconstructed = service.get(PLAN_ID)
        self.assertEqual("emergency", reconstructed.primary_plan["content"]["setting"])
        self.assertEqual("inpatient", reconstructed.plan["content"]["setting"])
        self.assertEqual("P2D", reconstructed.plan["content"]["nextAppointment"]["interval"])
        self.assertEqual(original, reconstructed.primary_plan)
        self.assertEqual(2, reconstructed.version)
        self.assertEqual("psychiatrist-1", reconstructed.edits[0].actor_id)
        self.assertEqual("session-1", reconstructed.edits[0].session_id)
        self.assertEqual("2026-07-14T19:30:00Z", reconstructed.edits[0].edited_at)

        # Returned mappings are copies; mutating one view cannot mutate the stored fact.
        reconstructed.primary_plan["content"]["setting"] = "outpatient"
        self.assertEqual("emergency", service.get(PLAN_ID).primary_plan["content"]["setting"])

    def test_sensitive_edit_categories_are_derived_and_require_reasons(self):
        cases = [
            ("/safetyFindings/2", "remove", None, EditCategory.WARNING_REMOVAL),
            ("/safetyFindings/0/status", "replace", "overridden", EditCategory.SEVERE_DDI_OVERRIDE),
            ("/content/setting", "replace", "inpatient", EditCategory.URGENT_SETTING_OVERRIDE),
            ("/content/pharmacotherapy/0/dose", "replace", "40 mg", EditCategory.POLICY_BOUND_OVERRIDE),
        ]
        for path, operation, after, expected_category in cases:
            with self.subTest(category=expected_category.value):
                service = ledger()
                view = service.register_primary_plan(primary_plan())
                with self.assertRaisesRegex(ReasonRequired, expected_category.value):
                    service.edit(
                        PLAN_ID,
                        expected_etag=view.etag,
                        actor_id="psychiatrist-1",
                        session_id="session-1",
                        path=path,
                        operation=operation,
                        after=after,
                        reason=" ",
                    )
                accepted = service.edit(
                    PLAN_ID,
                    expected_etag=view.etag,
                    actor_id="psychiatrist-1",
                    session_id="session-1",
                    path=path,
                    operation=operation,
                    after=after,
                    reason="Synthetic review reason",
                )
                self.assertEqual(expected_category, accepted.edits[-1].category)
                self.assertEqual("Synthetic review reason", accepted.edits[-1].reason)

    def test_compare_and_append_rejects_a_lost_update(self):
        service = ledger()
        initial = service.register_primary_plan(primary_plan())
        service.edit(
            PLAN_ID,
            expected_etag=initial.etag,
            actor_id="psychiatrist-1",
            session_id="session-1",
            path="/content/nextAppointment/interval",
            operation="replace",
            after="P2D",
        )
        with self.assertRaises(PreconditionFailed):
            service.edit(
                PLAN_ID,
                expected_etag=initial.etag,
                actor_id="psychiatrist-2",
                session_id="session-2",
                path="/content/nextAppointment/interval",
                operation="replace",
                after="P3D",
            )

    def test_in_memory_and_sqlite_adapters_share_append_only_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "tp.sqlite"
            repository = SQLiteRepository(database)
            repository.migrate()
            adapters = [InMemoryPlanEditStore(), SQLitePlanEditStore(database)]
            for store in adapters:
                with self.subTest(adapter=type(store).__name__):
                    service = ledger(store)
                    initial = service.register_primary_plan(primary_plan())
                    updated = service.edit(
                        PLAN_ID,
                        expected_etag=initial.etag,
                        actor_id="psychiatrist-1",
                        session_id="session-1",
                        path="/content/nextAppointment/interval",
                        operation="replace",
                        after="P2D",
                    )
                    self.assertEqual(1, updated.version)
                    self.assertEqual("P1D", updated.edits[0].before)
                    self.assertEqual("P2D", updated.edits[0].after)
                    self.assertEqual("P1D", updated.primary_plan["content"]["nextAppointment"]["interval"])


class EditLedgerRouteTests(unittest.TestCase):
    def test_authenticated_route_returns_428_and_stale_writes_return_412(self):
        service = ledger()
        initial = service.register_primary_plan(primary_plan())
        session = Session(
            "psychiatrist-1",
            frozenset({"psychiatrist"}),
            NOW + timedelta(hours=1),
            "csrf-secret",
            session_id="auth-session-1",
        )
        security = Security(InMemoryAuthenticationAdapter({"sid=trusted": session}), now=lambda: NOW)
        app = create_app(Settings(environment="test"), InMemoryRepository(), security, service)
        headers = {"Cookie": "sid=trusted", "X-CSRF-Token": "csrf-secret"}

        with TestClient(app) as client:
            missing = client.patch(
                f"/api/treatment-plan/v1/plans/{PLAN_ID}/draft",
                headers=headers,
                json={"operation": "replace", "path": "/content/nextAppointment/interval", "after": "P2D"},
            )
            self.assertEqual(428, missing.status_code)

            first = client.patch(
                f"/api/treatment-plan/v1/plans/{PLAN_ID}/draft",
                headers={**headers, "If-Match": initial.etag},
                json={"operation": "replace", "path": "/content/nextAppointment/interval", "after": "P2D"},
            )
            self.assertEqual(200, first.status_code)
            self.assertNotEqual(initial.etag, first.headers["etag"])
            self.assertEqual("psychiatrist-1", first.json()["edits"][0]["actorId"])
            self.assertEqual("auth-session-1", first.json()["edits"][0]["sessionId"])

            stale = client.patch(
                f"/api/treatment-plan/v1/plans/{PLAN_ID}/draft",
                headers={**headers, "If-Match": initial.etag},
                json={"operation": "replace", "path": "/content/nextAppointment/interval", "after": "P3D"},
            )
            self.assertEqual(412, stale.status_code)

            current = client.get(f"/api/treatment-plan/v1/plans/{PLAN_ID}", headers={"Cookie": "sid=trusted"})
            self.assertEqual(200, current.status_code)
            self.assertEqual("P2D", current.json()["plan"]["content"]["nextAppointment"]["interval"])
            self.assertEqual("P1D", current.json()["primaryPlan"]["content"]["nextAppointment"]["interval"])


if __name__ == "__main__":
    unittest.main()
