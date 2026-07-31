"""Live INS-059 follow-up acceptance tests.

Set INSIGHT_E2E_BASE_URL, INSIGHT_FOLLOWUP_E2E_FIXTURE, and
INSIGHT_E2E_RESTART_COMMAND to run. Fixture and deployment credentials must
remain outside this repository.
"""

import json
import os
import shlex
import subprocess
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_ins058_gateway_e2e import GatewayBrowser, GatewayScenario, ROOT


SCENARIOS = (
    "no-change",
    "changed-medication",
    "new-risk",
    "missing-data",
    "concurrent-retry",
    "patient-encounter-mismatch",
    "prior-version-provenance",
    "restart",
)
FOLLOW_UP_OPERATIONS = (
    "sign-in",
    "patient-lookup",
    "prior-history",
    "encounter",
    "follow-up-delta",
    "diagnosis",
    "severity",
    "medical-history",
    "risk",
    "successor-recommendation",
    "successor-review",
    "successor-finalization",
    "longitudinal-history",
)
EXPECTED_OUTCOMES = {
    "no-change": "finalized-unchanged",
    "changed-medication": "finalized-changed",
    "new-risk": "safety-blocked",
    "missing-data": "inputs-incomplete",
    "concurrent-retry": "idempotent-replay",
    "patient-encounter-mismatch": "rejected",
    "prior-version-provenance": "version-preserved",
    "restart": "history-preserved",
}


def _operations(definition):
    return tuple(step.get("operation") for step in definition.get("steps", ()))


def _requires_order(definition, required):
    operations = _operations(definition)
    try:
        positions = [operations.index(operation) for operation in required]
    except ValueError as error:
        raise RuntimeError(f"scenario lacks required operation: {error}") from error
    if positions != sorted(positions):
        raise RuntimeError("follow-up operations must use the required order")


def _run_restart(command):
    subprocess.run(shlex.split(command), check=True, timeout=120)


class HarnessUnitTests(unittest.TestCase):
    def test_required_follow_up_flow_and_restart_action(self):
        definition = {"steps": [{"operation": name} for name in FOLLOW_UP_OPERATIONS]}
        _requires_order(definition, FOLLOW_UP_OPERATIONS)
        with self.assertRaisesRegex(RuntimeError, "lacks required operation"):
            _requires_order({"steps": definition["steps"][:-1]}, FOLLOW_UP_OPERATIONS)

        called = []
        transcript = GatewayScenario(
            "http://gateway.example",
            {"steps": [{"operation": "restart-gateway", "action": "restart"}]},
            actions={"restart": lambda: called.append(True)},
        ).run(self)
        self.assertEqual([True], called)
        self.assertEqual(("restart-gateway", {"action": "restart"}), transcript[0])

    def test_concurrent_retry_requests_run_in_parallel(self):
        barrier = threading.Barrier(2)

        def request(_browser, _method, _path, **_kwargs):
            barrier.wait(timeout=1)
            return {"status": 201, "headers": {}, "body": {"successor": "same"}}

        retry = {
            "operation": "concurrent-successor-retry",
            "parallel": [
                {"operation": "successor-recommendation", "method": "POST", "path": "/retry", "expectedStatus": 201},
                {"operation": "successor-recommendation", "method": "POST", "path": "/retry", "expectedStatus": 201},
            ],
        }
        with patch.object(GatewayBrowser, "request", request):
            transcript = GatewayScenario("http://gateway.example", {"steps": [retry]}).run(self)
        self.assertEqual(2, len(transcript))
        self.assertEqual(transcript[0][1]["body"], transcript[1][1]["body"])


