"""Tests for AST repository map generator and devops ai repomap CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.repomap import generate_repo_map, parse_file_symbols, render_repo_map_text
from devops_cli.commands.ai import app as ai_app

runner = CliRunner()


def test_repomap_generation(tmp_path: Path) -> None:
    """Verify AST repository map generation and formatting."""
    src_file = tmp_path / "sample.py"
    src_file.write_text(
        'class Calculator:\n    """Simple calculator."""\n    def add(self, a: int, b: int) -> int:\n        return a + b\n\ndef helper() -> str:\n    return "ok"\n',
        encoding="utf-8",
    )
    node = parse_file_symbols(src_file, tmp_path)
    assert node is not None
    assert len(node.symbols) == 2
    assert node.symbols[0].name == "Calculator"
    assert node.symbols[1].name == "helper"

    text = render_repo_map_text([node])
    assert "class Calculator" in text
    assert "def add" in text
    assert "def helper" in text


def test_repomap_cli(tmp_path: Path) -> None:
    """Verify devops ai repomap CLI command."""
    res = runner.invoke(ai_app, ["repomap", "--dry-run"])
    assert (res.exit_code == 0) and (
        "DRY_RUN_MAPPED" in res.output or "generate_symbol_map" in res.output
    )

    sample = tmp_path / "sample.py"
    sample.write_text("def hello() -> None:\n    pass\n", encoding="utf-8")

    res_json = runner.invoke(
        ai_app, ["repomap", "--target", str(tmp_path), "--max-files", "5", "--json"]
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert (data.get("files_count") == 1, len(data.get("files", [])) == 1) == (True, True)


def test_repomap_maps_the_nested_worktree_it_runs_in(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops ai repomap` from a worktree under `.claude/worktrees/` maps that worktree's
    sources, not the checkout around it (#582)."""
    main, nested = nested_worktree
    for tree, module in ((main, "main_only"), (nested, "worktree_only")):
        (tree / "src").mkdir()
        (tree / "src" / f"{module}.py").write_text("def size() -> int:\n    return 1\n")
    monkeypatch.chdir(nested)

    mapped = [node.path for node in generate_repo_map()]

    assert mapped == ["src/worktree_only.py"]
