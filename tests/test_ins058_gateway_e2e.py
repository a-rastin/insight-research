"""Live INS-058 acceptance tests.

Set INSIGHT_E2E_BASE_URL and INSIGHT_E2E_FIXTURE to run. The fixture must live
outside this repository because it contains deployment credentials and the
governance-approved synthetic reference case.
"""

import copy
import concurrent.futures
import http.cookiejar
import json
import os
import re
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = (
    "happy-approved-reference",
    "missing-severity",
    "stale-source",
    "conflicting-risk",
    "unresolved-medication",
    "blocked-model",
    "dependency-outage",
    "revoked-account",
    "stale-edit",
    "retry",
)
HAPPY_OPERATIONS = (
    "sign-in",
    "disclaimer",
    "patient",
    "encounter",
    "diagnosis",
    "severity",
    "medical-history",
    "risk",
    "recommendation",
    "review",
    "edit",
    "safety-recheck",
    "finalization",
)
EXPECTED_OUTCOMES = {
    "happy-approved-reference": "finalized",
    "missing-severity": "inputs-incomplete",
    "stale-source": "inputs-incomplete",
    "conflicting-risk": "inputs-incomplete",
    "unresolved-medication": "inputs-incomplete",
    "blocked-model": "generation-failed",
    "dependency-outage": "dependency-unavailable",
    "revoked-account": "unauthorized",
    "stale-edit": "precondition-failed",
    "retry": "idempotent-replay",
}
TOKEN = re.compile(r"\{\{([A-Za-z][A-Za-z0-9_]*)\}\}")


def _lookup(value, selector):
    current = value
    for part in selector.split("."):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def _expand(value, variables):
    if isinstance(value, dict):
        return {key: _expand(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand(item, variables) for item in value]
    if not isinstance(value, str):
        return value
    match = TOKEN.fullmatch(value)
    if match:
        return copy.deepcopy(variables[match.group(1)])
    return TOKEN.sub(lambda found: str(variables[found.group(1)]), value)


def _validate_gateway_path(path):
    parsed = urlsplit(path)
    if not path.startswith("/") or path.startswith("//") or parsed.scheme or parsed.netloc:
        raise ValueError(f"E2E request is not gateway-relative: {path!r}")
    if parsed.query or parsed.fragment:
        raise ValueError("E2E requests must not put clinical data in query strings or fragments")


class GatewayBrowser:
    def __init__(self, base_url):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
            raise ValueError("INSIGHT_E2E_BASE_URL must be a gateway origin")
        self.base_url = base_url.rstrip("/")
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, method, path, *, body=None, headers=None):
        _validate_gateway_path(path)
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Accept": "application/json", **({"Content-Type": "application/json"} if data else {}), **(headers or {})},
        )
        try:
            response = self.opener.open(request, timeout=30)
        except HTTPError as error:
            response = error
        except URLError as error:
            raise AssertionError(f"gateway request failed: {error.reason}") from error
        raw = response.read()
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw.decode("utf-8", "replace")
        return {"status": response.status, "headers": dict(response.headers.items()), "body": payload}


class GatewayScenario:
    def __init__(self, base_url, definition, *, actions=None):
        self.definition = definition
        self.variables = copy.deepcopy(definition.get("variables", {}))
        self.browsers = {}
        self.base_url = base_url
        self.actions = actions or {}

    def run(self, case):
        transcript = []
        for step in self.definition["steps"]:
            expanded = _expand(step, self.variables)
            if "action" in expanded:
                action = expanded["action"]
                if action not in self.actions:
                    raise AssertionError(f"E2E action is not configured: {action}")
                self.actions[action]()
                transcript.append((expanded["operation"], {"action": action}))
                continue
            if "parallel" in expanded:
                requests = []
                for item in expanded["parallel"]:
                    browser = self.browsers.setdefault(
                        item.get("browser", "psychiatrist"), GatewayBrowser(self.base_url)
                    )
                    requests.append((item, browser))
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(requests)) as executor:
                    futures = [
                        executor.submit(
                            browser.request,
                            item["method"],
                            item["path"],
                            body=item.get("body"),
                            headers=item.get("headers"),
                        )
                        for item, browser in requests
                    ]
                    responses = [future.result(timeout=35) for future in futures]
                for (item, _), response in zip(requests, responses):
                    self._accept(item, response, case)
                    transcript.append((item["operation"], response))
                continue
            browser = self.browsers.setdefault(step.get("browser", "psychiatrist"), GatewayBrowser(self.base_url))
            response = browser.request(
                expanded["method"], expanded["path"], body=expanded.get("body"), headers=expanded.get("headers")
            )
            self._accept(expanded, response, case)
            transcript.append((expanded["operation"], response))
        return transcript

    def _accept(self, step, response, case):
        case.assertEqual(step["expectedStatus"], response["status"], step["operation"])
        for selector, expected in step.get("assert", {}).items():
            source, _, path = selector.partition(".")
            case.assertEqual(expected, _lookup(response[source], path) if path else response[source])
        for name, selector in step.get("capture", {}).items():
            source, _, path = selector.partition(".")
            self.variables[name] = _lookup(response[source], path) if path else response[source]
        for selector, variable in step.get("equals", {}).items():
            source, _, path = selector.partition(".")
            case.assertEqual(self.variables[variable], _lookup(response[source], path) if path else response[source])


