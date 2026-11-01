"""Tests for branches commands and branch naming logic."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

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


# =============================================================================
# Dry runs (#2258)
# =============================================================================


def _sync_workspace(tmp_path: Path, git_fake: GitFake) -> tuple[Path, Path]:
    """A workspace with one repository whose `main` tracks `origin`, and its git answers."""
    repos_dir = tmp_path / "repos"
    repo_dir = repos_dir / "group" / "my-repo"
    (repo_dir / ".git").mkdir(parents=True)
    git_fake.answer(["git", "-C", str(repo_dir), "remote"], ProcessAnswer(stdout="origin\n"))
    git_fake.answer(
        ["git", "-C", str(repo_dir), "branch", "--show-current"], ProcessAnswer(stdout="main\n")
    )
    git_fake.answer(
        ["git", "-C", str(repo_dir), "config", "--get", "branch.main.remote"],
        ProcessAnswer(stdout="origin\n"),
    )
    git_fake.answer(["git", "-C", str(repo_dir), "fetch"], ProcessAnswer())
    git_fake.answer(["git", "-C", str(repo_dir), "pull"], ProcessAnswer())
    return repos_dir, repo_dir


def _external_calls(git_fake: GitFake) -> list[tuple[str, ...]]:
    """The argv of each recorded call that is not a read of the local repository."""
    return [call.argv for call in git_fake.calls if not call.local_read]


def _plan_lines(output: str) -> list[str]:
    """The numbered lines of a request plan, without their numbers."""
    return [line.split(". ", 1)[1] for line in output.splitlines() if re.match(r"^\s*\d+\. ", line)]


def test_branches_dry_run_classes() -> None:
    """Each branches command carries the dry-run class of what it reaches."""
    from devops_cli.commands import branches
    from devops_cli.dry_run.decorator import get_dry_run_class

    assert get_dry_run_class(branches.update) == "request-plan"
    for callback in (branches.clean, branches.jira, branches.list_all):
        assert get_dry_run_class(callback) == "no-external-request"


@pytest.mark.parametrize(
    "argv",
    [
        ["branches", "sync", "--dry-run"],
        ["branches", "update", "--dry-run"],
        ["--dry-run", "branches", "sync"],
    ],
)
def test_branches_sync_dry_run_lists_the_fetch_and_the_pull(
    tmp_path: Path, git_fake: GitFake, cli: Any, argv: list[str]
) -> None:
    """A dry run reads the local repository, fetches and pulls nothing, and lists both."""
    repos_dir, repo_dir = _sync_workspace(tmp_path, git_fake)

    result = cli([*argv, "--base-dir", str(repos_dir)])

    assert result.exit_code == 0, result.output
    assert _external_calls(git_fake) == []
    assert _plan_lines(result.output) == [
        f"git -C {repo_dir} fetch --prune origin",
        f"git -C {repo_dir} pull origin main",
    ]


def test_branches_sync_runs_the_requests_of_its_plan(
    tmp_path: Path, git_fake: GitFake, cli: Any
) -> None:
    """The real run starts the commands of the plan, in the same order."""
    repos_dir, _repo_dir = _sync_workspace(tmp_path, git_fake)
    planned = _plan_lines(
        cli(["branches", "sync", "--dry-run", "--base-dir", str(repos_dir)]).output
    )
    git_fake.calls.clear()

    result = cli(["branches", "sync", "--base-dir", str(repos_dir)])

    assert result.exit_code == 0, result.output
    assert [" ".join(argv) for argv in _external_calls(git_fake)] == planned


def test_branches_list_and_clean_run_under_the_dry_run_flag(
    tmp_path: Path, git_fake: GitFake, cli: Any
) -> None:
    """`branches list` runs normally under `devops --dry-run`, and `branches clean` previews."""
    repos_dir = tmp_path / "repos"
    repo_dir = repos_dir / "group" / "my-repo"
    (repo_dir / ".git").mkdir(parents=True)
    git_fake.answer(
        ["git", "-C", str(repo_dir), "branch", "--show-current"], ProcessAnswer(stdout="main\n")
    )
    git_fake.answer(
        ["git", "-C", str(repo_dir), "for-each-ref"],
        ProcessAnswer(stdout="refs/heads/main\nrefs/heads/feat/test\n"),
    )
    git_fake.answer(
        ["git", "-C", str(repo_dir), "branch", "--merged"],
        ProcessAnswer(stdout="feat/test\nmain\n"),
    )

    listed = cli(["--dry-run", "branches", "list", "--base-dir", str(repos_dir)])
    assert listed.exit_code == 0, listed.output
    assert "group/my-repo" in listed.output
    assert "feat/test" in listed.output
    assert _external_calls(git_fake) == []

    for argv in (
        ["--dry-run", "branches", "clean", "--base-dir", str(repos_dir)],
        ["branches", "clean", "--dry-run", "--base-dir", str(repos_dir)],
    ):
        cleaned = cli(argv)
        assert cleaned.exit_code == 0, cleaned.output
        assert "would delete group/my-repo: feat/test" in cleaned.output
    assert _external_calls(git_fake) == []


@pytest.mark.parametrize(
    "argv",
    [
        ["branches", "jira", "PROJ-1", "--dry-run"],
        ["--dry-run", "branches", "jira", "PROJ-1"],
    ],
)
def test_branches_jira_dry_run_creates_no_branch(
    tmp_path: Path, git_fake: GitFake, cli: Any, argv: list[str]
) -> None:
    """A dry run names the branch that the run would create, and starts no git."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    result = cli([*argv, "--repo", str(repo)])

    assert result.exit_code == 0, result.output
    assert "Would create the branch feature/PROJ-1" in result.output
    assert git_fake.calls == []


def test_branches_jira_dry_run_refuses_a_bad_ticket(cli: Any) -> None:
    """A dry run refuses the ticket that a run refuses."""
    result = cli(["branches", "jira", "bad", "--dry-run"])

    assert result.exit_code == 1
    assert "Invalid ticket ID" in result.output
