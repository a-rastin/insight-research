import ast
import json
import unittest
from pathlib import Path
from urllib.parse import urldefrag


MODULE = Path(__file__).resolve().parents[1]
OPENAPI_PATH = MODULE / "contracts/openapi/treatment-plan.openapi.v1.1.0.json"
APP_PATH = MODULE / "treatment_plan/app.py"
BN_ADAPTER_PATH = MODULE / "treatment_plan/bn_evaluation.py"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


class TreatmentPlanContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.openapi = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
        cls.app_tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))

    def test_openapi_31_is_versioned_and_records_compatibility(self):
        self.assertEqual("3.1.0", self.openapi["openapi"])
        self.assertEqual("1.1.0", self.openapi["info"]["version"])
        compatibility = self.openapi["x-insight-compatibility"]
        self.assertEqual("breaking-contract-correction", compatibility["classification"])
        self.assertTrue(compatibility["runtimeBehaviorChanged"])
        self.assertTrue(compatibility["newClinicalBehavior"])

    def test_live_router_and_openapi_have_exact_operation_parity(self):
        live = set()
        for node in ast.walk(self.app_tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                method = decorator.func.attr.lower()
                if method not in HTTP_METHODS or not decorator.args:
                    continue
                path = ast.literal_eval(decorator.args[0])
                if path == "/modules/treatment-plan":
                    continue
                live.add((method, path))
        published = {
            (method, path)
            for path, path_item in self.openapi["paths"].items()
            for method in path_item
            if method in HTTP_METHODS
        }
        self.assertEqual(live, published)

    def test_every_operation_has_unique_id_and_implementation_issue(self):
        operation_ids = []
        for path_item in self.openapi["paths"].values():
            for method, operation in path_item.items():
                if method not in HTTP_METHODS:
                    continue
                operation_ids.append(operation["operationId"])
                expected_issue = "INS-049" if operation["operationId"] in {
                    "discoverTreatmentPlanContract", "getTreatmentPlanOpenApi", "getTreatmentPlanSchema"
                } else "INS-050" if operation["operationId"] in {
                    "createRecommendationRun", "getRecommendationRun"
                } else "INS-053" if operation["operationId"] == "supersedeTreatmentPlan" else "INS-020"
                if operation["operationId"] == "requestTreatmentPlanAssistantAdvisory":
                    expected_issue = "INS-055"
                self.assertEqual(expected_issue, operation["x-insight-implementation-issue"])
                self.assertIn("responses", operation)
        self.assertEqual(len(operation_ids), len(set(operation_ids)))

    def test_all_json_references_resolve_with_valid_fragments(self):
        documents = {OPENAPI_PATH.resolve(): self.openapi}

        def load(path):
            path = path.resolve()
            if path not in documents:
                documents[path] = json.loads(path.read_text(encoding="utf-8"))
            return documents[path]

        def resolve(document_path, reference):
            target_name, fragment = urldefrag(reference)
            target_path = (document_path.parent / target_name).resolve() if target_name else document_path
            target = load(target_path)
            if fragment:
                self.assertTrue(fragment.startswith("/"))
                for token in fragment[1:].split("/"):
                    token = token.replace("~1", "/").replace("~0", "~")
                    target = target[int(token)] if isinstance(target, list) else target[token]
            return target_path, target

        pending = [(OPENAPI_PATH.resolve(), self.openapi)]
        seen = set()
        while pending:
            document_path, value = pending.pop()
            marker = (document_path, id(value))
            if marker in seen:
                continue
            seen.add(marker)
            if isinstance(value, dict):
                reference = value.get("$ref")
                if reference:
                    target_path, target = resolve(document_path, reference)
                    pending.append((target_path, target))
                pending.extend((document_path, item) for item in value.values())
            elif isinstance(value, list):
                pending.extend((document_path, item) for item in value)

    def test_provider_contract_paths_are_real_and_security_controls_are_published(self):
        for provider in self.openapi["x-insight-provider-contracts"]:
            reference = provider.get("schema") or provider.get("openapi")
            if reference:
                self.assertTrue((OPENAPI_PATH.parent / reference).resolve().is_file())

        draft = self.openapi["paths"]["/api/treatment-plan/v1/plans/{plan_id}/draft"]["patch"]
        finalization = self.openapi["paths"]["/api/treatment-plan/v1/plans/{plan_id}/finalize"]["post"]
        supersession = self.openapi["paths"]["/api/treatment-plan/v1/plans/{plan_id}/supersede"]["post"]
        self.assertEqual([{"cookieSession": [], "csrfToken": []}], draft["security"])
        self.assertEqual([{"cookieSession": [], "csrfToken": []}], finalization["security"])
        self.assertEqual([{"cookieSession": [], "csrfToken": []}], supersession["security"])
        draft_parameters = {item["$ref"] for item in draft["parameters"]}
        final_parameters = {item["$ref"] for item in finalization["parameters"]}
        self.assertIn("#/components/parameters/IfMatch", draft_parameters)
        self.assertIn("#/components/parameters/IfMatch", final_parameters)
        self.assertIn("#/components/parameters/IdempotencyKey", final_parameters)
        supersession_parameters = {item["$ref"] for item in supersession["parameters"]}
        self.assertIn("#/components/parameters/IdempotencyKey", supersession_parameters)
        self.assertIn("#/components/parameters/RequestId", supersession_parameters)
        bn_provider = next(
            provider for provider in self.openapi["x-insight-provider-contracts"]
            if provider["provider"] == "bn-manager"
        )
        self.assertEqual("POST /api/bn-manager/v3/evaluations", bn_provider["operation"])
        bn_openapi = json.loads(
            (OPENAPI_PATH.parent / bn_provider["openapi"]).resolve().read_text(encoding="utf-8")
        )
        self.assertIn("post", bn_openapi["paths"]["/evaluations"])
        adapter_source = BN_ADAPTER_PATH.read_text(encoding="utf-8")
        self.assertIn("/api/bn-manager/v3/evaluations", adapter_source)
        self.assertNotIn("/api/bn-manager/v1/evaluations", adapter_source)

    def test_plan_ids_are_uuids_and_request_id_matches_common_profile(self):
        plan_id = self.openapi["components"]["parameters"]["PlanId"]
        request_id = self.openapi["components"]["parameters"]["RequestId"]
        self.assertEqual("uuid", plan_id["schema"]["format"])
        self.assertTrue(request_id["required"])
        self.assertEqual("uuid", request_id["schema"]["format"])

        annotations = {
            node.name: ast.unparse(argument.annotation)
            for node in ast.walk(self.app_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for argument in node.args.args
            if argument.arg == "plan_id" and argument.annotation is not None
        }
        self.assertEqual(
            {"read_plan", "supersede_plan", "edit_draft", "finalize_plan", "read_plan_provenance", "read_plan_audit"},
            set(annotations),
        )
        self.assertEqual({"UUID"}, set(annotations.values()))

    def test_runtime_response_envelopes_and_schema_headers_are_exact(self):
        plan_response = self.openapi["paths"]["/api/treatment-plan/v1/plans/{plan_id}"]["get"]["responses"]["200"]
        self.assertEqual(
            "../schemas/1.1.0/runtime-api.schema.json#/$defs/PlanView",
            plan_response["content"]["application/json"]["schema"]["$ref"],
        )
        self.assertEqual(
            "#/components/headers/PlanViewSchemaVersion",
            plan_response["headers"]["X-Schema-Version"]["$ref"],
        )
        problem = self.openapi["components"]["responses"]["RuntimeError"]["content"]
        self.assertEqual({"application/json"}, set(problem))


if __name__ == "__main__":
    unittest.main()
