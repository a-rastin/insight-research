from __future__ import annotations

from math import prod
from typing import Any

from .model import ClinicalGraphModel, Node, Potential


def flatten_numbers(value: Any) -> list[float]:
    if isinstance(value, list):
        result: list[float] = []
        for item in value:
            result.extend(flatten_numbers(item))
        return result
    return [float(value)]


def parent_cardinality(model: ClinicalGraphModel, parents: list[str]) -> int:
    node_map = model.node_map()
    return prod((len(node_map[parent].states) for parent in parents), start=1)


def expected_probability_value_count(model: ClinicalGraphModel, child: Node, parents: list[str]) -> int:
    return parent_cardinality(model, parents) * len(child.states)


def probability_rows(model: ClinicalGraphModel, child: Node, parents: list[str], data: Any) -> list[list[float]]:
    flat = flatten_numbers(data)
    expected = expected_probability_value_count(model, child, parents)
    if len(flat) != expected:
        raise ValueError(f"Probability table has {len(flat)} values; expected {expected}")
    width = len(child.states)
    return [flat[index : index + width] for index in range(0, len(flat), width)]


def flat_table_cache(model: ClinicalGraphModel) -> dict[str, list[float]]:
    return {
        potential.child: flatten_numbers(potential.data)
        for potential in model.potentials
        if potential.data is not None
    }


def table_value(
    child_name: str,
    parents: list[str],
    assignment: dict[str, str],
    node_map: dict[str, Node],
    potential_map: dict[str, Potential],
    flat_cache: dict[str, list[float]],
) -> float:
    child = node_map[child_name]
    flat = flat_cache[child_name]
    parent_index = 0
    for parent in parents:
        parent_node = node_map[parent]
        parent_index = parent_index * len(parent_node.states) + parent_node.states.index(assignment[parent])
    if child.kind == "chance":
        return flat[parent_index * len(child.states) + child.states.index(assignment[child_name])]
    return flat[parent_index]
