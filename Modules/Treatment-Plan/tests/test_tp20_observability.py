import io
import json
import logging
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from treatment_plan.app import create_app
from treatment_plan.config import Settings
from treatment_plan.logging import JsonFormatter
from treatment_plan.observability import Observability
from treatment_plan.repository import InMemoryRepository
from treatment_plan.security import InMemoryAuthenticationAdapter, Security, Session
from tests.test_tp15_edit_ledger import PLAN_ID as EDIT_PLAN_ID, ledger, primary_plan


CORRELATION_ID = "00000000-0000-4000-8000-000000000020"
PLAN_ID = "00000000-0000-4000-8000-000000000021"


class TP20ObservabilityTests(unittest.TestCase):
    def test_formatter_and_audit_logger_drop_phi_and_payloads(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())
        logger = logging.Logger("tp20-test")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.info(
            "Patient Alice has F20 and takes clozapine",
            extra={"tp_structured": {
                "event": "test.redaction",
                "diagnosis": "F20",
                "medication": "clozapine",
                "payload": {"patientName": "Alice"},
            }},
        )
        observer = Observability(logger=logger)
        with observer.bind(CORRELATION_ID):
            observer.audit("plan.finalize", "success", actor_id="Dr Alice", entity_id=PLAN_ID)

        output = stream.getvalue()
        for forbidden in ("Alice", "F20", "clozapine", "patientName", "payload", PLAN_ID, CORRELATION_ID):
            self.assertNotIn(forbidden, output)
        self.assertIn("test.redaction", output)
        self.assertIn("security.audit", output)
        self.assertIn("sha256:", output)

    def test_metrics_share_correlation_and_drive_bounded_alerts(self):
        observer = Observability(logger=logging.getLogger("tp20-disabled"))
        observer._logger.disabled = True
        with observer.bind(CORRELATION_ID):
            observer.metric("tp_dependency_failure_total", labels={"dependency": "bn-manager", "outcome": "failure"})
            observer.metric("tp_missing_input_total", labels={"kind": "clinical-context", "dependency": "diagnosis"})
        self.assertEqual({CORRELATION_ID}, {point.correlation_id for point in observer.points()})
        dashboard = observer.dashboard()
        self.assertEqual("degraded", dashboard["status"])
        self.assertEqual({"dependency-failures", "missing-inputs"}, {item["name"] for item in dashboard["alerts"]})
        with self.assertRaises(ValueError):
            observer.metric("tp_bad_label_total", labels={"diagnosis": "F20"})

    def test_override_signal_uses_request_correlation_without_edit_content(self):
        observer = Observability(logger=logging.getLogger("tp20-disabled-override"))
        observer._logger.disabled = True
        service = ledger()
        view = service.register_primary_plan(primary_plan())
        with observer.bind(CORRELATION_ID):
            service.edit(
                EDIT_PLAN_ID, expected_etag=view.etag, actor_id="opaque-actor",
                session_id="opaque-session", path="/content/setting",
                operation="replace", after="inpatient", reason="reviewed",
            )
        override = next(point for point in observer.points() if point.name == "tp_override_total")
        self.assertEqual(CORRELATION_ID, override.correlation_id)
        self.assertEqual("urgent-setting-override", dict(override.labels)["category"])

    def test_audit_and_operational_retrieval_require_distinct_admin_permissions(self):
        expiry = datetime(2099, 1, 1, tzinfo=timezone.utc)
        sessions = {
            "sid=psychiatrist": Session("user-psy", frozenset({"psychiatrist"}), expiry, "csrf", session_id="session-psy"),
            "sid=auditor": Session("user-audit", frozenset({"admin"}), expiry, "csrf", permissions=frozenset({"treatment-plan:audit"}), session_id="session-audit"),
            "sid=support": Session("user-support", frozenset({"admin"}), expiry, "csrf", permissions=frozenset({"treatment-plan:support"}), session_id="session-support"),
        }
        observer = Observability(logger=logging.getLogger("tp20-disabled-routes"))
        observer._logger.disabled = True
        with observer.bind(CORRELATION_ID):
            observer.audit("plan.finalize", "success", actor_id="user-psy", entity_id=PLAN_ID)
            observer.metric("tp_dependency_failure_total", labels={"dependency": "ddi-checker", "outcome": "failure"})
        security = Security(InMemoryAuthenticationAdapter(sessions), observer=observer)
        app = create_app(Settings(environment="test"), InMemoryRepository(), security, observability=observer)

        with TestClient(app) as client:
            audit_path = f"/api/treatment-plan/v1/plans/{PLAN_ID}/audit"
            self.assertEqual(401, client.get(audit_path, headers={"Cookie": "sid=psychiatrist"}).status_code)
            audit = client.get(audit_path, headers={"Cookie": "sid=auditor", "X-Correlation-ID": CORRELATION_ID})
            self.assertEqual(200, audit.status_code)
            self.assertEqual(CORRELATION_ID, audit.headers["X-Correlation-ID"])
            self.assertEqual("AuditEvent", audit.json()[0]["resourceType"])
            self.assertNotIn("sources", json.dumps(audit.json()))

            self.assertEqual(401, client.get("/api/treatment-plan/v1/observability/dashboard", headers={"Cookie": "sid=auditor"}).status_code)
            dashboard = client.get("/api/treatment-plan/v1/observability/dashboard", headers={"Cookie": "sid=support"})
            self.assertEqual(200, dashboard.status_code)
            self.assertEqual("degraded", dashboard.json()["status"])
            metrics = client.get("/metrics", headers={"Cookie": "sid=support"})
            self.assertEqual(200, metrics.status_code)
            self.assertIn("tp_dependency_failure_total", metrics.text)


if __name__ == "__main__":
    unittest.main()

