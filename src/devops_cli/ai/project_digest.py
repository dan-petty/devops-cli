"""Project digest generator from code at run time (#3904)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from devops_cli.docs.generator import CommandDoc, CommandGroupDoc, iter_settings_fields


def _format_annotation(annotation: Any) -> str:
    """Format type annotation string without pathlib prefix."""
    if annotation is None:
        return ""
    name = getattr(annotation, "__name__", str(annotation))
    return name.replace("pathlib.", "")


def _field_default(field_info: FieldInfo) -> Any:
    """Extract default value or factory name from FieldInfo."""
    if field_info.default_factory is not None:
        return getattr(field_info.default_factory, "__name__", str(field_info.default_factory))
    if field_info.default is not PydanticUndefined:
        val = field_info.default
        if isinstance(val, (int, float, bool, str)) or val is None:
            return val
        return str(val)
    return None


def command_facts(groups: Sequence[CommandGroupDoc]) -> list[dict[str, str]]:
    """Turn introspected command groups into a flat list of command facts."""
    facts: list[dict[str, str]] = []
    for g in groups:

        def _collect(cmd: CommandDoc, prefix: str, group_name: str = g.name) -> None:
            cmd_name = f"{prefix} {cmd.name}".strip() if prefix else cmd.name
            help_text = cmd.description or cmd.summary or ""
            facts.append(
                {
                    "group": group_name,
                    "command": cmd_name,
                    "help": help_text,
                }
            )
            for sub in cmd.subcommands:
                _collect(sub, cmd_name, group_name)

        for cmd in g.commands:
            _collect(cmd, "")
    return facts


def settings_sections() -> dict[str, list[dict[str, Any]]]:
    """Project settings fields into each section without resolving live values."""
    sections: dict[str, list[dict[str, Any]]] = {}
    for sec_key, sec_model, field_name, field_info in iter_settings_fields():
        if sec_key not in sections:
            sections[sec_key] = []
        dotted_name = field_name if sec_model is None else f"{sec_key}.{field_name}"
        sections[sec_key].append(
            {
                "name": dotted_name,
                "annotation": _format_annotation(field_info.annotation),
                "default": _field_default(field_info),
            }
        )
    return sections
