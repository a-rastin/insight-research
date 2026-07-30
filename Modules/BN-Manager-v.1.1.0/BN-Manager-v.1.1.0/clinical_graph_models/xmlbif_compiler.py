from __future__ import annotations

from dataclasses import asdict
from math import prod
from pathlib import Path
from typing import Iterable

from lxml import etree

from .model import ClinicalGraphModel, Node, Potential, ValidationMessage


class XmlBifCompileError(Exception):
    def __init__(self, message: str, messages: Iterable[ValidationMessage]) -> None:
        super().__init__(message)
        self.messages = list(messages)

    def details(self) -> dict[str, list[dict[str, str]]]:
        return {"messages": [asdict(message) for message in self.messages]}


def compile_xmlbif(
    text: str,
    schema_text: str | None = None,
    schema_path: str | Path | None = None,
) -> ClinicalGraphModel:
    """Compile one schema-valid BIF 0.3 XML network into the internal model.

    The supplied INSIGHT networks use a compact one-row TABLE for neutral,
    uncalibrated conditional distributions. When a conditional table contains
    exactly one child-state row, that row is broadcast over every parent-state
    combination. Full conditional tables are preserved unchanged.
    """
    root = _parse_xml_document(text)
    if schema_text is not None or schema_path is not None:
        _validate_xsd(root, schema_text, schema_path)

    if root.tag != "BIF":
        raise XmlBifCompileError(
            "BN XML root element is invalid.",
            [ValidationMessage("error", "/", "Expected BIF root element")],
        )

    network = _single(root, "NETWORK", "/BIF/NETWORK")
    name = _text(_single(network, "NAME", "/BIF/NETWORK/NAME"))
    attributes: dict[str, object] = {
        "name": name,
        "xml_version": root.get("VERSION"),
    }

    nodes = [_compile_variable(variable, index) for index, variable in enumerate(network.findall("VARIABLE"))]
    node_map = {node.name: node for node in nodes}
    potentials = [
        _compile_definition(definition, index, node_map)
        for index, definition in enumerate(network.findall("DEFINITION"))
    ]
    return ClinicalGraphModel(attributes=attributes, nodes=nodes, potentials=potentials)


def _parse_xml_document(text: str) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True)
    try:
        return etree.fromstring(text.encode("utf-8"), parser=parser)
    except etree.XMLSyntaxError as exc:
        messages = [
            ValidationMessage(
                "error",
                f"line:{entry.line}:column:{entry.column}",
                entry.message,
            )
            for entry in exc.error_log
        ] or [ValidationMessage("error", "/", str(exc))]
        raise XmlBifCompileError("BN XML parsing failed.", messages) from exc


def _validate_xsd(
    root: etree._Element,
    schema_text: str | None,
    schema_path: str | Path | None,
) -> None:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True)
    try:
        schema_root = (
            etree.fromstring(schema_text.encode("utf-8"), parser=parser)
            if schema_text is not None
            else etree.parse(str(schema_path), parser=parser).getroot()
        )
        schema = etree.XMLSchema(schema_root)
    except (OSError, etree.XMLSchemaParseError, etree.XMLSyntaxError) as exc:
        raise XmlBifCompileError(
            "BN XML XSD loading failed.",
            [ValidationMessage("error", "schema", str(exc))],
        ) from exc

    if schema.validate(root):
        return

    messages = [
        ValidationMessage(
            "error",
            f"line:{entry.line}:column:{entry.column}",
            entry.message,
        )
        for entry in schema.error_log
    ] or [ValidationMessage("error", "/", "BN XML document failed XSD validation.")]
    raise XmlBifCompileError("BN XML XSD validation failed.", messages)


def _compile_variable(variable: etree._Element, index: int) -> Node:
    name = _text(_single(variable, "NAME", f"/BIF/NETWORK/VARIABLE[{index}]/NAME"))
    kind = _node_kind(variable.get("TYPE"), name)
    properties = _properties(variable.findall("PROPERTY"))
    if "label" not in properties:
        properties["label"] = name
    properties["states"] = [_text(outcome) for outcome in variable.findall("OUTCOME")]
    properties["xml_type"] = variable.get("TYPE")
    return Node(name=name, kind=kind, attributes=properties)


def _compile_definition(
    definition: etree._Element,
    index: int,
    node_map: dict[str, Node],
) -> Potential:
    path = f"/BIF/NETWORK/DEFINITION[{index}]"
    child = _text(_single(definition, "FOR", f"{path}/FOR"))
    parents = [_text(given) for given in definition.findall("GIVEN")]
    table = _single(definition, "TABLE", f"{path}/TABLE")
    data = _parse_table(_text(table), f"{path}/TABLE")
    attributes: dict[str, object] = {"data": data}

    child_node = node_map.get(child)
    parent_nodes = [node_map.get(parent) for parent in parents]
    if (
        child_node is not None
        and parents
        and all(parent_node is not None for parent_node in parent_nodes)
        and len(data) == len(child_node.states)
    ):
        combinations = prod(len(parent_node.states) for parent_node in parent_nodes if parent_node)
        attributes["data"] = data * combinations
        attributes["table_broadcast"] = True
        attributes["source_table_value_count"] = len(data)

    return Potential(child=child, parents=parents, attributes=attributes)


def _node_kind(xml_type: str | None, node_name: str) -> str:
    if xml_type == "nature":
        return "chance"
    raise XmlBifCompileError(
        "BN XML variable type is unsupported.",
        [
            ValidationMessage(
                "error",
                f"variables.{node_name}.TYPE",
                f"Unsupported VARIABLE TYPE {xml_type!r}; expected 'nature'",
            )
        ],
    )


def _parse_table(text: str, path: str) -> list[float]:
    values: list[float] = []
    for token in text.split():
        try:
            values.append(float(token))
        except ValueError as exc:
            raise XmlBifCompileError(
                "BN XML TABLE contains a non-numeric value.",
                [ValidationMessage("error", path, f"Invalid TABLE value {token!r}")],
            ) from exc
    return values


def _properties(elements: Iterable[etree._Element]) -> dict[str, object]:
    properties: dict[str, object] = {}
    extras: list[str] = []
    for element in elements:
        raw = _text(element)
        if "=" not in raw:
            extras.append(raw)
            continue
        key, value = raw.split("=", 1)
        properties[key.strip()] = value.strip()
    if extras:
        properties["properties"] = extras
    return properties


def _single(parent: etree._Element, tag: str, path: str) -> etree._Element:
    matches = parent.findall(tag)
    if len(matches) != 1:
        raise XmlBifCompileError(
            "BN XML element count is invalid.",
            [ValidationMessage("error", path, f"Expected one {tag} element; found {len(matches)}")],
        )
    return matches[0]


def _text(element: etree._Element) -> str:
    return "".join(element.itertext()).strip()
