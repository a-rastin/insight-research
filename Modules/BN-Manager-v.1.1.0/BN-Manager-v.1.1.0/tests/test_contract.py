from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from clinical_graph_models import (
    CLINICAL_SAFETY_WORDING,
    CONTRACT_VERSION,
    DECISION_IDS,
    ERROR_CODES,
    MODULE_ID,
    PERMISSIONS,
    ROLE_PERMISSIONS,
    ROUTES,
    ROUTE_PREFIX,
    TARGET_NODE_IDS,
    XMLBIF_TARGET,
    contract_payload,
    error_response,
    ok_response,
)

ROOT = Path(__file__).resolve().parent.parent


class BnManagerContractTests(unittest.TestCase):
    def test_module_identity_and_xml_target_are_versioned(self) -> None:
        self.assertEqual(MODULE_ID, "bn-manager")
        self.assertEqual(CONTRACT_VERSION, "3.2.0")
        self.assertEqual(ROUTE_PREFIX, "/api/bn-manager/v1")
        self.assertEqual(XMLBIF_TARGET.format_id, "XML")
        self.assertEqual(XMLBIF_TARGET.version, "0.3")
        self.assertEqual(XMLBIF_TARGET.extension, ".xml")
        self.assertEqual(XMLBIF_TARGET.variable_types, ("nature",))
        self.assertIn(".net", XMLBIF_TARGET.compatibility_note)

    def test_surfaces_have_owned_routes_and_no_conversion_route(self) -> None:
        by_surface = {route.surface: route for route in ROUTES}

        self.assertEqual(by_surface["Dashboard"].path, f"{ROUTE_PREFIX}/dashboard/evaluate")
        self.assertEqual(by_surface["Add New Patient"].path, f"{ROUTE_PREFIX}/add-new-patient/evaluate")
        self.assertEqual(by_surface["Follow-up"].path, f"{ROUTE_PREFIX}/follow-up/evaluate")
        self.assertTrue(all(route.permission in PERMISSIONS.values() for route in ROUTES))
        self.assertFalse(any("convert" in route.path for route in ROUTES))
        self.assertNotIn("convert_model", PERMISSIONS)

    def test_target_ids_cover_the_four_xml_networks(self) -> None:
        self.assertEqual(
            DECISION_IDS,
            {
                "pharmacotherapy": "management_recommendation",
                "treatment_setting": "management_recommendation",
                "involuntary_treatment_considerations": "management_recommendation",
                "clozapine_suicide_risk": "Clinical_Action_Pattern",
            },
        )
        self.assertEqual(TARGET_NODE_IDS, ("management_recommendation", "Clinical_Action_Pattern"))

    def test_role_permissions_cover_user_facing_routes(self) -> None:
        self.assertIn(PERMISSIONS["evaluate_dashboard"], ROLE_PERMISSIONS["Psychiatrist"])
        self.assertIn(PERMISSIONS["evaluate_add_new_patient"], ROLE_PERMISSIONS["IntakeClinician"])
        self.assertIn(PERMISSIONS["evaluate_follow_up"], ROLE_PERMISSIONS["CareTeam"])
        self.assertIn(PERMISSIONS["validate_model"], ROLE_PERMISSIONS["ModelManager"])
        self.assertEqual(set(ROLE_PERMISSIONS["Admin"]), set(PERMISSIONS.values()))

    def test_response_envelope_and_errors_are_stable(self) -> None:
        ok = ok_response({"rankings": []}, request_id="req-1")
        error = error_response(ERROR_CODES["invalid_request"], "Bad payload", request_id="req-2")

        self.assertEqual(set(ok), {"ok", "data", "error", "meta"})
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["meta"]["module_id"], MODULE_ID)
        self.assertIn(CLINICAL_SAFETY_WORDING, ok["meta"]["clinical_safety_wording"])
        self.assertEqual(error["error"]["code"], "BNM_INVALID_REQUEST")
        with self.assertRaises(ValueError):
            error_response("BNM_NOT_REAL", "Bad payload")

    def test_contract_payload_exposes_xml_target_and_module_boundary(self) -> None:
        payload = contract_payload()

        self.assertEqual(payload["contract_version"], "3.2.0")
        self.assertEqual(payload["xml_target"]["extension"], ".xml")
        self.assertNotIn("xmlbif_target", payload)
        self.assertIn("No direct imports or database reads", payload["module_boundary"])

    def test_package_has_no_cross_surface_or_database_imports(self) -> None:
        forbidden_roots = {
            "add_new_patient",
            "asyncpg",
            "dashboard",
            "follow_up",
            "followup",
            "mysql",
            "patients",
            "psycopg",
            "psycopg2",
            "pymongo",
            "sqlalchemy",
            "sqlite3",
        }
        violations: list[str] = []
        for path in (ROOT / "clinical_graph_models").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                else:
                    continue
                for module in modules:
                    if module.split(".", 1)[0] in forbidden_roots:
                        violations.append(f"{path.relative_to(ROOT)} imports {module}")

        self.assertEqual(violations, [])

    def test_v3_machine_contract_publishes_actual_routes_and_strict_request(self) -> None:
        contract_dir = ROOT / "contracts"
        contract = json.loads((contract_dir / "bn-manager-v3.contract.json").read_text(encoding="utf-8"))
        schema = json.loads((contract_dir / "bn-manager-v3.schema.json").read_text(encoding="utf-8"))
        openapi = json.loads((contract_dir / "openapi-v3.json").read_text(encoding="utf-8"))

        self.assertEqual(contract["interfaceVersion"], "3.2.0")
        expected_paths = {
            "/models", "/models/{stable_id}", "/evaluations", "/admin/models",
            "/admin/models/{stable_id}", "/admin/models/{stable_id}/review",
            "/admin/models/{stable_id}/activate", "/admin/models/{stable_id}/retire",
            "/admin/models/{stable_id}/rollback",
        }
        self.assertEqual(set(openapi["paths"]), expected_paths)
        app_tree = ast.parse((ROOT / "bn_manager_backend/main.py").read_text(encoding="utf-8"))
        runtime_paths = {
            ast.literal_eval(decorator.args[0]).removeprefix("/api/bn-manager/v3")
            for node in ast.walk(app_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
            and str(decorator.args[0].value).startswith("/api/bn-manager/v3")
        }
        self.assertEqual(runtime_paths, expected_paths)
        self.assertFalse(schema["$defs"]["evaluationRequest"]["additionalProperties"])
        self.assertEqual(
            set(schema["$defs"]["evaluationRequest"]["properties"]),
            {"stable_id", "candidate_id", "evidence"},
        )
        self.assertFalse(contract["callerModelText"]["allowedForV3Evaluation"])
        self.assertEqual(contract["callerModelText"]["allowedRole"], "admin")
        self.assertTrue(contract["registryAdministration"]["manifestOwnedOnly"])
        self.assertFalse(contract["registryAdministration"]["callerPathsAllowed"])


if __name__ == "__main__":
    unittest.main()
