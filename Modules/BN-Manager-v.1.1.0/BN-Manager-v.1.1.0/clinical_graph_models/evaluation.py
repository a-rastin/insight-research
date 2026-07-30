from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .model import ClinicalGraphModel
from .tables import flat_table_cache, table_value

Evidence = dict[str, str | dict[str, float]]


@dataclass(slots=True)
class EvaluationResult:
    target: str
    values: dict[str, float]


def evaluate_posterior(
    model: ClinicalGraphModel,
    target: str,
    evidence: Evidence | None = None,
) -> EvaluationResult:
    evidence = evidence or {}
    node_map = model.node_map()
    if target not in node_map:
        raise KeyError(f"Unknown target node: {target}")
    target_node = node_map[target]
    if target_node.kind != "chance":
        raise ValueError("Posterior target must be a chance node")

    totals = {state: 0.0 for state in target_node.states}
    normalizer = 0.0
    for assignment, probability in _enumerate_chance_assignments(model):
        weight = probability * _evidence_weight(assignment, evidence)
        if weight == 0:
            continue
        totals[assignment[target]] += weight
        normalizer += weight

    values = {state: (value / normalizer if normalizer else 0.0) for state, value in totals.items()}
    return EvaluationResult(target=target, values=values)


def evaluate_expected_utilities(
    model: ClinicalGraphModel,
    decision: str,
    evidence: Evidence | None = None,
) -> EvaluationResult:
    evidence = evidence or {}
    node_map = model.node_map()
    if decision not in node_map:
        raise KeyError(f"Unknown decision node: {decision}")
    decision_node = node_map[decision]
    if decision_node.kind != "decision":
        raise ValueError("Expected utility target must be a decision node")

    utility_potentials = [p for p in model.potentials if node_map[p.child].kind == "utility"]
    potential_map = model.potential_map()
    flat_cache = flat_table_cache(model)
    chance_assignments = _enumerate_chance_assignments(model)
    values = {state: 0.0 for state in decision_node.states}
    normalizers = {state: 0.0 for state in decision_node.states}

    for option in decision_node.states:
        for assignment, probability in chance_assignments:
            weight = probability * _evidence_weight(assignment, evidence)
            if weight == 0:
                continue
            enriched = {**assignment, decision: option}
            utility = sum(
                table_value(p.child, p.parents, enriched, node_map, potential_map, flat_cache)
                for p in utility_potentials
            )
            values[option] += weight * utility
            normalizers[option] += weight

    values = {state: (value / normalizers[state] if normalizers[state] else 0.0) for state, value in values.items()}
    return EvaluationResult(target=decision, values=values)


def _enumerate_chance_assignments(model: ClinicalGraphModel) -> list[tuple[dict[str, str], float]]:
    chance_nodes = [node for node in model.nodes if node.kind == "chance"]
    node_map = model.node_map()
    potential_map = model.potential_map()
    flat_cache = flat_table_cache(model)
    rows: list[tuple[dict[str, str], float]] = []
    for states in product(*[node.states for node in chance_nodes]):
        assignment = dict(zip([node.name for node in chance_nodes], states, strict=True))
        probability = 1.0
        for node in chance_nodes:
            potential = potential_map.get(node.name)
            if potential is None:
                probability = 0.0
                break
            probability *= table_value(node.name, potential.parents, assignment, node_map, potential_map, flat_cache)
        rows.append((assignment, probability))
    return rows


def _evidence_weight(assignment: dict[str, str], evidence: Evidence) -> float:
    weight = 1.0
    for node_name, observed in evidence.items():
        if node_name not in assignment:
            continue
        actual = assignment[node_name]
        if isinstance(observed, dict):
            weight *= float(observed.get(actual, 0.0))
        elif observed != actual:
            return 0.0
    return weight
