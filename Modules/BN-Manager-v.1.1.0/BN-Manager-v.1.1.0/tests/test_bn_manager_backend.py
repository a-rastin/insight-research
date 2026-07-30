from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import Request
from fastapi.testclient import TestClient

from bn_manager_backend.auth_adapter import SessionState, session_from_payload
from bn_manager_backend.main import create_app
from bn_manager_backend.model_registry import (
    MODEL_REGISTRY,
    MODEL_REGISTRY_DIR,
    read_registry_model,
    resolve_owned_registry_file,
)
from clinical_graph_models import compile_xmlbif


class AdminSessionAdapter:
    def __init__(self) -> None:
        self.session = session_from_payload(
            {
                "authenticated": True,
                "user": {"id": "admin-1", "roles": ["Administrator"]},
                "csrfToken": "csrf-validate",
            }
        )

    def fetch_session(self, request: Request) -> SessionState:
        return self.session


class BnManagerBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())
        self.admin_client = TestClient(create_app(session_adapter=AdminSessionAdapter()))

    def test_health_ready_and_contract_endpoints(self) -> None:
        health = self.client.get("/api/health").json()
        ready = self.client.get("/api/ready").json()
        contract = self.client.get("/api/bn-manager/v1/contract").json()

        self.assertEqual(health["data"]["module_id"], "bn-manager")
        self.assertTrue(ready["data"]["contract_loaded"])
        self.assertEqual(contract["data"]["contract_version"], "3.0.0")
        self.assertEqual(contract["data"]["xml_target"]["extension"], ".xml")

    def test_models_list_contains_exactly_the_four_canonical_networks(self) -> None:
        response = self.client.get("/api/bn-manager/v1/models")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(
            {entry["stable_id"] for entry in payload["models"]},
            {
                "bnm.pharmacotherapy",
                "bnm.treatment-setting",
                "bnm.involuntary-treatment-considerations",
                "bnm.clozapine-suicide-risk",
            },
        )
        self.assertEqual(
            {entry["title"] for entry in payload["models"]},
            {
                "Pharmacotherapy",
                "Treatment Setting",
                "Involuntary Treatment Considerations",
                "Clozapine in Suicide Risk",
            },
        )
        self.assertEqual(payload["schema"], {
            "format": "XML",
            "version": "0.3",
            "path": "schemas/XSD.xml",
        })

    def test_schema_endpoint_returns_supplied_xsd(self) -> None:
        response = self.client.get("/api/bn-manager/v1/models/schema/xml-0.3")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["format"], "XML")
        self.assertEqual(payload["mime_type"], "application/xml")
        self.assertIn('<xs:element name="BIF">', payload["text"])
        self.assertIn('minOccurs="2"', payload["text"])

    def test_every_model_detail_is_xsd_parseable_and_has_its_target(self) -> None:
        schema = self.client.get("/api/bn-manager/v1/models/schema/xml-0.3").json()["data"]["text"]
        for entry in MODEL_REGISTRY:
            with self.subTest(stable_id=entry.stable_id):
                response = self.client.get(f"/api/bn-manager/v1/models/{entry.stable_id}")
                self.assertEqual(response.status_code, 200)
                payload = response.json()["data"]
                self.assertEqual(payload["format"], "XML")
                self.assertTrue(payload["model"]["file_path"].endswith(".xml"))
                model = compile_xmlbif(payload["text"], schema_text=schema)
                self.assertIn(entry.target_node, model.node_map())

    def test_unknown_and_traversal_like_model_ids_return_404(self) -> None:
        for stable_id in (
            "bnm.does-not-exist",
            "..%2Fxml%2FBN-Pharmacotherapy.xml",
            "bnm..pharmacotherapy",
        ):
            with self.subTest(stable_id=stable_id):
                response = self.client.get(f"/api/bn-manager/v1/models/{stable_id}")
                self.assertEqual(response.status_code, 404)

    def test_registry_resolver_rejects_external_paths(self) -> None:
        for path in (
            "../xml/BN-Pharmacotherapy.xml",
            "/etc/passwd",
            str((MODEL_REGISTRY_DIR.parent.parent / "README.md").resolve()),
        ):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    resolve_owned_registry_file(path)

    def test_dashboard_route_discovery_payload_shape(self) -> None:
        response = self.client.get("/internal/dashboard/module-routes/bn-manager")
        route = response.json()["routes"][0]

        self.assertEqual(route["id"], "bn-manager")
        self.assertTrue(route["embed"])
        self.assertTrue(route["requires_verified_session"])

    def test_validate_accepts_registry_model_id_and_compact_cpts(self) -> None:
        for entry in MODEL_REGISTRY:
            with self.subTest(stable_id=entry.stable_id):
                response = self.admin_client.post(
                    "/api/bn-manager/v1/models/validate",
                    json={"model": {"model_id": entry.stable_id}},
                    headers={"x-csrf-token": "csrf-validate"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["data"]["valid"])

    def test_validate_reports_requested_missing_target_node(self) -> None:
        response = self.admin_client.post(
            "/api/bn-manager/v1/models/validate",
            json={
                "model": {"model_id": "bnm.pharmacotherapy"},
                "target_node_ids": ["management_recommendation", "NotARealNode"],
            },
            headers={"x-csrf-token": "csrf-validate"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertFalse(payload["valid"])
        self.assertTrue(any(m["path"] == "target_nodes.NotARealNode" for m in payload["messages"]))

    def test_legacy_net_format_is_rejected_and_convert_route_is_removed(self) -> None:
        _, xml = read_registry_model("bnm.clozapine-suicide-risk")
        validate = self.admin_client.post(
            "/api/bn-manager/v1/models/validate",
            json={"model": {"format": "NET", "text": xml}},
            headers={"x-csrf-token": "csrf-validate"},
        )
        convert = self.admin_client.post(
            "/api/bn-manager/v1/models/convert",
            json={"model": {"format": "NET", "text": "net {}"}},
            headers={"x-csrf-token": "csrf-validate"},
        )

        self.assertEqual(validate.status_code, 415)
        self.assertEqual(validate.json()["error"]["code"], "BNM_UNSUPPORTED_FORMAT")
        self.assertEqual(convert.status_code, 405)

    def test_unknown_registry_model_id_returns_structured_404(self) -> None:
        response = self.admin_client.post(
            "/api/bn-manager/v1/models/validate",
            json={"model": {"model_id": "bnm.unknown"}},
            headers={"x-csrf-token": "csrf-validate"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "BNM_MODEL_NOT_FOUND")

    def test_v3_discovery_exposes_governed_identity_without_model_text(self) -> None:
        response = self.client.get("/api/bn-manager/v3/models")
        self.assertEqual(response.status_code, 200)
        models = response.json()["data"]["models"]
        self.assertEqual(len(models), 4)
        for model in models:
            self.assertRegex(model["content_hash"], r"^sha256:[0-9a-f]{64}$")
            self.assertEqual(model["schema_version"], "BIF-0.3")
            self.assertEqual(model["lifecycle_status"], "active")
            self.assertEqual(model["clinical_use_status"], "research-only")
            self.assertNotIn("text", model)
            self.assertIn("mapping_version", model)

    def test_v3_evaluation_is_traceable_and_idempotent(self) -> None:
        payload = {
            "stable_id": "bnm.clozapine-suicide-risk",
            "evidence": {"Not_A_Node": "Unknown"},
        }
        headers = {"x-csrf-token": "csrf-validate", "idempotency-key": "eval-1"}
        posterior = SimpleNamespace(target="Clinical_Action_Pattern", values={"Review": 1.0})
        with patch("bn_manager_backend.main.evaluate_posterior", return_value=posterior):
            first = self.admin_client.post("/api/bn-manager/v3/evaluations", json=payload, headers=headers)
            second = self.admin_client.post("/api/bn-manager/v3/evaluations", json=payload, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        result = first.json()["data"]
        self.assertRegex(result["evaluation_id"], r"^[0-9a-f-]{36}$")
        self.assertTrue(result["evaluated_at"].endswith("Z"))
        self.assertEqual(result["accepted_evidence"], {})
        self.assertEqual(result["ignored_evidence"]["Not_A_Node"]["reason"], "unknown-variable")
        self.assertEqual(result["target"], "Clinical_Action_Pattern")
        self.assertIn("posterior", result)

    def test_v3_rejects_missing_or_conflicting_idempotency_and_caller_text(self) -> None:
        no_key = self.admin_client.post(
            "/api/bn-manager/v3/evaluations",
            json={"stable_id": "bnm.clozapine-suicide-risk"},
            headers={"x-csrf-token": "csrf-validate"},
        )
        self.assertEqual(no_key.status_code, 400)
        headers = {"x-csrf-token": "csrf-validate", "idempotency-key": "eval-conflict"}
        posterior = SimpleNamespace(target="management_recommendation", values={"Review": 1.0})
        with patch("bn_manager_backend.main.evaluate_posterior", return_value=posterior):
            self.admin_client.post(
                "/api/bn-manager/v3/evaluations",
                json={"stable_id": "bnm.pharmacotherapy"},
                headers=headers,
            )
        conflict = self.admin_client.post(
            "/api/bn-manager/v3/evaluations",
            json={"stable_id": "bnm.treatment-setting"},
            headers=headers,
        )
        self.assertEqual(conflict.status_code, 409)
        legacy_text = self.admin_client.post(
            "/api/bn-manager/v1/dashboard/evaluate",
            json={"format": "XML", "text": "<BIF/>"},
            headers={"x-csrf-token": "csrf-validate"},
        )
        self.assertEqual(legacy_text.status_code, 400)


if __name__ == "__main__":
    unittest.main()
