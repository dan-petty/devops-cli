"""Tests for active marginalia and epistemic scratchpad (devops ai research annotate)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from devops_cli.ai.research.crawler import ForageCrawler
from devops_cli.ai.research.marginalia import (
    annotate_file,
    compute_file_hash,
    get_marginalia_path,
    read_marginalia,
)
from devops_cli.ai.research.models import MarginaliaRecord, MarginaliaType
from devops_cli.config.constants import CONST_MARGINALIA_TYPES
from devops_cli.main import app

runner = CliRunner()


def test_marginalia_type_constants_cover_exact_five_types() -> None:
    expected = ("ASSUMPTION", "HYPOTHESIS", "CONTRADICTION", "QUESTION", "TODO")
    assert CONST_MARGINALIA_TYPES == expected
    assert tuple(t.value for t in MarginaliaType) == expected


def test_compute_file_hash_and_path(tmp_path: Path) -> None:
    digest = compute_file_hash("src/foo.py")
    assert len(digest) == 64
    path = get_marginalia_path("src/foo.py", repo_root=tmp_path)
    assert path.name == f"{digest}.jsonl"


def test_marginalia_record_validation() -> None:
    record = MarginaliaRecord(
        file_path="src/module.py",
        file_hash="abcd1234ef56",
        type="ASSUMPTION",
        content="Assumes network is local",
        anchor="src/module.py",
        created_at="2026-10-11T20:00:00Z",
    )
    assert (record.type, record.anchor, record.content) == (
        "ASSUMPTION",
        "src/module.py",
        "Assumes network is local",
    )


def test_marginalia_record_rejects_invalid_type() -> None:
    with pytest.raises(ValidationError) as raised:
        MarginaliaRecord.model_validate(
            {
                "file_path": "src/module.py",
                "file_hash": "abcd1234ef56",
                "type": "INVALID_TYPE",
                "content": "bad type",
                "anchor": "1-10",
                "created_at": "2026-10-11T20:00:00Z",
            }
        )
    assert len(raised.value.errors()) > 0


def test_annotate_file_and_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    test_file = tmp_path / "foo.py"
    test_file.write_text("def hello(): pass\n", encoding="utf-8")

    rec1 = annotate_file(
        file_path=test_file,
        type="HYPOTHESIS",
        content="May leak file descriptors",
        anchor="hello",
        repo_root=tmp_path,
    )
    assert (rec1.type, rec1.anchor, rec1.content) == (
        "HYPOTHESIS",
        "hello",
        "May leak file descriptors",
    )

    records = read_marginalia(test_file, repo_root=tmp_path)
    assert len(records) == 1
    assert (records[0].type, records[0].content) == ("HYPOTHESIS", "May leak file descriptors")

    # Second annotation survives across sessions
    rec2 = annotate_file(
        file_path=test_file,
        type="TODO",
        content="Add resource cleanup handler",
        anchor="1-2",
        repo_root=tmp_path,
    )
    assert rec2.type == "TODO"

    records_updated = read_marginalia(test_file, repo_root=tmp_path)
    assert len(records_updated) == 2
    assert (records_updated[0].content, records_updated[1].content) == (
        "May leak file descriptors",
        "Add resource cleanup handler",
    )


def test_cli_research_annotate_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    target = tmp_path / "bar.py"
    target.write_text("x = 42\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "ai",
            "research",
            "annotate",
            str(target),
            "--type",
            "QUESTION",
            "--content",
            "Is 42 dynamically recomputed?",
            "--anchor",
            "1",
        ],
    )
    assert result.exit_code == 0
    assert "QUESTION" in result.output
    assert "Is 42 dynamically recomputed?" in result.output

    # Listing mode with --list and --format json
    list_res = runner.invoke(
        app,
        ["ai", "research", "annotate", str(target), "--list", "--format", "json"],
    )
    assert list_res.exit_code == 0
    parsed = json.loads(list_res.output)
    assert len(parsed) == 1
    assert (parsed[0]["type"], parsed[0]["content"], parsed[0]["anchor"]) == (
        "QUESTION",
        "Is 42 dynamically recomputed?",
        "1",
    )

    # Second invocation without --content appends a record and output includes both
    second_res = runner.invoke(
        app,
        ["ai", "research", "annotate", str(target), "--format", "json"],
    )
    assert second_res.exit_code == 0
    parsed_updated = json.loads(second_res.output)
    assert len(parsed_updated) == 2
    assert parsed_updated[0]["type"] == "QUESTION"
    assert parsed_updated[1]["type"] == "TODO"


def test_forage_surfaces_prior_marginalia(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    main_py = tmp_path / "app.py"
    main_py.write_text("import helper\n", encoding="utf-8")
    helper_py = tmp_path / "helper.py"
    helper_py.write_text("val = 100\n", encoding="utf-8")

    # Annotate helper.py before foraging
    annotate_file(
        file_path="helper.py",
        type="CONTRADICTION",
        content="Hardcoded constant conflicts with settings",
        anchor="helper.py",
        repo_root=tmp_path,
    )

    crawler = ForageCrawler(repo_root=tmp_path, max_nodes=5)
    trail = crawler.forage(anchor="app.py", query="constant settings")

    # Verify that helper.py has marginalia attached
    helper_nodes = [n for n in trail.visited_nodes if n.path == "helper.py"]
    assert len(helper_nodes) == 1
    assert len(helper_nodes[0].marginalia) == 1
    assert helper_nodes[0].marginalia[0].type == "CONTRADICTION"
    assert "Hardcoded constant conflicts" in helper_nodes[0].marginalia[0].content
