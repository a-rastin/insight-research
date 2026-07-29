import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "context/architecture-decisions/0002-internal-service-authentication.md"
CONTRACT = ROOT / "contracts/internal-service-auth-v1.json"


class InternalServiceAuthContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_adr_schema_and_links(self):
        text = ADR.read_text(encoding="utf-8")
        for field in ("Status", "Date", "Decision owners", "Scope"):
            self.assertRegex(text, rf"(?m)^- {re.escape(field)}: \S+")
        for heading in ("Context", "Decision", "Alternatives", "Consequences", "Verification", "Rollback"):
            self.assertIn(f"## {heading}", text)
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            self.assertNotIn("://", target)
            self.assertTrue((ADR.parent / target).resolve().is_file(), target)

    def test_signed_request_and_destination_policy(self):
        service = self.contract["serviceAuthentication"]
        self.assertEqual(self.contract["schemaVersion"], "1.0.0")
        self.assertEqual(service["algorithm"], "HMAC-SHA256")
        self.assertEqual(service["keyIsolation"], "one-secret-per-caller-destination-pair")
        self.assertIn("reject CR or LF", service["canonicalEncoding"])
        for field in ("destinationServiceId", "uppercaseMethod", "rawPathAndQuery", "lowercaseHexSha256OfExactBody", "requestId", "correlationId", "causationIdOrEmpty"):
            self.assertIn(field, service["canonicalFields"])
        ssrf = self.contract["ssrf"]
        self.assertEqual(ssrf["scheme"], "http")
        self.assertFalse(ssrf["callerSuppliedUrlsAllowed"])
        self.assertFalse(ssrf["redirectsAllowed"])
        self.assertTrue(ssrf["callerMethodPathCapabilitySetRequired"])
        self.assertTrue(ssrf["denyBeforeNetworkAccess"])
        self.assertEqual(ssrf["originMatch"], ["scheme", "ip", "port"])
        self.assertFalse(ssrf["gatewayBasePathIsCapabilityPath"])
        capability = ssrf["capabilityPolicy"]
        self.assertEqual(capability["missingOrInvalidConfiguration"], "deny-all")
        self.assertEqual(capability["methodMatch"], "exact-uppercase")
        self.assertEqual(capability["pathMatch"], "exact-or-prefix-followed-by-slash")
        self.assertEqual(
            set(capability["requiredEntryFields"]),
            {"callerServiceId", "destinationServiceId", "methods", "pathPrefixes"},
        )
        for unsafe_path in (
            "dot-segments",
            "backslashes",
            "percent-encoded-forward-slash",
            "percent-encoded-backslash",
        ):
            self.assertIn(unsafe_path, capability["rejectBeforeMatch"])

    def test_user_background_csrf_and_audit_boundaries(self):
        user = self.contract["userAttribution"]
        self.assertEqual(user["authority"], "GET /api/auth/session")
        self.assertFalse(user["cacheSessionAuthorization"])
        self.assertIn("X-User-ID", user["forbiddenForwardedHeaders"])
        self.assertFalse(self.contract["backgroundCalls"]["userIdentityAllowed"])
        self.assertFalse(self.contract["backgroundCalls"]["finalizationAllowed"])
        self.assertEqual(self.contract["csrf"]["browserWrites"], "validate at first receiving module")
        self.assertFalse(self.contract["trace"]["phiAllowed"])
        security_events = set(self.contract["audit"]["securityEvents"])
        provenance_events = set(self.contract["audit"]["clinicalProvenanceEvents"])
        self.assertTrue(security_events.isdisjoint(provenance_events))

    def test_required_examples(self):
        examples = {item["name"]: item for item in self.contract["examples"]}
        self.assertEqual(
            set(examples),
            {
                "browser-write",
                "user-attributed-server-call",
                "revoked-session",
                "disabled-account",
                "role-change",
                "background-job",
                "untrusted-destination",
            },
        )
        for name in ("revoked-session", "disabled-account"):
            self.assertEqual(examples[name]["result"], "denied")
        self.assertFalse(examples["background-job"]["sessionCookie"])
        self.assertEqual(examples["untrusted-destination"]["result"], "denied-before-network-access")


if __name__ == "__main__":
    unittest.main()
