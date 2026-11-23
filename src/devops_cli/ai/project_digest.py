"""Project digest generator from code at run time (#3904)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from devops_cli.core.process import run_subprocess
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


def pin_facts(root: Path) -> list[dict[str, str]]:
    """Return an entry for each pinned component with its name, version and file."""
    from devops_cli.research.inventory import read_inventory

    inventory = read_inventory(root)
    return [
        {
            "name": c.name,
            "version": c.version,
            "file": c.file,
        }
        for c in inventory.components
    ]


def architecture_facts(root: Path) -> dict[str, Any]:
    """Return repository map module paths with symbol counts and import graph edges."""
    import ast

    from devops_cli.ai.repomap import generate_repo_map
    from devops_cli.core.import_graph import build_import_graph

    src_dir = root / "src"
    py_files = sorted(src_dir.rglob("*.py"))
    trees: dict[Path, ast.Module] = {}
    for p in py_files:
        try:
            trees[p] = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except Exception:
            pass

    nodes = generate_repo_map(root, max_files=len(py_files))
    graph = build_import_graph(trees, root=root)

    return {
        "modules": [{"path": node.path, "symbols": len(node.symbols)} for node in nodes],
        "edges": [
            {"source": src, "target": dst}
            for src, targets in sorted(graph.edges.items())
            for dst in sorted(targets)
        ],
    }


def decision_facts(directory: Path) -> list[dict[str, str]]:
    """Return an entry for each ADR record with its path, title and status."""
    from devops_cli.docs.adr_records import read_record_texts
    from devops_cli.roadmap.adr import adr_of

    records = read_record_texts(directory)
    facts: list[dict[str, str]] = []
    for path, text in sorted(records.items()):
        adr = adr_of(path, text)
        if adr is not None:
            status = (
                adr.front_matter.status.value
                if hasattr(adr.front_matter.status, "value")
                else str(adr.front_matter.status)
            )
            facts.append(
                {
                    "path": path,
                    "title": adr.title,
                    "status": status,
                }
            )
    return facts


class ProjectDigest(BaseModel):
    """Run-time digest of project facts read from their owners."""

    commands: list[dict[str, str]] = Field(default_factory=list)
    settings: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    pins: list[dict[str, str]] = Field(default_factory=list)
    architecture: dict[str, Any] = Field(default_factory=dict)
    decisions: list[dict[str, str]] = Field(default_factory=list)
    content_hash: str = ""
    commit: str = ""


def build_project_digest(root: Path, commit: str) -> ProjectDigest:
    """Build the project digest from the repository at root with the given commit."""
    from devops_cli.docs.generator import DocGenerator

    generator = DocGenerator()
    cmd_groups = generator.introspect_all_groups()
    commands = command_facts(cmd_groups)
    settings = settings_sections()
    pins = pin_facts(root)
    architecture = architecture_facts(root)
    adr_dir = root / "docs" / "adr"
    decisions = decision_facts(adr_dir) if adr_dir.exists() else []

    sections = {
        "commands": commands,
        "settings": settings,
        "pins": pins,
        "architecture": architecture,
        "decisions": decisions,
    }
    raw = json.dumps(sections, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    return ProjectDigest(
        commands=commands,
        settings=settings,
        pins=pins,
        architecture=architecture,
        decisions=decisions,
        content_hash=content_hash,
        commit=commit,
    )


def head_commit(root: Path) -> str:
    """Return the commit SHA of HEAD for the repository at root."""
    res = run_subprocess(["git", "rev-parse", "HEAD"], cwd=root, local_read=True)
    return res.stdout.strip()
