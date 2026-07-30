import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
DDI = ROOT / "Modules" / "DDI-Checker-1.2.0"
CONTRACTS = DDI / "contracts"


class DdiV1ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((CONTRACTS / "ddi-v1.contract.json").read_text())
        cls.schema = json.loads((CONTRACTS / "ddi-v1.schema.json").read_text())
        cls.openapi = json.loads((CONTRACTS / "openapi-v1.json").read_text())
        Draft202012Validator.check_schema(cls.schema)

    def validator(self, definition):
        return Draft202012Validator(
            {**self.schema, "$ref": f"#/$defs/{definition}"},
            format_checker=FormatChecker(),
        )

    def test_contract_covers_lifecycle_permissions_override_and_errors(self):
        lifecycle = self.contract["knowledgeRevisionLifecycle"]
        self.assertEqual(lifecycle["states"], ["draft", "reviewed", "active", "retired"])
        self.assertEqual(lifecycle["transitions"]["active"], ["retired"])
        self.assertTrue(lifecycle["immutableAfterActivation"])
        self.assertTrue(lifecycle["singleActiveRevision"])
        self.assertTrue(lifecycle["rollback"]["doesNotMutateHistoricalChecks"])

        permissions = self.contract["permissions"]
        self.assertIn("activate-reviewed-revision", permissions["admin"])
        self.assertIn("review-revision", permissions["clinicalReviewer"])
        self.assertIn("override-high-finding", permissions["psychiatrist"])
        self.assertIn("override-clinical-finding", permissions["forbidden"]["admin"])

        override = self.contract["findingsAndAudit"]["override"]
        self.assertEqual(override["allowedRole"], "psychiatrist")
        self.assertEqual(override["allowedSeverities"], ["high"])
        self.assertEqual((override["rationaleMinLength"], override["rationaleMaxLength"]), (20, 2000))
        self.assertTrue(override["preserveOriginalFinding"])
        self.assertTrue(self.contract["findingsAndAudit"]["clinicalAuditAppendOnly"])
        self.assertTrue(self.contract["findingsAndAudit"]["securityAuditSeparate"])

        for code in (
            "DDI_IDEMPOTENCY_KEY_REUSED",
            "DDI_REVISION_TRANSITION_INVALID",
            "DDI_MEDICATION_SET_HASH_MISMATCH",
            "DDI_NO_ACTIVE_KNOWLEDGE_REVISION",
        ):
            self.assertIn(code, self.contract["errors"])

    def test_treatment_plan_aligned_check_request_and_response_validate(self):
        digest_a = "sha256:" + "a" * 64
        digest_b = "sha256:" + "b" * 64
        request = {
            "schemaVersion": "1.0.0",
            "idempotencyKey": digest_a,
            "planSemanticHash": digest_a,
            "medicationSetHash": digest_b,
            "medications": [
                {
                    "inputIndex": 0,
                    "source": "current",
                    "originalText": "medication entered by clinician",
                },
                {
                    "inputIndex": 1,
                    "source": "proposed",
                    "originalText": "12345",
                    "medicationCode": "12345",
                    "codeSystem": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "dose": "example dose",
                    "route": "oral",
                    "frequency": "daily",
                },
            ],
        }
        self.validator("checkRequest").validate(request)

        response = {
            "schemaVersion": "1.0.0",
            "checkId": "00000000-0000-4000-8000-000000000001",
            "medicationSetHash": digest_b,
            "knowledgeBaseId": "00000000-0000-4000-8000-000000000002",
            "knowledgeBaseVersion": "1.2.3",
            "knowledgeBaseContentHash": digest_a,
            "coverageStatus": "incomplete",
            "normalizedMedications": [
                {
                    "inputIndex": 1,
                    "status": "resolved",
                    "originalText": "12345",
                    "conceptId": "12345",
                    "codeSystem": "RxNorm",
                    "display": "Example medication",
                }
            ],
            "unresolvedMedications": [
                {
                    "inputIndex": 0,
                    "status": "unknown",
                    "originalText": "medication entered by clinician",
                    "reason": "no-active-concept-match",
                    "candidates": [],
                }
            ],
            "pairsChecked": [],
            "alerts": [],
            "checkedAt": "2026-07-30T00:00:00Z",
        }
        self.validator("checkResponse").validate(response)

    def test_resolution_and_override_fail_closed(self):
        invalid_resolved = {
            "inputIndex": 0,
            "status": "resolved",
            "originalText": "unknown",
        }
        self.assertTrue(list(self.validator("medicationResolution").iter_errors(invalid_resolved)))

        blank_candidates = {
            "inputIndex": 0,
            "status": "ambiguous",
            "originalText": "shared label",
            "reason": "multiple-matches",
            "candidates": [],
        }
        self.assertTrue(list(self.validator("medicationResolution").iter_errors(blank_candidates)))

        override_without_rationale = {
            "actionId": "00000000-0000-4000-8000-000000000003",
            "alertId": "00000000-0000-4000-8000-000000000004",
            "action": "overridden",
            "actorId": "00000000-0000-4000-8000-000000000005",
            "actorRole": "psychiatrist",
            "recordedAt": "2026-07-30T00:00:00Z",
        }
        self.assertTrue(list(self.validator("findingAction").iter_errors(override_without_rationale)))

    def test_openapi_publishes_treatment_plan_check_endpoint(self):
        self.assertEqual(self.openapi["openapi"], "3.1.0")
        operation = self.openapi["paths"]["/checks"]["post"]
        self.assertEqual(operation["operationId"], "createDdiClinicalCheck")
        refs = json.dumps(operation)
        self.assertIn("#/$defs/checkRequest", refs)
        self.assertIn("#/$defs/checkResponse", refs)
        parameters = {item["name"]: item for item in operation["parameters"]}
        self.assertTrue(parameters["Idempotency-Key"]["required"])
        self.assertTrue(parameters["X-Schema-Version"]["required"])
        for path in (
            "/knowledge-revisions",
            "/knowledge-revisions/{revisionId}/review",
            "/knowledge-revisions/{revisionId}/activate",
            "/knowledge-revisions/{revisionId}/rollback",
            "/checks/{checkId}/findings/{alertId}/actions",
        ):
            self.assertIn(path, self.openapi["paths"])

    def test_contract_package_is_complete(self):
        self.assertEqual(self.contract["interfaceVersion"], "1.0.0")
        self.assertEqual(self.contract["commonRestProfile"], "1.0.0")
        self.assertEqual(self.contract["clinicalCheck"]["consumer"], "treatment-plan")
        self.assertTrue(self.contract["identityResolution"]["unresolvedCoverageIsNotNoInteraction"])
        for artifact in self.contract["artifacts"]:
            self.assertTrue((CONTRACTS / artifact).is_file(), artifact)


if __name__ == "__main__":
    unittest.main()
