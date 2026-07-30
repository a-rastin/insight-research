from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

NodeKind = Literal["chance", "decision", "utility"]
Severity = Literal["error", "warning"]


@dataclass(slots=True)
class Node:
    name: str
    kind: NodeKind
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        value = self.attributes.get("label")
        return str(value) if value is not None else self.name

    @property
    def states(self) -> list[str]:
        value = self.attributes.get("states", [])
        return [str(item) for item in value] if isinstance(value, list) else []

    @property
    def position(self) -> tuple[float, float]:
        value = self.attributes.get("position")
        if isinstance(value, list) and len(value) >= 2:
            return (float(value[0]), float(value[1]))
        return (0.0, 0.0)


@dataclass(slots=True)
class Potential:
    child: str
    parents: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def data(self) -> Any:
        return self.attributes.get("data")


@dataclass(slots=True)
class ClinicalGraphModel:
    attributes: dict[str, Any] = field(default_factory=dict)
    nodes: list[Node] = field(default_factory=list)
    potentials: list[Potential] = field(default_factory=list)

    def node_map(self) -> dict[str, Node]:
        return {node.name: node for node in self.nodes}

    def potential_map(self) -> dict[str, Potential]:
        return {potential.child: potential for potential in self.potentials}

    @property
    def name(self) -> str:
        value = self.attributes.get("name")
        return str(value) if value is not None else "Clinical Graph Model"


@dataclass(slots=True)
class ValidationMessage:
    severity: Severity
    path: str
    message: str
