import json
import unittest
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from treatment_plan.app import create_app
from treatment_plan.config import Settings
from treatment_plan.repository import InMemoryRepository


MODULE = Path(__file__).resolve().parents[1]
ROOT = MODULE.parents[1]
COMMON_SCHEMA = json.loads((ROOT / "contracts/common-rest-profile-v1.schema.json").read_text(encoding="utf-8"))


class TreatmentPlanDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(Settings(environment="test"), InMemoryRepository()))

    def tearDown(self):
        self.client.close()

    def test_contract_discovers_canonical_openapi_without_authentication(self):
        response = self.client.get("/api/treatment-plan/v1/contract")
        self.assertEqual(200, response.status_code)
        discovery = response.json()
        schema = {**COMMON_SCHEMA, "$ref": "#/$defs/contractDiscovery"}
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(discovery)
        self.assertEqual("treatment-plan", discovery["moduleId"])
        self.assertEqual(["1.0.0", "1.1.0"], discovery["schemaVersions"])
        self.assertEqual("1.1.0", response.headers["X-Schema-Version"])
        UUID(response.headers["X-Request-ID"])
        UUID(response.headers["X-Correlation-ID"])

        root_request_id = "00000000-0000-4000-8000-000000000049"
        traced = self.client.get(
            "/api/treatment-plan/v1/contract", headers={"X-Request-ID": root_request_id}
        )
        self.assertEqual(root_request_id, traced.headers["X-Correlation-ID"])
        self.assertNotEqual(root_request_id, traced.headers["X-Request-ID"])

        openapi = self.client.get(discovery["openapiPath"])
        expected = json.loads(
            (MODULE / "contracts/openapi/treatment-plan.openapi.v1.1.0.json").read_text(encoding="utf-8")
        )
        self.assertEqual(200, openapi.status_code)
        self.assertEqual(expected, openapi.json())

    def test_schema_route_serves_only_registered_artifacts(self):
        cases = {
            ("audit-event", "1.0.0"): "contracts/schemas/1.0.0/audit-event.schema.json",
            ("runtime-api", "1.1.0"): "contracts/schemas/1.1.0/runtime-api.schema.json",
            ("treatment-plan", "1.0.0"): "contracts/schemas/1.0.0/treatment-plan.schema.json",
        }
        for (name, version), relative_path in cases.items():
            with self.subTest(name=name, version=version):
                response = self.client.get(f"/api/treatment-plan/v1/schemas/{name}/{version}")
                self.assertEqual(200, response.status_code)
                self.assertTrue(response.headers["content-type"].startswith("application/schema+json"))
                self.assertEqual(
                    json.loads((MODULE / relative_path).read_text(encoding="utf-8")),
                    response.json(),
                )

        for path in (
            "/api/treatment-plan/v1/schemas/unknown/1.0.0",
            "/api/treatment-plan/v1/schemas/runtime-api/9.0.0",
            "/api/treatment-plan/v1/schemas/../1.1.0",
        ):
            with self.subTest(path=path):
                self.assertEqual(404, self.client.get(path).status_code)

    def test_release_image_contains_canonical_contract_artifacts(self):
        dockerfile = (MODULE / "Dockerfile.release").read_text(encoding="utf-8")
        self.assertIn("COPY --chown=10001:10001 contracts ./contracts", dockerfile)


if __name__ == "__main__":
    unittest.main()
