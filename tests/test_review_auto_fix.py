"""Tests for automated PR remediation branch generator and auto-fix CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review.auto_fix import generate_remediation_branch
from devops_cli.commands.review import app as review_app

runner = CliRunner()


def test_review_auto_fix_cli() -> None:
    """Verify devops ai review auto-fix command."""
    res = runner.invoke(review_app, ["auto-fix", "cwe-200-leak", "--dry-run"])
    assert res.exit_code == 0
    assert (
        "Created remediation topic branch" in res.output or "fix/finding-cwe-200-leak" in res.output
    )


def test_auto_fix_finds_a_file_only_the_nested_worktree_has(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a remediation target present only in the worktree under `.claude/worktrees/` it
    runs from is found there rather than looked up in the checkout around it (#582)."""
    _, nested = nested_worktree
    (nested / "src").mkdir()
    (nested / "src" / "only_here.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.chdir(nested)

    result = generate_remediation_branch("cwe-200", target_file="src/only_here.py")

    assert (result.status, result.applied) == ("REMEDIATION_BRANCH_PREPARED", True)
