"""Tests for architecture topology and threat modeling diagram generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.diagram import generate_architecture_diagram, generate_threat_diagram
from devops_cli.commands.ai import app as ai_app

runner = CliRunner()


def test_diagram_generation() -> None:
    """Verify architecture and threat modeling diagram generators."""
    arch = generate_architecture_diagram()
    assert arch.diagram_type == "arch"
    assert "graph TD" in arch.mermaid_code

    threat = generate_threat_diagram()
    assert threat.diagram_type == "threat"
    assert "graph LR" in threat.mermaid_code


def test_diagram_cli() -> None:
    """Verify devops ai diagram CLI command."""
    res_arch = runner.invoke(ai_app, ["diagram", "arch", "--dry-run"])
    assert res_arch.exit_code == 0
    assert "DRY_RUN_DIAGRAM_GENERATED" in res_arch.output

    res_threat = runner.invoke(ai_app, ["diagram", "threat", "--json"])
    assert res_threat.exit_code == 0
    data = json.loads(res_threat.output)
    assert data["diagram_type"] == "threat"


def test_architecture_diagram_lists_the_nested_worktrees_packages(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the architecture diagram from a worktree under `.claude/worktrees/` lists that
    worktree's subsystems, not the checkout's around it (#582)."""
    main, nested = nested_worktree
    for tree, package in ((main, "main_only"), (nested, "worktree_only")):
        (tree / "src" / "devops_cli" / package).mkdir(parents=True)
    monkeypatch.chdir(nested)

    components = [component["name"] for component in generate_architecture_diagram().components]

    assert components == ["worktree_only"]
