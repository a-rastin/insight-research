import copy
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "context/architecture-decisions/0009-common-internal-rest-profile.md"
CONTRACTS = ROOT / "contracts"
PROFILE_PATH = CONTRACTS / "common-rest-profile-v1.json"
SCHEMA_PATH = CONTRACTS / "common-rest-profile-v1.schema.json"
OPENAPI_PATH = CONTRACTS / "common-rest-profile-v1.openapi.json"
EXAMPLES_PATH = CONTRACTS / "common-rest-profile-v1.examples.json"
INVALID_PATH = ROOT / "tests/fixtures/common-rest-profile-invalid.json"


class CommonRestProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.openapi = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
        cls.examples = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))
        cls.invalid = json.loads(INVALID_PATH.read_text(encoding="utf-8"))
        cls.format_checker = FormatChecker()

    def validator(self, definition):
        schema = copy.deepcopy(self.schema)
        schema["$ref"] = f"#/$defs/{definition}"
        return Draft202012Validator(schema, format_checker=self.format_checker)

    def test_adr_schema_and_links(self):
        text = ADR.read_text(encoding="utf-8")
        for field in ("Status", "Date", "Decision owners", "Scope"):
            self.assertRegex(text, rf"(?m)^- {re.escape(field)}: \S+")
        for heading in ("Context", "Decision", "Alternatives", "Consequences", "Verification", "Rollback"):
            self.assertIn(f"## {heading}", text)
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            self.assertNotIn("://", target)
            self.assertTrue((ADR.parent / target).resolve().is_file(), target)

    def test_package_is_complete_and_copyable_unchanged(self):
        self.assertEqual(self.profile["profileVersion"], "1.0.0")
        self.assertTrue(self.profile["packaging"]["copyUnchanged"])
        self.assertTrue(self.profile["packaging"]["sameDirectoryRequired"])
        for artifact in self.profile["artifacts"]:
            self.assertTrue((CONTRACTS / artifact).is_file(), artifact)

    def test_valid_schema_examples(self):
        mapping = {
            "uuid": "uuid",
            "utcTimestamp": "utcTimestamp",
            "requestHeaders": "requestHeaders",
            "responseHeaders": "responseHeaders",
            "health": "health",
            "readiness": "readiness",
            "contractDiscovery": "contractDiscovery",
            "problemDetails": "problemDetails",
        }
        for example, definition in mapping.items():
            self.validator(definition).validate(self.examples[example])

    def test_invalid_uuid_time_header_and_error_fixtures(self):
        for definition, values in self.invalid.items():
            validator = self.validator(definition)
            for value in values:
                self.assertTrue(list(validator.iter_errors(value)), (definition, value))

    def test_openapi_components_lint_and_resolve(self):
        self.assertEqual(self.openapi["openapi"], "3.1.0")
        self.assertEqual(self.openapi["info"]["version"], self.profile["profileVersion"])
        self.assertEqual(self.openapi["paths"], {})
        refs = []

        def collect(value):
            if isinstance(value, dict):
                refs.extend(item for key, item in value.items() if key == "$ref")
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(self.openapi)
        for ref in refs:
            if ref.startswith("#/"):
                target = self.openapi
                for part in ref[2:].split("/"):
                    target = target[part]
                self.assertIsInstance(target, dict)
            else:
                filename, fragment = ref.split("#", 1)
                self.assertEqual(filename, SCHEMA_PATH.name)
                target = self.schema
                for part in fragment.removeprefix("/").split("/"):
                    target = target[part]
                self.assertIsInstance(target, dict)

        components = self.openapi["components"]
        self.assertEqual(set(components["schemas"]), {"ProblemDetails", "Health", "Readiness", "ContractDiscovery"})
        self.assertIn("If-Match", components["parameters"])
        self.assertIn("Idempotency-Key", components["parameters"])
        self.assertIn("application/problem+json", components["responses"]["Problem"]["content"])

    def test_provider_consumer_major_compatibility_fails_closed(self):
        negotiation = self.profile["schemaNegotiation"]
        self.assertTrue(negotiation["majorIsCompatibilityBoundary"])
        self.assertEqual(negotiation["unsupportedRequestMajor"], {"status": 400, "code": "COMMON_UNSUPPORTED_SCHEMA_MAJOR"})
        self.assertEqual(negotiation["unsupportedResponseMajor"]["consumerAction"], "reject-before-use-or-persistence")
        self.assertEqual(negotiation["unsupportedResponseMajor"]["dependencyStatus"], 502)

        supported_major = self.profile["profileVersion"].split(".", 1)[0]
        self.assertEqual("1.9.0".split(".", 1)[0], supported_major)
        self.assertNotEqual("2.0.0".split(".", 1)[0], supported_major)

    def test_compatibility_deprecation_concurrency_and_idempotency(self):
        compatibility = self.profile["compatibility"]
        self.assertTrue(compatibility["minorMayAddOptionalFields"])
        for rule in ("newRequiredFieldRequiresNewMajor", "fieldRemovalRequiresNewMajor", "meaningChangeRequiresNewMajor"):
            self.assertTrue(compatibility[rule])

        deprecation = self.profile["deprecation"]
        self.assertFalse(deprecation["inPlaceRemovalWithinMajorAllowed"])
        self.assertTrue(deprecation["allConsumersMustPassCompatibilityTests"])
        self.assertTrue(deprecation["rolloutMustCompleteBeforeSunset"])

        concurrency = self.profile["concurrency"]
        self.assertEqual(concurrency["mutableResourceEtag"], "strong-required")
        self.assertFalse(concurrency["ifMatchWildcardAllowed"])
        self.assertEqual(concurrency["missingIfMatch"]["status"], 428)
        self.assertEqual(concurrency["staleIfMatch"]["status"], 412)

        idempotency = self.profile["idempotency"]
        self.assertIn("without-reexecution", idempotency["sameFingerprint"])
        self.assertEqual(idempotency["differentFingerprint"]["status"], 409)
        self.assertEqual(idempotency["differentFingerprint"]["code"], "COMMON_IDEMPOTENCY_KEY_REUSED")

    def test_problem_contract_excludes_unsafe_fields(self):
        problem = self.profile["problemDetails"]
        for field in ("instance", "path", "stackTrace", "token", "secret", "patientId", "patientCode", "patientName"):
            self.assertIn(field, problem["forbiddenFields"])
        self.assertTrue(problem["boundaryRedactionRequired"])
        self.assertFalse(problem["phiAllowed"])
        self.assertFalse(problem["credentialsAllowed"])
        self.assertFalse(problem["filesystemPathsAllowed"])
        self.assertFalse(problem["stackTracesAllowed"])


if __name__ == "__main__":
    unittest.main()
