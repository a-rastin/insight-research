from __future__ import annotations

import unittest

from clinical_graph_models import Node, Potential, ValidationMessage, validate_model
from clinical_graph_models.model import ClinicalGraphModel


def _make_node(name: str, kind: str = "chance", states: list[str] | None = None) -> Node:
    return Node(name=name, kind=kind, attributes={"states": states if states is not None else ["No", "Yes"]})


def _make_potential(child: str, parents: list[str] | None = None, data: object | None = None) -> Potential:
    return Potential(child=child, parents=list(parents or []), attributes={"data": data})


class ValidateModelTests(unittest.TestCase):
    def _model(self, nodes: list[Node], potentials: list[Potential]) -> ClinicalGraphModel:
        return ClinicalGraphModel(attributes={"name": "Test"}, nodes=nodes, potentials=potentials)

    def _errors(self, model: ClinicalGraphModel, **kwargs) -> list[ValidationMessage]:
        return [m for m in validate_model(model, **kwargs) if m.severity == "error"]

    def _warnings(self, model: ClinicalGraphModel, **kwargs) -> list[ValidationMessage]:
        return [m for m in validate_model(model, **kwargs) if m.severity == "warning"]

    def test_clean_model_has_no_errors(self) -> None:
        model = self._model(
            [_make_node("A"), _make_node("B")],
            [_make_potential("A", data=[0.5, 0.5]), _make_potential("B", parents=["A"], data=[0.7, 0.3, 0.4, 0.6])],
        )
        self.assertEqual(self._errors(model), [])

    def test_reports_duplicate_node_name(self) -> None:
        model = self._model(
            [_make_node("A"), _make_node("A")],
            [_make_potential("A", data=[0.5, 0.5])],
        )
        errors = self._errors(model)
        self.assertTrue(any(e.path == "nodes.A" for e in errors))

    def test_reports_unsupported_node_kind(self) -> None:
        model = self._model(
            [Node(name="Bad", kind="mystery", attributes={"states": ["a"]})],
            [_make_potential("Bad", data=[1.0])],
        )
        errors = self._errors(model)
        self.assertTrue(any(e.path == "nodes.Bad.kind" for e in errors))

    def test_reports_duplicate_state(self) -> None:
        model = self._model(
            [_make_node("A", states=["Yes", "Yes"])],
            [_make_potential("A", data=[0.5, 0.5])],
        )
        errors = self._errors(model)
        self.assertTrue(any(e.path == "nodes.A.states" and "Duplicate" in e.message for e in errors))

    def test_reports_chance_node_without_states(self) -> None:
        model = self._model(
            [_make_node("Empty", states=[])],
            [_make_potential("Empty", data=[])],
        )
        errors = self._errors(model)
        self.assertTrue(any(e.path == "nodes.Empty.states" for e in errors))

    def test_reports_unknown_parent_reference(self) -> None:
        model = self._model(
            [_make_node("A")],
            [_make_potential("A", parents=["Ghost"], data=[0.5, 0.5, 0.5, 0.5])],
        )
        errors = self._errors(model)
        self.assertTrue(any(e.path == "potentials.A.parents" and "Ghost" in e.message for e in errors))

    def test_reports_potential_for_nonexistent_child(self) -> None:
        model = self._model([_make_node("A")], [_make_potential("Ghost", data=[0.5, 0.5])])
        errors = self._errors(model)
        self.assertTrue(any(e.path == "potentials.Ghost" for e in errors))

    def test_reports_bad_table_length(self) -> None:
        model = self._model(
            [_make_node("A", states=["No", "Yes"]), _make_node("B", states=["No", "Yes"])],
            [_make_potential("A", data=[0.5, 0.5]), _make_potential("B", parents=["A"], data=[0.1, 0.9])],
        )
        errors = self._errors(model)
        path_msgs = [e for e in errors if e.path == "potentials.B.data"]
        self.assertTrue(path_msgs)
        self.assertIn("expected 4", path_msgs[0].message)

    def test_reports_bad_probability_row_sums(self) -> None:
        model = self._model(
            [
                _make_node("A", states=["No", "Yes"]),
                _make_node("B", states=["No", "Yes"]),
            ],
            [
                _make_potential("A", data=[0.1, 0.1]),
                _make_potential("B", parents=["A"], data=[0.5, 0.5, 0.4, 0.4]),
            ],
        )
        errors = self._errors(model)
        row_msgs = [e for e in errors if e.path == "potentials.A.data[0]"]
        self.assertTrue(row_msgs)
        self.assertIn("expected 1", row_msgs[0].message)

    def test_reports_chance_node_missing_probability_data(self) -> None:
        model = self._model(
            [_make_node("A")],
            [_make_potential("A", data=None)],
        )
        errors = self._errors(model)
        self.assertTrue(any(e.path == "potentials.A.data" for e in errors))

    def test_reports_utility_table_wrong_width(self) -> None:
        model = self._model(
            [
                _make_node("D", kind="decision", states=["Do", "Wait"]),
                Node(name="U", kind="utility", attributes={}),
            ],
            [_make_potential("U", parents=["D"], data=[1.0, 2.0, 3.0])],
        )
        errors = self._errors(model)
        self.assertTrue(
            any(e.path == "potentials.U.data" and "expected 2" in e.message for e in errors)
        )

    def test_reports_missing_potential_as_warning(self) -> None:
        model = self._model([_make_node("Lonely")], [])
        warnings = self._warnings(model)
        self.assertTrue(any(w.path == "potentials.Lonely" for w in warnings))

    def test_decision_node_without_data_is_allowed(self) -> None:
        model = self._model(
            [
                _make_node("D", kind="decision", states=["Do", "Skip"]),
            ],
            [_make_potential("D", data=None)],
        )
        errors = self._errors(model)
        self.assertFalse(any(e.path.startswith("potentials.D.data") for e in errors))

    def test_target_node_existence_check(self) -> None:
        model = self._model(
            [_make_node("A")],
            [_make_potential("A", data=[0.5, 0.5])],
        )
        errors = self._errors(model, target_node_ids=["A", "MissingDecision"])
        target_msgs = [e for e in errors if e.path == "target_nodes.MissingDecision"]
        self.assertTrue(target_msgs)
        self.assertIn("target", target_msgs[0].message.lower())

    def test_target_node_check_skipped_when_no_targets_supplied(self) -> None:
        model = self._model(
            [_make_node("A")],
            [_make_potential("A", data=[0.5, 0.5])],
        )
        messages = validate_model(model, target_node_ids=None)
        self.assertFalse(any(m.path.startswith("target_nodes.") for m in messages))

    def test_messages_carry_paths_for_endpoint(self) -> None:
        model = self._model(
            [_make_node("A", states=["Yes", "Yes"])],
            [_make_potential("A", data=[0.2, 0.2])],
        )
        messages = validate_model(model)
        self.assertTrue(all(isinstance(m.path, str) and m.path for m in messages))
        self.assertTrue(any(m.path.startswith("nodes.") for m in messages))
        self.assertTrue(any(m.path.startswith("potentials.") for m in messages))


if __name__ == "__main__":
    unittest.main()
