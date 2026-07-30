from __future__ import annotations

from typing import Any, Iterable

from .model import ClinicalGraphModel, Node, Potential, ValidationMessage
from .tables import flatten_numbers, parent_cardinality, probability_rows

SUPPORTED_KINDS: frozenset[str] = frozenset({"chance", "decision", "utility"})


def validate_model(
    model: ClinicalGraphModel,
    *,
    target_node_ids: Iterable[str] | None = None,
) -> list[ValidationMessage]:
    """Return semantic BN validation errors/warnings for a Clinical Graph Model.

    Each message carries a dotted ``path`` rooted at ``nodes.<name>`` or
    ``potentials.<child>`` so callers can point at the offending element. The
    optional ``target_node_ids`` lets the API boundary pass the frozen contract
    target nodes so the validator can confirm the model declares them.
    """
    messages: list[ValidationMessage] = []
    node_map = model.node_map()

    _check_duplicate_node_names(model, messages)
    _check_node_kinds_and_states(model, messages)
    _check_potentials(model, node_map, messages)
    _check_missing_potentials(model, messages)
    if target_node_ids is not None:
        _check_target_nodes(model, node_map, target_node_ids, messages)
    return messages


def _check_duplicate_node_names(
    model: ClinicalGraphModel,
    messages: list[ValidationMessage],
) -> None:
    node_map = model.node_map()
    if len(node_map) == len(model.nodes):
        return
    seen: set[str] = set()
    for node in model.nodes:
        if node.name in seen:
            messages.append(ValidationMessage("error", f"nodes.{node.name}", "Duplicate node name"))
        seen.add(node.name)


def _check_node_kinds_and_states(
    model: ClinicalGraphModel,
    messages: list[ValidationMessage],
) -> None:
    for node in model.nodes:
        if node.kind not in SUPPORTED_KINDS:
            messages.append(
                ValidationMessage(
                    "error",
                    f"nodes.{node.name}.kind",
                    f"Unsupported node kind {node.kind!r}; expected one of {sorted(SUPPORTED_KINDS)}",
                )
            )
            continue
        if node.kind in {"chance", "decision"} and not node.states:
            messages.append(ValidationMessage("error", f"nodes.{node.name}.states", "Node needs states"))
            continue
        if node.kind in {"chance", "decision"}:
            state_seen: set[str] = set()
            for state in node.states:
                if state in state_seen:
                    messages.append(
                        ValidationMessage(
                            "error",
                            f"nodes.{node.name}.states",
                            f"Duplicate state {state!r}",
                        )
                    )
                state_seen.add(state)


def _check_potentials(
    model: ClinicalGraphModel,
    node_map: dict[str, Node],
    messages: list[ValidationMessage],
) -> None:
    for potential in model.potentials:
        _check_potential_target(model, node_map, potential, messages)


def _check_potential_target(
    model: ClinicalGraphModel,
    node_map: dict[str, Node],
    potential: Potential,
    messages: list[ValidationMessage],
) -> None:
    child = node_map.get(potential.child)
    if child is None:
        messages.append(
            ValidationMessage("error", f"potentials.{potential.child}", "Potential child is not a node")
        )
        return
    has_unknown_parent = False
    for parent in potential.parents:
        if parent not in node_map:
            has_unknown_parent = True
            messages.append(
                ValidationMessage(
                    "error",
                    f"potentials.{potential.child}.parents",
                    f"Unknown parent {parent}",
                )
            )
    if has_unknown_parent:
        return

    if child.kind == "decision" and potential.data is None:
        return
    if child.kind == "utility":
        _validate_utility_table(messages, model, child, potential.parents, potential.data)
    elif child.kind == "chance":
        _validate_probability_table(messages, model, child, potential.parents, potential.data)
    else:
        # Unsupported kinds are already reported by `_check_node_kinds_and_states`.
        return


def _check_missing_potentials(
    model: ClinicalGraphModel,
    messages: list[ValidationMessage],
) -> None:
    potential_children = {potential.child for potential in model.potentials}
    for node in model.nodes:
        if node.kind != "decision" and node.name not in potential_children:
            messages.append(
                ValidationMessage("warning", f"potentials.{node.name}", "Node has no potential")
            )


def _check_target_nodes(
    model: ClinicalGraphModel,
    node_map: dict[str, Node],
    target_node_ids: Iterable[str],
    messages: list[ValidationMessage],
) -> None:
    declared = set(node_map)
    seen_targets: set[str] = set()
    for target in target_node_ids:
        if target in seen_targets:
            continue
        seen_targets.add(target)
        if target not in declared:
            messages.append(
                ValidationMessage(
                    "error",
                    f"target_nodes.{target}",
                    "Target node is declared by the BN Manager contract but is missing from the model",
                )
            )


def _validate_probability_table(
    messages: list[ValidationMessage],
    model: ClinicalGraphModel,
    child: Node,
    parents: list[str],
    data: Any,
) -> None:
    if data is None:
        messages.append(
            ValidationMessage("error", f"potentials.{child.name}.data", "Chance node needs probability data")
        )
        return
    expected_width = len(child.states)
    expected_rows = parent_cardinality(model, parents) if parents else 1
    expected_values = expected_width * expected_rows if expected_width else 0
    flat = flatten_numbers(data)
    if expected_values and len(flat) != expected_values:
        messages.append(
            ValidationMessage(
                "error",
                f"potentials.{child.name}.data",
                (
                    f"Probability table has {len(flat)} values; "
                    f"expected {expected_values} ({expected_rows} rows x {expected_width} states)"
                ),
            )
        )
        return
    try:
        rows = probability_rows(model, child, parents, data)
    except ValueError as exc:
        messages.append(
            ValidationMessage("error", f"potentials.{child.name}.data", str(exc))
        )
        return
    for row_number, row in enumerate(rows):
        if abs(sum(row) - 1.0) > 1e-6:
            messages.append(
                ValidationMessage(
                    "error",
                    f"potentials.{child.name}.data[{row_number}]",
                    f"Probability row sums to {sum(row):.6g}, expected 1",
                )
            )


def _validate_utility_table(
    messages: list[ValidationMessage],
    model: ClinicalGraphModel,
    child: Node,
    parents: list[str],
    data: Any,
) -> None:
    if data is None:
        messages.append(
            ValidationMessage("error", f"potentials.{child.name}.data", "Utility node needs utility data")
        )
        return
    flat = flatten_numbers(data)
    expected = parent_cardinality(model, parents)
    if len(flat) != expected:
        messages.append(
            ValidationMessage(
                "error",
                f"potentials.{child.name}.data",
                f"Utility table has {len(flat)} values; expected {expected}",
            )
        )
