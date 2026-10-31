"""Tests for architecture topology and threat modeling diagram generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.diagram import generate_architecture_diagram, generate_threat_diagram
from devops_cli.commands.ai import app as ai_app
from devops_cli.main import app as root_app

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
    res_arch = runner.invoke(root_app, ["--dry-run", "ai", "diagram", "arch"])
    assert res_arch.exit_code == 0
    assert "graph TD" in res_arch.output

    res_threat = runner.invoke(ai_app, ["diagram", "threat", "--json"])
    assert res_threat.exit_code == 0
    data = json.loads(res_threat.output)
    assert data["diagram_type"] == "threat"


@pytest.fixture
def nested_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Provide a nested worktree without starting git processes."""
    main = tmp_path / "main"
    main.mkdir(parents=True, exist_ok=True)
    (main / ".git").mkdir(parents=True, exist_ok=True)
    (main / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (main / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (main / "pyproject.toml").write_text(
        '[project]\nname = "main"\n\n[tool.ruff.lint]\nselect = ["F401"]\n',
        encoding="utf-8",
    )
    nested = main / ".claude" / "worktrees" / "wt"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.mkdir(parents=True, exist_ok=True)
    (nested / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (nested / "pyproject.toml").write_text(
        '[project]\nname = "main"\n\n[tool.ruff.lint]\nselect = ["F401"]\n',
        encoding="utf-8",
    )
    wt_git = main / ".git" / "worktrees" / "wt"
    wt_git.mkdir(parents=True, exist_ok=True)
    (nested / ".git").write_text(f"gitdir: {wt_git}\n", encoding="utf-8")
    (wt_git / "gitdir").write_text(f"{nested / '.git'}\n", encoding="utf-8")
    (wt_git / "commondir").write_text("../..\n", encoding="utf-8")
    (wt_git / "HEAD").write_text("ref: refs/heads/nested\n", encoding="utf-8")
    return main, nested


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
