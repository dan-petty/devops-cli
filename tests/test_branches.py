"""Tests for branches commands and branch naming logic."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.branches import app as branches_app

runner = CliRunner()


def _make_branch(ticket_id: str, slug: str | None = None) -> str:
    """Replicate the branch naming logic from commands/branches.py."""
    ticket_upper = ticket_id.upper()
    if slug:
        safe_slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
        return f"feature/{ticket_upper}-{safe_slug}"
    return f"feature/{ticket_upper}"


_JIRA_RE = re.compile(r"^([A-Z][A-Z0-9]+-\d+)$", re.IGNORECASE)


@pytest.mark.parametrize(
    "ticket_id,valid",
    [
        ("PROJ-123", True),
        ("ABC-1", True),
        ("abc-99", True),
        ("A1B-42", True),
        ("123-PROJ", False),
        ("PROJ", False),
        ("PROJ-", False),
        ("", False),
        ("-123", False),
    ],
)
def test_jira_id_validation(ticket_id: str, valid: bool) -> None:
    assert bool(_JIRA_RE.match(ticket_id)) == valid


@pytest.mark.parametrize(
    "ticket_id,slug,expected",
    [
        ("PROJ-123", None, "feature/PROJ-123"),
        ("proj-456", None, "feature/PROJ-456"),
        ("PROJ-123", "add user auth", "feature/PROJ-123-add-user-auth"),
        ("PROJ-123", "Fix Bug!!!", "feature/PROJ-123-fix-bug"),
        ("PROJ-789", "  leading spaces  ", "feature/PROJ-789-leading-spaces"),
        ("PROJ-1", "a---b", "feature/PROJ-1-a-b"),
        ("ABC-99", "Update / Refactor", "feature/ABC-99-update-refactor"),
    ],
)
def test_branch_name_generation(ticket_id: str, slug: str | None, expected: str) -> None:
    assert _make_branch(ticket_id, slug) == expected


def test_branches_commands(tmp_path: Path) -> None:
    """Verify branches list, clean, jira, and update subcommands."""
    repo_dir = tmp_path / "my-repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    with (
        patch("devops_cli.commands.branches.iter_workspace_repos", return_value=[repo_dir]),
        patch(
            "devops_cli.commands.branches.list_branches",
            return_value=MagicMock(branches=["main", "feat/test"], current="main"),
        ),
        patch("devops_cli.commands.branches.delete_merged_branches", return_value=["feat/test"]),
        patch("devops_cli.commands.branches.fetch_all"),
        patch("devops_cli.commands.branches.pull_tracking"),
        patch("devops_cli.commands.branches.create_branch"),
    ):
        res_list = runner.invoke(branches_app, ["list", "--all"])
        assert res_list.exit_code == 0

        res_clean = runner.invoke(branches_app, ["clean", "--dry-run"])
        assert res_clean.exit_code == 0

        res_update = runner.invoke(branches_app, ["update"])
        assert res_update.exit_code == 0

        res_jira = runner.invoke(
            branches_app, ["jira", "PROJ-123", "--slug", "my-feature", "--repo", str(repo_dir)]
        )
        assert res_jira.exit_code == 0


def _repo_with_one_commit(git: Callable[..., None], repo: Path) -> None:
    git(repo, "init", "--quiet", "-b", "main")
    git(repo, "commit", "--quiet", "--allow-empty", "-m", "init")


def _current_branch(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_jira_creates_and_checks_out_the_feature_branch(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """`branches jira` creates feature/<TICKET>-<slug> from HEAD and switches to it."""
    _repo_with_one_commit(git, tmp_path)

    result = runner.invoke(
        branches_app, ["jira", "PROJ-123", "--slug", "my feature", "--repo", str(tmp_path)]
    )

    assert (result.exit_code, _current_branch(tmp_path)) == (0, "feature/PROJ-123-my-feature")


def test_jira_prints_gits_reason_when_git_refuses_the_branch(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """A branch git refuses ends in git's reason and exit 1, not a traceback."""
    _repo_with_one_commit(git, tmp_path)
    git(tmp_path, "branch", "feature")

    result = runner.invoke(branches_app, ["jira", "PROJ-123", "--repo", str(tmp_path)])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output
    assert "'refs/heads/feature' exists" in result.output


def test_branches_sync_reports_failures_and_exits_nonzero(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """`branches sync` reports failed repos with git's reason, finishes remaining repos, and exits 1."""
    repos_dir = tmp_path / "repos"
    bare1 = tmp_path / "bare1.git"
    bare2 = tmp_path / "bare2.git"
    bare1.mkdir()
    bare2.mkdir()
    git(bare1, "init", "--bare", "--initial-branch=main", "--quiet")
    git(bare2, "init", "--bare", "--initial-branch=main", "--quiet")

    repo1 = repos_dir / "group" / "repo1"
    repo2 = repos_dir / "group" / "repo2"
    git(tmp_path, "clone", "--quiet", str(bare1), str(repo1))
    git(tmp_path, "clone", "--quiet", str(bare2), str(repo2))

    (repo1 / "f.txt").write_text("1", encoding="utf-8")
    git(repo1, "add", ".")
    git(repo1, "commit", "--quiet", "-m", "init")
    git(repo1, "push", "--quiet", "origin", "main")

    (repo2 / "f.txt").write_text("2", encoding="utf-8")
    git(repo2, "add", ".")
    git(repo2, "commit", "--quiet", "-m", "init")
    git(repo2, "push", "--quiet", "origin", "main")

    # Make bare1 refuse fetch
    objects_dir = bare1 / "objects"
    objects_dir.chmod(0o000)

    try:
        res = runner.invoke(branches_app, ["sync", "--base-dir", str(repos_dir)])
        assert res.exit_code == 1
        assert "group/repo1" in res.output
        assert "group/repo2" in res.output
    finally:
        objects_dir.chmod(0o755)
