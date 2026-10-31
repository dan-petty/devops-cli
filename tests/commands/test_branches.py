"""Tests for branches commands and branch naming logic."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.branches import app as branches_app
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer

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


def test_branches_commands(tmp_path: Path, git_fake: GitFake) -> None:
    """Verify branches list, clean, jira, and update subcommands."""
    repos_dir = tmp_path / "repos"
    repo_dir = repos_dir / "group" / "my-repo"
    (repo_dir / ".git").mkdir(parents=True)

    git_fake.answer(
        ["git", "-C", str(repo_dir), "branch", "--show-current"],
        ProcessAnswer(stdout="main\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(repo_dir),
            "for-each-ref",
            "--format=%(refname)",
            "refs/heads",
            "refs/remotes",
        ],
        ProcessAnswer(stdout="refs/heads/main\nrefs/heads/feat/test\nrefs/remotes/origin/main\n"),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(repo_dir),
            "branch",
            "--merged",
            "main",
            "--format=%(refname:lstrip=2)",
        ],
        ProcessAnswer(stdout="feat/test\nmain\n"),
    )
    git_fake.answer(
        ["git", "-C", str(repo_dir), "remote"],
        ProcessAnswer(stdout="origin\n"),
    )
    git_fake.answer(
        ["git", "-C", str(repo_dir), "fetch", "--prune", "origin"],
        ProcessAnswer(returncode=0),
    )
    git_fake.answer(
        ["git", "-C", str(repo_dir), "config", "--get", "branch.main.remote"],
        ProcessAnswer(stdout="origin\n"),
    )
    git_fake.answer(
        ["git", "-C", str(repo_dir), "pull", "origin", "main"],
        ProcessAnswer(returncode=0),
    )
    git_fake.answer(
        [
            "git",
            "-C",
            str(repo_dir),
            "show-ref",
            "--verify",
            "--quiet",
            "refs/heads/feature/PROJ-123-my-feature",
        ],
        ProcessAnswer(returncode=1),
    )
    git_fake.answer(
        ["git", "-C", str(repo_dir), "checkout", "-b", "feature/PROJ-123-my-feature"],
        ProcessAnswer(returncode=0),
    )

    res_list = runner.invoke(branches_app, ["list", "--all", "--base-dir", str(repos_dir)])
    assert res_list.exit_code == 0
    assert "group/my-repo" in res_list.output
    assert "feat/test" in res_list.output

    res_clean = runner.invoke(branches_app, ["clean", "--dry-run", "--base-dir", str(repos_dir)])
    assert res_clean.exit_code == 0
    assert "would delete group/my-repo: feat/test" in res_clean.output

    res_update = runner.invoke(branches_app, ["update", "--base-dir", str(repos_dir)])
    assert res_update.exit_code == 0
    assert "group/my-repo" in res_update.output

    res_jira = runner.invoke(
        branches_app, ["jira", "PROJ-123", "--slug", "my-feature", "--repo", str(repo_dir)]
    )
    assert res_jira.exit_code == 0


def test_jira_creates_and_checks_out_the_feature_branch(tmp_path: Path, git_fake: GitFake) -> None:
    """`branches jira` creates feature/<TICKET>-<slug> from HEAD and switches to it."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    git_fake.answer(
        [
            "git",
            "-C",
            str(repo),
            "show-ref",
            "--verify",
            "--quiet",
            "refs/heads/feature/PROJ-123-my-feature",
        ],
        ProcessAnswer(returncode=1),
    )
    git_fake.answer(
        ["git", "-C", str(repo), "checkout", "-b", "feature/PROJ-123-my-feature"],
        ProcessAnswer(returncode=0),
    )

    result = runner.invoke(
        branches_app, ["jira", "PROJ-123", "--slug", "my feature", "--repo", str(repo)]
    )

    assert result.exit_code == 0
    assert ("git", "-C", str(repo), "checkout", "-b", "feature/PROJ-123-my-feature") in [
        c.argv for c in git_fake.calls
    ]


def test_jira_prints_gits_reason_when_git_refuses_the_branch(
    tmp_path: Path, git_fake: GitFake
) -> None:
    """A branch git refuses ends in git's reason and exit 1, not a traceback."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    git_fake.answer(
        ["git", "-C", str(repo), "show-ref", "--verify", "--quiet", "refs/heads/feature/PROJ-123"],
        ProcessAnswer(returncode=1),
    )
    git_fake.answer(
        ["git", "-C", str(repo), "checkout", "-b", "feature/PROJ-123"],
        ProcessAnswer(
            returncode=128,
            stderr=(
                "fatal: cannot lock ref 'refs/heads/feature/PROJ-123': 'refs/heads/feature' exists; "
                "cannot create 'refs/heads/feature/PROJ-123'"
            ),
        ),
    )

    result = runner.invoke(branches_app, ["jira", "PROJ-123", "--repo", str(repo)])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output
    assert "'refs/heads/feature' exists" in result.output


def test_branches_sync_reports_failures_and_exits_nonzero(
    tmp_path: Path, git_fake: GitFake
) -> None:
    """`branches sync` reports failed repos with git's reason, finishes remaining repos, and exits 1."""
    repos_dir = tmp_path / "repos"
    repo1 = repos_dir / "group" / "repo1"
    repo2 = repos_dir / "group" / "repo2"
    (repo1 / ".git").mkdir(parents=True)
    (repo2 / ".git").mkdir(parents=True)

    git_fake.answer(
        ["git", "-C", str(repo1), "remote"],
        ProcessAnswer(stdout="origin\n"),
    )
    git_fake.answer(
        ["git", "-C", str(repo1), "fetch", "--prune", "origin"],
        ProcessAnswer(returncode=1, stderr="fatal: remote error: permission denied"),
    )

    git_fake.answer(
        ["git", "-C", str(repo2), "remote"],
        ProcessAnswer(stdout="origin\n"),
    )
    git_fake.answer(
        ["git", "-C", str(repo2), "fetch", "--prune", "origin"],
        ProcessAnswer(returncode=0),
    )
    git_fake.answer(
        ["git", "-C", str(repo2), "branch", "--show-current"],
        ProcessAnswer(stdout="main\n"),
    )
    git_fake.answer(
        ["git", "-C", str(repo2), "config", "--get", "branch.main.remote"],
        ProcessAnswer(stdout="origin\n"),
    )
    git_fake.answer(
        ["git", "-C", str(repo2), "pull", "origin", "main"],
        ProcessAnswer(returncode=0),
    )

    res = runner.invoke(branches_app, ["sync", "--base-dir", str(repos_dir)])
    assert res.exit_code == 1
    assert "group/repo1" in res.output
    assert "group/repo2" in res.output
