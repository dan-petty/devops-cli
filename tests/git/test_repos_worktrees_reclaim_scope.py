"""Tests for the scope of the reclaim that `devops repos worktrees add` runs first (#4092).

The reclaim removes a worktree only under the folder that `add` manages (`agent/worktrees` of the
data directory), only when its branch is merged, and only when it holds no uncommitted file and no
file that `.gitignore` hides. It names each worktree that it removes, and each one that it leaves
because it is outside the folder or holds an ignored file. The repositories are real, in
`tmp_path`; `origin` is a bare repository at `example-org/app.git`, so git reaches no network.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.git.worktree_inventory import directory_size
from devops_cli.output import format_bytes
from tests.support.fakes.github import github_json

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

# The command also claims the issue on the roadmap (#2910). The roadmap is in memory.
pytestmark = pytest.mark.usefixtures("roadmap_store")

Git = Callable[..., None]
Cli = Callable[..., Any]

PULLS_PATH = "/repos/example-org/app/commits/{sha}/pulls?per_page=100"
OUTSIDE = "outside the managed folder"


@pytest.fixture
def new_dir(managed: Path) -> Path:
    """Where the worktree of issue 2345 goes."""
    return managed / "w-2345"


def _worktree(git: Git, repo: Path, branch: str, path: Path, *, gitignore: str = "") -> str:
    """Add a worktree on a new branch with one commit of its own; return its tip. A `gitignore`
    text becomes the committed `.gitignore` of the worktree."""
    git(repo, "worktree", "add", "-b", branch, str(path))
    (path / "work.txt").write_text(f"{branch}\n", encoding="utf-8")
    git(path, "add", "work.txt")
    if gitignore:
        (path / ".gitignore").write_text(gitignore, encoding="utf-8")
        git(path, "add", ".gitignore")
    git(path, "commit", "-m", f"work on {branch}")
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _merged(api: GitHubApiFake, tip: str, number: int = 2134) -> None:
    """Answer the lookup of `tip` with a merged pull request headed by it."""
    pull = {
        "number": number,
        "state": "closed",
        "merged_at": "2026-10-24T18:35:41Z",
        "head": {"sha": tip, "ref": "branch"},
    }
    api.route("GET", PULLS_PATH.format(sha=tip), github_json([pull]))


def _listed(repo: Path) -> str:
    """What `git worktree list` says of the repository."""
    return subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _add(cli: Cli, repo: Path, *extra: str) -> Any:
    return cli(
        "repos",
        "worktrees",
        "add",
        "2345",
        "--type",
        "feat",
        "--slug",
        "next",
        "--repo-dir",
        str(repo),
        *extra,
    )


def _said(result: Any) -> str:
    """The output of a run, with each run of white space as one space."""
    return " ".join(result.output.split())


def test_worktree_outside_managed_folder_is_kept(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, github_api: GitHubApiFake, new_dir: Path
) -> None:
    outside = tmp_path / "wt_outside"
    _merged(github_api, _worktree(git, repo, "fix/2100-other", outside))

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert (outside.is_dir(), github_api.requested, new_dir.is_dir()) == (True, [], True)
    assert str(outside) in _said(result)
    assert OUTSIDE in _said(result)


def test_merged_clean_worktree_inside_folder_is_removed_and_named(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake, new_dir: Path
) -> None:
    inside = managed / "w-2100"
    _merged(github_api, _worktree(git, repo, "fix/2100-old", inside))
    shown = format_bytes(directory_size(inside))

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert (inside.exists(), new_dir.is_dir()) == (False, True)
    assert f"removed {inside} ({shown})" in _said(result)


def test_ignored_file_keeps_worktree(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake, new_dir: Path
) -> None:
    kept = managed / "w-2100"
    _merged(github_api, _worktree(git, repo, "fix/2100-old", kept, gitignore="*.log\n"))
    (kept / "keep.log").write_text("hours of work\n", encoding="utf-8")
    status = subprocess.run(
        ["git", "-C", str(kept), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert status == "", "the file must be hidden from `git status`"

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert ((kept / "keep.log").is_file(), new_dir.is_dir()) == (True, True)
    assert str(kept) in _said(result)
    assert "ignored" in _said(result)


def test_missing_directory_outside_folder_is_kept(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, github_api: GitHubApiFake, new_dir: Path
) -> None:
    gone = tmp_path / "wt_gone"
    _worktree(git, repo, "fix/2100-other", gone)
    shutil.rmtree(gone)
    assert "prunable" in _listed(repo), "git must list the record as prunable"

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert str(gone) in _listed(repo)
    assert github_api.requested == []
    assert str(gone) in _said(result)
    assert OUTSIDE in _said(result)
    assert new_dir.is_dir()


def test_missing_directory_inside_folder_is_removed_without_a_read(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake, new_dir: Path
) -> None:
    gone = managed / "w-2100"
    _worktree(git, repo, "fix/2100-old", gone)
    shutil.rmtree(gone)

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert str(gone) not in _listed(repo)
    assert github_api.requested == []
    assert new_dir.is_dir()


def test_json_report_lists_each_kept_worktree_with_its_reason(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, managed: Path, github_api: GitHubApiFake
) -> None:
    outside = tmp_path / "wt_outside"
    _worktree(git, repo, "fix/2100-other", outside)
    ignored = managed / "w-2101"
    _worktree(git, repo, "fix/2101-old", ignored, gitignore="*.log\n")
    (ignored / "keep.log").write_text("hours of work\n", encoding="utf-8")

    result = _add(cli, repo, "--json")

    kept = {item["path"]: item for item in json.loads(result.stdout)["kept"]}
    assert result.exit_code == 0, result.output
    assert set(kept) == {str(outside), str(ignored)}
    assert kept[str(outside)]["reason"] == OUTSIDE
    assert "ignored" in kept[str(ignored)]["reason"]
    assert github_api.requested == []


def test_worktree_whose_status_fails_is_kept(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake, new_dir: Path
) -> None:
    broken = managed / "w-2100"
    _merged(github_api, _worktree(git, repo, "fix/2100-old", broken))
    (broken / ".git").write_text("not a gitdir file\n", encoding="utf-8")

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert (broken.is_dir(), github_api.requested, new_dir.is_dir()) == (True, [], True)
    assert "git status failed" in _said(result)


def test_the_dry_run_lists_a_read_only_for_a_worktree_inside_the_folder(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, managed: Path, github_api: GitHubApiFake
) -> None:
    _worktree(git, repo, "fix/2100-other", tmp_path / "wt_outside")
    inside_tip = _worktree(git, repo, "fix/2101-old", managed / "w-2101")

    result = _add(cli, repo, "--dry-run", "--json")

    report = json.loads(result.stdout)
    assert result.exit_code == 0, result.output
    assert github_api.requested == []
    reads = [line for line in report["requests"] if "/commits/" in line]
    assert reads == [f"GET /repos/example-org/app/commits/{inside_tip}/pulls"]


def test_prune_keeps_its_scope_and_removes_a_merged_worktree_outside_the_folder(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, github_api: GitHubApiFake
) -> None:
    outside = tmp_path / "wt_outside"
    _merged(github_api, _worktree(git, repo, "fix/2100-other", outside))

    result = cli("repos", "worktrees", "prune", "--confirm", "--repo-dir", str(repo))

    assert result.exit_code == 0, result.output
    assert not outside.exists()
    assert f"removed {outside}" in _said(result)
