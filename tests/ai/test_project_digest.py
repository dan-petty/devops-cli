"""Tests for project digest generation from code at run time (#3904)."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic_core import PydanticUndefined

from devops_cli.ai.project_digest import (
    architecture_facts,
    build_project_digest,
    command_facts,
    decision_facts,
    head_commit,
    pin_facts,
    settings_sections,
)
from devops_cli.ai.repomap import generate_repo_map
from devops_cli.ai.tools.builtin_tools import project_digest
from devops_cli.core.import_graph import build_import_graph
from devops_cli.docs.adr_records import read_record_texts
from devops_cli.docs.generator import DocGenerator, iter_settings_fields
from devops_cli.roadmap.adr import adr_of
from tests.support.paths import REPO_ROOT


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
    # A temporary root holding pyproject.toml and uv.lock
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "my-project"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    uv_lock_text = """version = 1
revision = 1
requires-python = ">=3.14"

[[package]]
name = "aiofile"
version = "3.12.3"
"""
    (tmp_path / "uv.lock").write_text(uv_lock_text, encoding="utf-8")

    facts = pin_facts(tmp_path)
    aio_facts = [f for f in facts if f["name"] == "aiofile"]
    assert len(aio_facts) == 1
    assert aio_facts[0]["version"] == "3.12.3"
    assert aio_facts[0]["file"] == "uv.lock"

    # Asserts that a temporary root with a changed uv.lock gives the changed version
    changed_uv = uv_lock_text.replace("3.12.3", "99.99.99")
    (tmp_path / "uv.lock").write_text(changed_uv, encoding="utf-8")

    tmp_facts = pin_facts(tmp_path)
    aio_facts = [f for f in tmp_facts if f["name"] == "aiofile"]
    assert len(aio_facts) == 1
    assert aio_facts[0]["version"] == "99.99.99"
    assert aio_facts[0]["file"] == "uv.lock"


def test_the_digest_lists_each_module_each_import_edge_and_each_decision_record() -> None:
    arch = architecture_facts(REPO_ROOT)

    # Asserts that the module paths of architecture_facts equal the paths of generate_repo_map
    src_py_count = len(list((REPO_ROOT / "src").rglob("*.py")))
    expected_nodes = generate_repo_map(REPO_ROOT, max_files=src_py_count)
    assert [m["path"] for m in arch["modules"]] == [n.path for n in expected_nodes]

    # Asserts that each edge names two modules of build_import_graph
    trees: dict[Path, ast.Module] = {}
    for p in sorted((REPO_ROOT / "src").rglob("*.py")):
        trees[p] = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    graph = build_import_graph(trees, root=REPO_ROOT)
    all_expected_edges = {(src, dst) for src, targets in graph.edges.items() for dst in targets}
    actual_edges = {(e["source"], e["target"]) for e in arch["edges"]}
    assert actual_edges == all_expected_edges

    # Asserts that each record of docs/adr appears in decision_facts with its title and its status
    decisions = decision_facts(REPO_ROOT / "docs" / "adr")
    records = read_record_texts(REPO_ROOT / "docs" / "adr")
    assert len(decisions) == len(records)
    decision_map = {d["path"]: d for d in decisions}
    for path, text in records.items():
        assert path in decision_map
        adr = adr_of(path, text)
        assert adr is not None
        assert decision_map[path]["title"] == adr.title
        expected_status = (
            adr.front_matter.status.value
            if adr.front_matter.status is not None and hasattr(adr.front_matter.status, "value")
            else str(adr.front_matter.status)
            if adr.front_matter.status is not None
            else ""
        )
        assert decision_map[path]["status"] == expected_status


def test_the_digest_hashes_its_sections_and_names_the_commit_it_was_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commit_sha = "0123456789abcdef0123456789abcdef01234567"
    digest1 = build_project_digest(REPO_ROOT, commit=commit_sha)
    digest2 = build_project_digest(REPO_ROOT, commit=commit_sha)

    # Asserts that two builds of one section map give one hash
    assert digest1.content_hash == digest2.content_hash
    assert digest1.commit == commit_sha
    assert len(digest1.content_hash) == 64

    # Asserts that a changed section gives another hash
    changed_sections = dict(digest1.model_dump())
    changed_sections["commands"] = []
    raw = json.dumps(
        {
            k: changed_sections[k]
            for k in ["commands", "settings", "pins", "architecture", "decisions"]
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    changed_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert changed_hash != digest1.content_hash

    # Asserts that a temporary root with a changed uv.lock gives another hash again
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "my-project"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (tmp_path / "uv.lock").write_text(
        'version = 1\n[[package]]\nname = "aiofile"\nversion = "3.12.3"\n', encoding="utf-8"
    )
    digest_tmp_orig = build_project_digest(tmp_path, commit=commit_sha)

    (tmp_path / "uv.lock").write_text(
        'version = 1\n[[package]]\nname = "aiofile"\nversion = "99.99.99"\n', encoding="utf-8"
    )
    digest_tmp_changed = build_project_digest(tmp_path, commit=commit_sha)

    assert digest_tmp_orig.content_hash != digest_tmp_changed.content_hash
    assert digest_tmp_changed.content_hash != digest1.content_hash

    # Asserts that head_commit returns the SHA that the doubled run_subprocess call answers
    expected_sha = "fedcba9876543210fedcba9876543210fedcba98"

    def fake_run_subprocess(cmd: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert list(cmd) == ["git", "rev-parse", "HEAD"]
        return subprocess.CompletedProcess(cmd, 0, stdout=f"{expected_sha}\n", stderr="")

    monkeypatch.setattr("devops_cli.ai.project_digest.run_subprocess", fake_run_subprocess)
    assert head_commit(REPO_ROOT) == expected_sha


def test_the_project_digest_tool_and_the_index_section_name_the_same_sections() -> None:
    res = project_digest()
    assert isinstance(res, dict)
    assert "content_hash" in res
    assert "commit" in res
    assert len(res["content_hash"]) == 64

    tool_sections = [k for k in res if k not in ("content_hash", "commit")]
    expected_sections = ["commands", "settings", "pins", "architecture", "decisions"]
    assert set(tool_sections) == set(expected_sections)

    generator = DocGenerator()
    kb_index = generator.generate_knowledge_base_index()
    assert "## Project Digest" in kb_index
    for section_name in tool_sections:
        assert f"`{section_name}`" in kb_index
