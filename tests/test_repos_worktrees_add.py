"""Tests for `devops repos worktrees add`: where it creates the worktree of an issue, which
issues it refuses, and what its dry run lists (#2337).

The repositories are real. `origin` is a bare repository in `tmp_path`, so `git ls-remote` and
`git fetch` run for real and reach no network.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

Git = Callable[..., None]
Cli = Callable[..., Any]

ISSUE = 2337
BOT = "devops-roadmap[bot]"
STAGED = "feat/2337-worktrees-add"


@pytest.fixture
def origin(tmp_path: Path, git: Git) -> Path:
    """A bare repository that serves as `origin`."""
    bare = tmp_path / "origin.git"
    bare.mkdir()
    git(bare, "init", "--bare", "-b", "main")
    return bare


@pytest.fixture
def repo(tmp_path: Path, git: Git, origin: Path) -> Path:
    """A repository with one commit on main, pushed to `origin`."""
    work = tmp_path / "repo"
    work.mkdir()
    git(work, "init", "-b", "main")
    (work / "file.txt").write_text("base\n", encoding="utf-8")
    git(work, "add", "file.txt")
    git(work, "commit", "-m", "init")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "origin", "main")
    return work


@pytest.fixture
def standard_dir(isolate_data_dir: Path) -> Path:
    """The directory that holds the worktree of an issue: `w-<issue>` under the agent worktrees
    directory of the data directory."""
    return isolate_data_dir / "agent" / "worktrees" / f"w-{ISSUE}"


def _add(
    cli: Cli,
    repo: Path,
    *,
    issue: int = ISSUE,
    type_: str = "feat",
    slug: str = "worktrees-add",
    extra: tuple[str, ...] = (),
) -> Any:
    return cli(
        "repos",
        "worktrees",
        "add",
        str(issue),
        "--type",
        type_,
        "--slug",
        slug,
        "--repo-dir",
        str(repo),
        # These tests are about claims. The reclaim has tests of its own, with the GitHub fake.
        "--no-reclaim",
        *extra,
    )


def _said(result: Any) -> str:
    """The output as one line of single-spaced words."""
    return " ".join(result.output.split())


def _git_out(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args], check=False, capture_output=True, text=True
    )


def _branches(repo: Path) -> list[str]:
    return _git_out(repo, "branch", "--format=%(refname:short)").stdout.split()


def _push_branch(origin: Path, tmp_path: Path, branch: str, *authors: str) -> str:
    """Push `branch` to `origin` with one commit for each name in `authors`, in order; return its
    tip. The commits come from a clone, so the repository under test has not fetched them."""
    work = tmp_path / f"push-{branch.replace('/', '-')}"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    subprocess.run(["git", "-C", str(work), "checkout", "-q", "-b", branch], check=True)
    for number, author in enumerate(authors):
        (work / f"commit-{number}.txt").write_text(f"{author}\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(work), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(work),
                "-c",
                f"user.name={author}",
                "-c",
                "user.email=author@example.com",
                "commit",
                "-q",
                "-m",
                f"commit {number}",
            ],
            check=True,
        )
    subprocess.run(["git", "-C", str(work), "push", "-q", "origin", branch], check=True)
    return _git_out(work, "rev-parse", "HEAD").stdout.strip()


def test_add_creates_the_worktree_of_the_issue_at_the_fetched_tip(
    cli: Cli, repo: Path, origin: Path, git: Git, tmp_path: Path, standard_dir: Path
) -> None:
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(origin), str(other)], check=True)
    (other / "later.txt").write_text("later\n", encoding="utf-8")
    git(other, "add", "later.txt")
    git(other, "commit", "-m", "later")
    git(other, "push", "origin", "main")
    pushed = _git_out(other, "rev-parse", "HEAD").stdout.strip()

    result = _add(cli, repo, extra=("--json",))

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert (report["issue"], report["branch"], report["status"]) == (
        ISSUE,
        "feat/2337-worktrees-add",
        "created",
    )
    assert Path(report["path"]) == standard_dir
    assert _git_out(standard_dir, "branch", "--show-current").stdout.strip() == report["branch"]
    assert _git_out(standard_dir, "rev-parse", "HEAD").stdout.strip() == pushed


def test_the_new_branch_has_no_upstream(cli: Cli, repo: Path, standard_dir: Path) -> None:
    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    upstream = _git_out(standard_dir, "rev-parse", "--abbrev-ref", "@{u}")
    assert upstream.returncode != 0


def test_the_table_output_names_the_path_and_the_branch(
    cli: Cli, repo: Path, standard_dir: Path
) -> None:
    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert f"w-{ISSUE}" in _said(result)
    assert "feat/2337-worktrees-add" in _said(result)


@pytest.mark.parametrize("type_", ["feature", "Feat", "", "wip"])
def test_an_unknown_type_is_a_usage_error_that_names_the_types(
    cli: Cli, repo: Path, standard_dir: Path, type_: str
) -> None:
    result = _add(cli, repo, type_=type_)

    assert result.exit_code == 2
    assert "refactor" in _said(result)
    assert not standard_dir.exists()


@pytest.mark.parametrize(
    "slug", ["Bad_Slug", "-leading", "trailing-", "double--hyphen", "UPPER", "with space", ""]
)
def test_a_slug_that_breaks_the_form_is_a_usage_error(
    cli: Cli, repo: Path, standard_dir: Path, slug: str
) -> None:
    result = _add(cli, repo, slug=slug)

    assert result.exit_code == 2
    assert "lowercase" in _said(result)
    assert not standard_dir.exists()
    assert _branches(repo) == ["main"]


def test_a_bad_type_is_reported_before_a_missing_origin(
    cli: Cli, repo: Path, git: Git, standard_dir: Path
) -> None:
    git(repo, "remote", "remove", "origin")

    result = _add(cli, repo, type_="feature")

    assert result.exit_code == 2
    assert "refactor" in _said(result)
    assert "origin" not in _said(result)


def test_a_worktree_with_another_slug_of_the_issue_holds_it(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, standard_dir: Path
) -> None:
    git(repo, "worktree", "add", "-b", "fix/2337-other", str(tmp_path / "wt_other"))

    result = _add(cli, repo)

    assert result.exit_code == 1
    assert "wt_other" in _said(result)
    assert "fix/2337-other" in _said(result)
    assert not standard_dir.exists()
    assert "feat/2337-worktrees-add" not in _branches(repo)


def test_the_standard_directory_holds_the_issue(cli: Cli, repo: Path, standard_dir: Path) -> None:
    standard_dir.mkdir(parents=True)

    result = _add(cli, repo)

    assert result.exit_code == 1
    assert f"w-{ISSUE}" in _said(result)
    assert "feat/2337-worktrees-add" not in _branches(repo)


def test_a_longer_issue_number_is_no_claim(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, standard_dir: Path
) -> None:
    git(repo, "worktree", "add", "-b", "feat/23370-x", str(tmp_path / "wt_longer"))

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert standard_dir.is_dir()


def test_a_branch_of_origin_with_a_commit_by_a_person_holds_the_issue(
    cli: Cli, repo: Path, origin: Path, tmp_path: Path, config: Cli, standard_dir: Path
) -> None:
    config(service={"github_app": {"slug": "devops-roadmap"}})
    _push_branch(origin, tmp_path, "fix/2337-other", "Jane Doe")

    result = _add(cli, repo, type_="fix", slug="other")

    assert result.exit_code == 1
    assert "origin/fix/2337-other" in _said(result)
    assert "Jane Doe" in _said(result)
    assert not standard_dir.exists()
    assert "feat/2337-worktrees-add" not in _branches(repo)


def test_a_branch_of_origin_with_no_commit_past_main_holds_the_issue(
    cli: Cli, repo: Path, git: Git, config: Cli, standard_dir: Path
) -> None:
    config(service={"github_app": {"slug": "devops-roadmap"}})
    git(repo, "push", "origin", "HEAD:refs/heads/fix/2337-other")

    result = _add(cli, repo, type_="fix", slug="other")

    assert result.exit_code == 1
    assert "origin/fix/2337-other" in _said(result)
    assert not standard_dir.exists()


def test_a_branch_of_origin_for_another_issue_is_no_claim(
    cli: Cli, repo: Path, git: Git, standard_dir: Path
) -> None:
    git(repo, "push", "origin", "HEAD:refs/heads/fix/2338-other")
    git(repo, "push", "origin", "HEAD:refs/heads/release-please--branches--main")

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert standard_dir.is_dir()


def test_a_local_branch_with_no_worktree_holds_nothing(
    cli: Cli, repo: Path, git: Git, standard_dir: Path
) -> None:
    git(repo, "branch", "feat/2337-old")

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert standard_dir.is_dir()


def test_a_repository_without_origin_names_origin(
    cli: Cli, repo: Path, git: Git, standard_dir: Path
) -> None:
    git(repo, "remote", "remove", "origin")

    result = _add(cli, repo)

    assert result.exit_code == 1
    assert "origin" in _said(result)
    assert not standard_dir.exists()
    assert _branches(repo) == ["main"]


def test_a_failed_read_of_origin_creates_nothing(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, standard_dir: Path
) -> None:
    git(repo, "remote", "set-url", "origin", str(tmp_path / "gone.git"))

    result = _add(cli, repo)

    assert result.exit_code == 1
    assert not standard_dir.exists()
    assert _branches(repo) == ["main"]


def test_a_dry_run_lists_the_four_commands_and_changes_nothing(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, standard_dir: Path
) -> None:
    # Origin cannot be reached, so a dry run that reads it would fail.
    git(repo, "remote", "set-url", "origin", str(tmp_path / "gone.git"))

    result = _add(cli, repo, extra=("--dry-run",))

    said = _said(result)
    assert result.exit_code == 0, result.output
    assert said.index("ls-remote --heads origin") < said.index("fetch origin main")
    assert said.index("fetch origin main") < said.index("log --format")
    assert said.index("log --format") < said.index("worktree add --no-track")
    assert "feat/2337-worktrees-add" in said
    assert not standard_dir.exists()
    assert _branches(repo) == ["main"]


def test_a_dry_run_report_has_the_type_of_the_real_report(
    cli: Cli, repo: Path, standard_dir: Path
) -> None:
    planned = json.loads(_add(cli, repo, extra=("--dry-run", "--json")).output)
    created = json.loads(_add(cli, repo, extra=("--json",)).output)

    assert planned["status"] == "would create"
    assert created["status"] == "created"
    assert {key for key in planned if key != "requests"} == {
        key for key in created if key != "requests"
    }
    assert len(planned["requests"]) == 4


def test_a_dry_run_names_the_read_of_the_authors_and_the_staged_branch(
    cli: Cli, repo: Path, standard_dir: Path
) -> None:
    said = _said(_add(cli, repo, extra=("--dry-run",)))

    assert f"log --format=%an origin/main..origin/{STAGED}" in said
    assert "staged branch" in said


def test_a_dry_run_without_a_slug_is_a_usage_error(
    cli: Cli, repo: Path, standard_dir: Path
) -> None:
    result = cli(
        "repos", "worktrees", "add", str(ISSUE), "--type", "feat",
        "--repo-dir", str(repo), "--no-reclaim", "--dry-run",
    )  # fmt: skip

    assert result.exit_code == 2
    assert "--slug" in _said(result)
    assert not standard_dir.exists()


def test_a_dry_run_still_refuses_an_issue_that_a_local_worktree_holds(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, standard_dir: Path
) -> None:
    git(repo, "worktree", "add", "-b", "fix/2337-other", str(tmp_path / "wt_other"))

    result = _add(cli, repo, extra=("--dry-run",))

    assert result.exit_code == 1
    assert "wt_other" in _said(result)


@pytest.fixture
def app(config: Cli) -> None:
    """The settings name the App `devops-roadmap`, so its bot login is `devops-roadmap[bot]`."""
    config(service={"github_app": {"slug": "devops-roadmap"}})


def _add_by_issue(cli: Cli, repo: Path, *extra: str) -> Any:
    """Run `add` with the options of `extra` and no `--type` or `--slug`."""
    return cli(
        "repos", "worktrees", "add", str(ISSUE), "--repo-dir", str(repo), "--no-reclaim", *extra
    )  # fmt: skip


@pytest.mark.usefixtures("app")
def test_a_branch_with_only_the_commits_of_the_app_is_taken_over(
    cli: Cli, repo: Path, origin: Path, tmp_path: Path, standard_dir: Path
) -> None:
    tip = _push_branch(origin, tmp_path, STAGED, BOT, BOT)

    result = _add(cli, repo, extra=("--json",))

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert (report["status"], report["commits"], report["branch"]) == ("took over", 2, STAGED)
    assert Path(report["path"]) == standard_dir
    assert _git_out(standard_dir, "branch", "--show-current").stdout.strip() == STAGED
    assert _git_out(standard_dir, "rev-parse", "HEAD").stdout.strip() == tip
    upstream = _git_out(standard_dir, "rev-parse", "--abbrev-ref", "@{u}")
    assert upstream.stdout.strip() == f"origin/{STAGED}"


@pytest.mark.usefixtures("app")
def test_the_table_output_says_that_the_command_took_over_a_staged_branch(
    cli: Cli, repo: Path, origin: Path, tmp_path: Path, standard_dir: Path
) -> None:
    _push_branch(origin, tmp_path, STAGED, BOT, BOT)

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    said = _said(result)
    assert f"Took over the staged branch {STAGED}" in said
    assert "Commits by the App: 2" in said
    assert f"w-{ISSUE}" in said


@pytest.mark.usefixtures("app")
def test_the_commits_of_a_stopped_implement_run_are_taken_over_with_the_staging_commit(
    cli: Cli, repo: Path, origin: Path, tmp_path: Path, standard_dir: Path
) -> None:
    _push_branch(origin, tmp_path, STAGED, BOT, BOT, BOT)

    report = json.loads(_add(cli, repo, extra=("--json",)).output)

    assert (report["status"], report["commits"]) == ("took over", 3)
    assert (standard_dir / "commit-2.txt").is_file()


@pytest.mark.usefixtures("app")
def test_a_branch_with_a_commit_by_a_person_is_refused_and_names_the_author(
    cli: Cli, repo: Path, origin: Path, tmp_path: Path, standard_dir: Path
) -> None:
    _push_branch(origin, tmp_path, STAGED, BOT, "Jane Doe")

    result = _add(cli, repo)

    assert result.exit_code == 1
    assert f"origin/{STAGED}" in _said(result)
    assert "Jane Doe" in _said(result)
    assert not standard_dir.exists()
    assert _branches(repo) == ["main"]


def test_an_unset_slug_refuses_a_staged_branch_and_names_the_setting(
    cli: Cli, repo: Path, origin: Path, tmp_path: Path, standard_dir: Path
) -> None:
    _push_branch(origin, tmp_path, STAGED, BOT)

    result = _add(cli, repo)

    assert result.exit_code == 1
    assert f"origin/{STAGED}" in _said(result)
    assert "service.github_app.slug" in _said(result)
    assert not standard_dir.exists()
    assert _branches(repo) == ["main"]


@pytest.mark.usefixtures("app")
def test_the_type_and_the_slug_come_from_the_staged_branch(
    cli: Cli, repo: Path, origin: Path, tmp_path: Path, standard_dir: Path
) -> None:
    _push_branch(origin, tmp_path, STAGED, BOT)

    result = _add_by_issue(cli, repo, "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["branch"] == STAGED


@pytest.mark.usefixtures("app")
def test_a_type_and_a_slug_that_match_the_staged_branch_are_accepted(
    cli: Cli, repo: Path, origin: Path, tmp_path: Path, standard_dir: Path
) -> None:
    _push_branch(origin, tmp_path, STAGED, BOT)

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert standard_dir.is_dir()


@pytest.mark.usefixtures("app")
@pytest.mark.parametrize(
    ("type_", "slug", "option"), [("feat", "other", "slug"), ("fix", "worktrees-add", "type")]
)
def test_a_type_or_a_slug_that_differs_from_the_staged_branch_is_an_error(
    cli: Cli,
    repo: Path,
    origin: Path,
    tmp_path: Path,
    standard_dir: Path,
    type_: str,
    slug: str,
    option: str,
) -> None:
    _push_branch(origin, tmp_path, STAGED, BOT)

    result = _add(cli, repo, type_=type_, slug=slug)

    assert result.exit_code == 1
    assert f"origin/{STAGED}" in _said(result)
    assert f"Its {option} is" in _said(result)
    assert not standard_dir.exists()
    assert _branches(repo) == ["main"]


@pytest.mark.usefixtures("app")
def test_two_branches_of_origin_for_the_issue_hold_it(
    cli: Cli, repo: Path, origin: Path, tmp_path: Path, standard_dir: Path
) -> None:
    _push_branch(origin, tmp_path, STAGED, BOT)
    _push_branch(origin, tmp_path, "fix/2337-other", BOT)

    result = _add(cli, repo)

    assert result.exit_code == 1
    assert f"origin/{STAGED}" in _said(result)
    assert "origin/fix/2337-other" in _said(result)
    assert not standard_dir.exists()


@pytest.mark.parametrize("extra", [("--type", "feat"), ("--slug", "x"), ()])
def test_a_missing_type_or_slug_without_a_branch_of_origin_is_an_error(
    cli: Cli, repo: Path, standard_dir: Path, extra: tuple[str, ...]
) -> None:
    result = _add_by_issue(cli, repo, *extra)

    assert result.exit_code == 1
    assert "--type" in _said(result)
    assert "--slug" in _said(result)
    assert not standard_dir.exists()
    assert _branches(repo) == ["main"]