class HarnessUnitTests(unittest.TestCase):
    def test_expands_captured_values_without_allowing_direct_service_urls(self):
        variables = {"patientId": "00000000-0000-4000-8000-000000000001"}
        self.assertEqual(
            {"path": "/api/patients/" + variables["patientId"]},
            _expand({"path": "/api/patients/{{patientId}}"}, variables),
        )
        for path in ("http://127.0.0.1:8101/api/auth/session", "//service/api", "/api?q=patient"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                _validate_gateway_path(path)


class InitialAssessmentGatewayE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_url = os.environ.get("INSIGHT_E2E_BASE_URL")
        fixture_name = os.environ.get("INSIGHT_E2E_FIXTURE")
        if not base_url or not fixture_name:
            raise unittest.SkipTest("live gateway and approved external INS-058 fixture are not configured")
        fixture_path = Path(fixture_name).resolve()
        if fixture_path == ROOT or ROOT in fixture_path.parents:
            raise RuntimeError("INSIGHT_E2E_FIXTURE must remain outside source control")
        cls.fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        cls.base_url = base_url
        metadata = cls.fixture.get("metadata", {})
        required_metadata = {"synthetic": True, "approved": True, "containsPhi": False, "gatewayOnly": True}
        if any(metadata.get(key) is not expected for key, expected in required_metadata.items()):
            raise RuntimeError("fixture must declare approved synthetic, no-PHI, gateway-only metadata")
        if set(cls.fixture.get("scenarios", {})) != set(SCENARIOS):
            raise RuntimeError("fixture must define exactly the ten INS-058 scenarios")
        operations = tuple(step.get("operation") for step in cls.fixture["scenarios"][SCENARIOS[0]].get("steps", ()))
        positions = [operations.index(operation) for operation in HAPPY_OPERATIONS]
        if positions != sorted(positions):
            raise RuntimeError("happy scenario must automate the complete ordered initial-assessment flow")

    def run_scenario(self, name):
        definition = self.fixture["scenarios"][name]
        self.assertEqual(EXPECTED_OUTCOMES[name], definition.get("expectedOutcome"), name)
        return GatewayScenario(self.base_url, definition).run(self)

    def assert_incomplete_run(self, name):
        transcript = self.run_scenario(name)
        run = next(response for operation, response in transcript if operation == "recommendation")
        self.assertEqual("inputs-incomplete", run["body"]["status"])
        self.assertIsNone(run["body"].get("primaryPlanId"))

    def test_happy_approved_synthetic_reference_case(self):
        transcript = self.run_scenario("happy-approved-reference")
        final = next(response for operation, response in transcript if operation == "finalization")
        self.assertEqual("finalized", final["body"]["status"])

    def test_missing_severity_fails_closed(self):
        self.assert_incomplete_run("missing-severity")

    def test_stale_source_fails_closed(self):
        self.assert_incomplete_run("stale-source")

    def test_conflicting_risk_fails_closed(self):
        self.assert_incomplete_run("conflicting-risk")

    def test_unresolved_medication_fails_closed(self):
        self.assert_incomplete_run("unresolved-medication")

    def test_blocked_model_creates_no_plan(self):
        transcript = self.run_scenario("blocked-model")
        run = next(response for operation, response in transcript if operation == "recommendation")
        self.assertEqual("generation-failed", run["body"]["status"])
        self.assertIsNone(run["body"].get("primaryPlanId"))

    def test_dependency_outage_is_explicit(self):
        transcript = self.run_scenario("dependency-outage")
        self.assertTrue(any(response["status"] == 503 for _, response in transcript))

    def test_revoked_account_loses_access(self):
        transcript = self.run_scenario("revoked-account")
        self.assertTrue(any(response["status"] in {401, 403} for _, response in transcript))

    def test_stale_edit_returns_precondition_failure(self):
        transcript = self.run_scenario("stale-edit")
        self.assertTrue(any(operation == "edit" and response["status"] == 412 for operation, response in transcript))

    def test_retry_replays_prior_result(self):
        definition = self.fixture["scenarios"]["retry"]
        self.assertTrue(any(step.get("equals") for step in definition["steps"]))
        self.run_scenario("retry")


if __name__ == "__main__":
    unittest.main()