class FollowUpGatewayE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_url = os.environ.get("INSIGHT_E2E_BASE_URL")
        fixture_name = os.environ.get("INSIGHT_FOLLOWUP_E2E_FIXTURE")
        restart_command = os.environ.get("INSIGHT_E2E_RESTART_COMMAND")
        if not base_url or not fixture_name or not restart_command:
            raise unittest.SkipTest("live gateway, approved INS-059 fixture, and restart command are not configured")
        fixture_path = Path(fixture_name).resolve()
        if fixture_path == ROOT or ROOT in fixture_path.parents:
            raise RuntimeError("INSIGHT_FOLLOWUP_E2E_FIXTURE must remain outside source control")
        cls.fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        cls.base_url = base_url
        cls.restart_command = restart_command
        metadata = cls.fixture.get("metadata", {})
        required_metadata = {"synthetic": True, "approved": True, "containsPhi": False, "gatewayOnly": True}
        if any(metadata.get(key) is not expected for key, expected in required_metadata.items()):
            raise RuntimeError("fixture must declare approved synthetic, no-PHI, gateway-only metadata")
        if set(cls.fixture.get("scenarios", {})) != set(SCENARIOS):
            raise RuntimeError("fixture must define exactly the eight INS-059 scenarios")
        for name in ("no-change", "changed-medication"):
            _requires_order(cls.fixture["scenarios"][name], FOLLOW_UP_OPERATIONS)
        retry_groups = [
            step.get("parallel") for step in cls.fixture["scenarios"]["concurrent-retry"]["steps"]
            if "parallel" in step
        ]
        if len(retry_groups) != 1 or len(retry_groups[0]) != 2:
            raise RuntimeError("concurrent-retry must issue exactly two parallel requests")
        if any(item.get("operation") != "successor-recommendation" for item in retry_groups[0]):
            raise RuntimeError("concurrent retry requests must both create the successor recommendation")
        restart_operations = _operations(cls.fixture["scenarios"]["restart"])
        if restart_operations.count("restart-gateway") != 1:
            raise RuntimeError("restart scenario must restart the gateway exactly once")
        restart_step = next(
            step for step in cls.fixture["scenarios"]["restart"]["steps"]
            if step.get("operation") == "restart-gateway"
        )
        if restart_step != {"operation": "restart-gateway", "action": "restart"}:
            raise RuntimeError("restart-gateway must use the external restart action")

    def run_scenario(self, name):
        definition = self.fixture["scenarios"][name]
        self.assertEqual(EXPECTED_OUTCOMES[name], definition.get("expectedOutcome"), name)
        return GatewayScenario(
            self.base_url,
            definition,
            actions={"restart": lambda: _run_restart(self.restart_command)},
        ).run(self)

    def test_no_change_preserves_prior_plan_and_finalizes_successor(self):
        transcript = self.run_scenario("no-change")
        successor = next(response for operation, response in transcript if operation == "successor-recommendation")
        comparisons = successor["body"]["supersession"]["sectionComparisons"]
        self.assertEqual({"unchanged"}, {item["status"] for item in comparisons})
        final = next(response for operation, response in transcript if operation == "successor-finalization")
        self.assertEqual("finalized", final["body"]["status"])

    def test_changed_medication_rechecks_and_finalizes_changed_successor(self):
        transcript = self.run_scenario("changed-medication")
        successor = next(response for operation, response in transcript if operation == "successor-recommendation")
        comparisons = successor["body"]["supersession"]["sectionComparisons"]
        pharmacotherapy = next(item for item in comparisons if item["section"] == "pharmacotherapy")
        self.assertEqual("changed", pharmacotherapy["status"])
        self.assertIn("safety-recheck", _operations(self.fixture["scenarios"]["changed-medication"]))

    def test_new_risk_blocks_routine_successor_finalization(self):
        transcript = self.run_scenario("new-risk")
        self.assertFalse(any(operation == "successor-finalization" and response.get("status") == 201 for operation, response in transcript))

    def test_missing_data_fails_closed(self):
        transcript = self.run_scenario("missing-data")
        recommendation = next(response for operation, response in transcript if operation == "successor-recommendation")
        self.assertEqual("inputs-incomplete", recommendation["body"]["status"])
        self.assertIsNone(recommendation["body"].get("primaryPlanId"))

    def test_concurrent_retry_converges_on_one_successor(self):
        transcript = self.run_scenario("concurrent-retry")
        responses = [response for operation, response in transcript if operation == "successor-recommendation"]
        self.assertEqual(2, len(responses))
        self.assertEqual(responses[0]["body"], responses[1]["body"])

    def test_patient_encounter_mismatch_is_rejected(self):
        transcript = self.run_scenario("patient-encounter-mismatch")
        self.assertTrue(any(response.get("status") in {409, 422} for _, response in transcript))

    def test_prior_version_provenance_remains_visible(self):
        definition = self.fixture["scenarios"]["prior-version-provenance"]
        self.assertGreaterEqual(sum(len(step.get("equals", {})) for step in definition["steps"]), 2)
        self.run_scenario("prior-version-provenance")

    def test_restart_preserves_longitudinal_history(self):
        transcript = self.run_scenario("restart")
        restart_index = next(index for index, item in enumerate(transcript) if item[0] == "restart-gateway")
        history_index = next(index for index, item in enumerate(transcript) if item[0] == "longitudinal-history")
        self.assertLess(restart_index, history_index)


if __name__ == "__main__":
    unittest.main()
