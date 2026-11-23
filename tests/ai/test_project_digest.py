"""Tests for project digest generation from code at run time (#3904)."""

from __future__ import annotations

import ast
import shutil
import tomllib
from pathlib import Path

from pydantic_core import PydanticUndefined

from devops_cli.ai.project_digest import (
    architecture_facts,
    command_facts,
    decision_facts,
    pin_facts,
    settings_sections,
)
from devops_cli.ai.repomap import generate_repo_map
from devops_cli.core.import_graph import build_import_graph
from devops_cli.docs.adr_records import read_record_texts
from devops_cli.docs.generator import DocGenerator, iter_settings_fields
from devops_cli.roadmap.adr import adr_of


def test_command_facts_lists_each_registered_command_and_no_absent_one() -> None:
    generator = DocGenerator()
    groups = generator.introspect_all_groups()
    facts = command_facts(groups)

    # Asserts that command_facts holds each group and command of DocGenerator.introspect_all_groups
    command_keys = {(f["group"], f["command"]) for f in facts}
    for g in groups:
        assert g.name in {f["group"] for f in facts}
        for cmd in g.commands:
            assert (g.name, cmd.name) in command_keys
            matching = [f for f in facts if f["group"] == g.name and f["command"] == cmd.name]
            assert len(matching) >= 1
            expected_help = cmd.description or cmd.summary or ""
            assert matching[0]["help"] == expected_help

    # Asserts that a command name that no module registers is absent
    assert ("roadmap", "nonexistent_command_xyz") not in command_keys
    assert ("nonexistent_group_xyz", "some_cmd") not in command_keys

    # Asserts that settings_sections holds each section and field of Settings
    sections = settings_sections()
    assert isinstance(sections, dict)

    for sec_key, sec_model, field_name, field_info in iter_settings_fields():
        assert sec_key in sections
        field_entries = sections[sec_key]
        dotted_name = field_name if sec_model is None else f"{sec_key}.{field_name}"
        matching = [f for f in field_entries if f["name"] == dotted_name]
        assert len(matching) == 1
        entry = matching[0]

        # Asserts default or default-factory name
        if field_info.default_factory is not None:
            factory_name = getattr(
                field_info.default_factory, "__name__", str(field_info.default_factory)
            )
            assert entry["default"] == factory_name
        elif field_info.default is not PydanticUndefined:
            val = field_info.default
            expected = val if isinstance(val, (int, float, bool, str)) or val is None else str(val)
            assert entry["default"] == expected
        else:
            assert entry["default"] is None


def test_each_pin_equals_its_lock_and_a_changed_lock_changes_the_pin_section(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).parents[2]
    facts = pin_facts(repo_root)

    # Asserts that each pin of pin_facts equals the version of the same name in uv.lock
    uv_lock_text = (repo_root / "uv.lock").read_text(encoding="utf-8")
    uv_lock_data = tomllib.loads(uv_lock_text)
    lock_packages = {
        pkg["name"]: pkg["version"] for pkg in uv_lock_data.get("package", []) if "version" in pkg
    }

    uv_facts = [f for f in facts if f["file"] == "uv.lock"]
    assert len(uv_facts) > 0
    for f in uv_facts:
        assert f["name"] in lock_packages
        assert f["version"] == lock_packages[f["name"]]

    # Asserts that a temporary root holding copies of pyproject.toml and uv.lock with one version changed
    # gives that version with uv.lock as its file
    shutil.copy(repo_root / "pyproject.toml", tmp_path / "pyproject.toml")
    changed_uv = uv_lock_text.replace(
        'name = "aiofile"\nversion = "3.12.3"',
        'name = "aiofile"\nversion = "99.99.99"',
    )
    (tmp_path / "uv.lock").write_text(changed_uv, encoding="utf-8")

    tmp_facts = pin_facts(tmp_path)
    aio_facts = [f for f in tmp_facts if f["name"] == "aiofile"]
    assert len(aio_facts) == 1
    assert aio_facts[0]["version"] == "99.99.99"
    assert aio_facts[0]["file"] == "uv.lock"


def test_the_digest_lists_each_module_each_import_edge_and_each_decision_record() -> None:
    repo_root = Path(__file__).parents[2]
    arch = architecture_facts(repo_root)

    # Asserts that the module paths of architecture_facts equal the paths of generate_repo_map
    src_py_count = len(list((repo_root / "src").rglob("*.py")))
    expected_nodes = generate_repo_map(repo_root, max_files=src_py_count)
    assert [m["path"] for m in arch["modules"]] == [n.path for n in expected_nodes]

    # Asserts that each edge names two modules of build_import_graph
    trees: dict[Path, ast.Module] = {}
    for p in sorted((repo_root / "src").rglob("*.py")):
        trees[p] = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    graph = build_import_graph(trees, root=repo_root)
    all_expected_edges = {(src, dst) for src, targets in graph.edges.items() for dst in targets}
    actual_edges = {(e["source"], e["target"]) for e in arch["edges"]}
    assert actual_edges == all_expected_edges

    # Asserts that each record of docs/adr appears in decision_facts with its title and its status
    decisions = decision_facts(repo_root / "docs" / "adr")
    records = read_record_texts(repo_root / "docs" / "adr")
    assert len(decisions) == len(records)
    decision_map = {d["path"]: d for d in decisions}
    for path, text in records.items():
        assert path in decision_map
        adr = adr_of(path, text)
        assert adr is not None
        assert decision_map[path]["title"] == adr.title
        expected_status = (
            adr.front_matter.status.value
            if hasattr(adr.front_matter.status, "value")
            else str(adr.front_matter.status)
        )
        assert decision_map[path]["status"] == expected_status
