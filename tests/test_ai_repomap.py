"""Tests for AST repository map generator and devops ai repomap CLI."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from devops_cli.ai.repomap import parse_file_symbols, render_repo_map_text
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


def test_repomap_cli() -> None:
    """Verify devops ai repomap CLI command."""
    res = runner.invoke(ai_app, ["repomap", "--dry-run"])
    assert res.exit_code == 0
    assert "DRY_RUN_MAPPED" in res.output or "generate_symbol_map" in res.output

    res_json = runner.invoke(ai_app, ["repomap", "--max-files", "5", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert "files_count" in data
