import ast
import json
import unittest
from pathlib import Path
from urllib.parse import urldefrag


MODULE = Path(__file__).resolve().parents[1]
OPENAPI_PATH = MODULE / "contracts/openapi/treatment-plan.openapi.v1.1.0.json"
APP_PATH = MODULE / "treatment_plan/app.py"
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
        self.assertFalse(compatibility["runtimeBehaviorChanged"])

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
                self.assertEqual("INS-020", operation["x-insight-implementation-issue"])
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
        self.assertEqual([{"cookieSession": [], "csrfToken": []}], draft["security"])
        self.assertEqual([{"cookieSession": [], "csrfToken": []}], finalization["security"])
        draft_parameters = {item["$ref"] for item in draft["parameters"]}
        final_parameters = {item["$ref"] for item in finalization["parameters"]}
        self.assertIn("#/components/parameters/IfMatch", draft_parameters)
        self.assertIn("#/components/parameters/IfMatch", final_parameters)
        self.assertIn("#/components/parameters/IdempotencyKey", final_parameters)

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
