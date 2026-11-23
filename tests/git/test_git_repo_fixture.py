"""Tests for the git_repo fixture (ADR 0007, #6474)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.project_digest import head_commit
from devops_cli.core.process import run_subprocess
from tests.support.fakes.git import GitFake
from tests.support.git_repo import GIT_REPO_COMMIT


def test_git_repo_fixture_answers_rev_parse_head(git_repo: Path, git_fake: GitFake) -> None:
    """A test that reads Git tracking gets the recorded commit and starts no real git."""
    commit = head_commit(git_repo)
    assert commit == GIT_REPO_COMMIT

    direct = run_subprocess(["git", "rev-parse", "HEAD"], cwd=git_repo)
    assert direct.stdout.strip() == GIT_REPO_COMMIT

    assert any("rev-parse" in call.argv and "HEAD" in call.argv for call in git_fake.calls)
