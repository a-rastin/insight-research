import hashlib
import json
import re
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "contracts/capability-matrix-v1.json"
SCHEMA_PATH = ROOT / "contracts/capability-matrix-v1.schema.json"
OVERVIEW_PATH = ROOT / "context/project-overview.md"
FEATURE_SPECS = ROOT / "context/feature-specs"


def numbered(prefix, values):
    return {f"{prefix}-{value}" for value in values}


EXPECTED_GOAL_REFS = numbered("goal", range(1, 5))


EXPECTED_SOURCE_REFS = (
    EXPECTED_GOAL_REFS
    | numbered("core-flow", range(1, 13))
    | numbered("feature-clinical", range(1, 8))
    | numbered("feature-decision", range(1, 8))
    | {f"feature-decision-5{suffix}" for suffix in "abcdefghi"}
    | numbered("feature-review", range(1, 7))
    | numbered("feature-platform", range(1, 8))
    | numbered("feature-security", range(1, 8))
    | numbered("feature-admin", range(1, 6))
    | numbered("in-scope", range(1, 11))
    | numbered("out-of-scope", range(1, 6))
    | numbered("success", (1, 2, 3, 4, 5, 7, 8, 9, 10, 11))
)


class CapabilityMatrixContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_matrix_validates_against_schema(self):
        jsonschema.Draft202012Validator(self.schema).validate(self.matrix)

    def test_source_is_hash_locked(self):
        digest = hashlib.sha256(OVERVIEW_PATH.read_bytes()).hexdigest()
        self.assertEqual(self.matrix["source"]["sha256"], digest)

    def test_every_normative_overview_item_has_one_row(self):
        rows = self.matrix["rows"]
        refs = [row["sourceRef"] for row in rows]
        ids = [row["id"] for row in rows]
        self.assertEqual(set(refs), EXPECTED_SOURCE_REFS)
        self.assertEqual(len(refs), len(set(refs)))
        self.assertEqual(ids, [f"CAP-{index:03d}" for index in range(1, len(rows) + 1)])

    def test_every_project_goal_is_expected_explicitly(self):
        actual = {
            row["sourceRef"]
            for row in self.matrix["rows"]
            if row["sourceRef"].startswith("goal-")
        }
        self.assertEqual(actual, EXPECTED_GOAL_REFS)

    def test_every_issue_is_defined(self):
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(FEATURE_SPECS.glob("*.md"))
        )
        defined = set(re.findall(r"^### (INS-[0-9]{3})\b", text, re.MULTILINE))
        referenced = {
            issue
            for row in self.matrix["rows"]
            for issue in row["implementationIssues"]
        }
        self.assertFalse(referenced - defined, referenced - defined)

    def test_contract_references_are_existing_or_owned_plans(self):
        for row in self.matrix["rows"]:
            for reference in row["contractSchemas"]:
                if reference.startswith("planned:"):
                    issue = reference.split(":", 2)[1]
                    self.assertIn(issue, row["implementationIssues"], row["id"])
                else:
                    self.assertTrue((ROOT / reference).is_file(), reference)

    def test_completion_is_fail_closed_and_release_specific(self):
        self.assertEqual(self.matrix["releaseModes"], ["research-build", "controlled-clinical"])
        self.assertEqual(self.matrix["completionContract"]["missingEvidenceRule"], "blocked")
        self.assertIn("INS-011", self.matrix["completionContract"]["clinicalReleaseRule"])
        assistant = next(row for row in self.matrix["rows"] if row["sourceRef"] == "feature-security-7")
        self.assertEqual(assistant["requirement"], "conditional")
        self.assertEqual(assistant["releaseApplicability"]["research-build"], "not-applicable")


if __name__ == "__main__":
    unittest.main()
