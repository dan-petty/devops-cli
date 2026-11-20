"""Tests for the scope rule of `devops repos worktrees prune` and of the reclaim that
`devops repos worktrees add` runs first (#4092, #6435). Both ask one function, `scope_refusal`.

The reclaim removes a worktree only under the folder that `add` manages (`agent/worktrees` of the
data directory), only when its branch is merged, and only when it holds no uncommitted file and no
ignored data file: a file that `.gitignore` hides and that no regenerable cache holds (#6435). It
names each worktree that it removes, and each one that it leaves because it is outside the folder
or holds an ignored data file. Prune refuses the same worktrees unless `--force` is given. The
repositories are real, in `tmp_path`; `origin` is a bare
repository at `example-org/app.git`, so git reaches no network.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.git.worktree_inventory import (
    directory_size,
    inventory_worktrees,
    scope_refusal,
)
from devops_cli.output import format_bytes
from tests.support.fakes.github import github_json

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

# The command also claims the issue on the roadmap (#2910). The roadmap is in memory.
pytestmark = pytest.mark.usefixtures("roadmap_store")

Git = Callable[..., None]
Cli = Callable[..., Any]

PULLS_PATH = "/repos/example-org/app/commits/{sha}/pulls?per_page=100"
OUTSIDE = "outside the managed folder {folder}"
# The committed `.gitignore` of a worktree that holds caches and data, as the repository hides them.
GITIGNORE = ".venv\n__pycache__/\n.pytest_cache/\n.data/*\n.env.*\n"
# Regenerable caches: a command makes each one again, so none of them is data.
CACHES = (".venv/x", "src/pkg/__pycache__/m.pyc", ".pytest_cache/v")
NOTE = ".data/agent/scratch/note.md"


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


def _prune(cli: Cli, repo: Path, *extra: str) -> tuple[Any, dict[str, tuple[str, str | None]]]:
    """Run prune with `--json`; return the run and each worktree's status and reason by path."""
    result = cli("repos", "worktrees", "prune", "--json", "--repo-dir", str(repo), *extra)
    items = json.loads(result.stdout)["items"]
    return result, {item["path"]: (item["status"], item["reason"]) for item in items}


def _said(result: Any) -> str:
    """The output of a run, with each run of white space as one space."""
    return " ".join(result.output.split())


def _put(worktree: Path, *names: str) -> None:
    """Write one small file at each path of `names` under `worktree`."""
    for name in names:
        target = worktree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{name}\n", encoding="utf-8")


def _worktree_with(git: Git, repo: Path, branch: str, path: Path, *names: str) -> str:
    """Add a worktree whose `.gitignore` is `GITIGNORE` and put the files of `names` in it."""
    tip = _worktree(git, repo, branch, path, gitignore=GITIGNORE)
    _put(path, *names)
    return tip


def test_worktree_outside_managed_folder_is_kept(
    cli: Cli,
    repo: Path,
    git: Git,
    tmp_path: Path,
    managed: Path,
    github_api: GitHubApiFake,
    new_dir: Path,
) -> None:
    outside = tmp_path / "wt_outside"
    _merged(github_api, _worktree(git, repo, "fix/2100-other", outside))

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert (outside.is_dir(), github_api.requested, new_dir.is_dir()) == (True, [], True)
    assert f"kept {outside}: {OUTSIDE.format(folder=managed)}" in _said(result)


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
    assert f"kept {kept}: holds 1 ignored data file" in _said(result)


def test_missing_directory_outside_folder_is_kept(
    cli: Cli,
    repo: Path,
    git: Git,
    tmp_path: Path,
    managed: Path,
    github_api: GitHubApiFake,
    new_dir: Path,
) -> None:
    gone = tmp_path / "wt_gone"
    _worktree(git, repo, "fix/2100-other", gone)
    shutil.rmtree(gone)
    assert "prunable" in _listed(repo), "git must list the record as prunable"

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert str(gone) in _listed(repo)
    assert github_api.requested == []
    assert f"kept {gone}: {OUTSIDE.format(folder=managed)}" in _said(result)
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
    assert kept[str(outside)]["reason"] == OUTSIDE.format(folder=managed)
    assert kept[str(ignored)]["reason"] == "holds 1 ignored data file"
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
    assert f"kept {broken}: ignored data files are unknown (git ls-files failed)" in _said(result)


def test_scope_refusal_names_the_folder_and_the_data_count(
    repo: Path, git: Git, tmp_path: Path, managed: Path
) -> None:
    """The shared rule refuses a worktree outside the folder and one that holds data files, and
    allows one that holds only caches, an empty directory or nothing at all (#6435)."""
    _worktree_with(git, repo, "fix/2100-other", tmp_path / "wt_outside")
    _worktree_with(git, repo, "fix/2101-one", managed / "w-2101", *CACHES, NOTE)
    three = (NOTE, ".data/agent/scratch/other.md", ".env.local")
    _worktree_with(git, repo, "fix/2102-three", managed / "w-2102", *three)
    caches = managed / "w-2103"
    _worktree_with(git, repo, "fix/2103-caches", caches, *CACHES, ".data/cache/x")
    (caches / ".data" / "agent" / "empty").mkdir(parents=True)
    gone = managed / "w-2104"
    _worktree_with(git, repo, "fix/2104-gone", gone)
    shutil.rmtree(gone)
    entries = {Path(entry.path).name: entry for entry in inventory_worktrees(repo)}

    refusals = {
        name: scope_refusal(entries[name], managed_root=managed)
        for name in ("wt_outside", "w-2101", "w-2102", "w-2103", "w-2104")
    }

    assert refusals == {
        "wt_outside": OUTSIDE.format(folder=managed),
        "w-2101": "holds 1 ignored data file",
        "w-2102": "holds 3 ignored data files",
        "w-2103": None,
        "w-2104": None,
    }


@pytest.mark.parametrize("names", [CACHES, (".data/cache/x",)], ids=["caches", "data-cache"])
def test_the_reclaim_takes_a_merged_worktree_that_holds_only_caches(
    cli: Cli,
    repo: Path,
    git: Git,
    managed: Path,
    github_api: GitHubApiFake,
    new_dir: Path,
    names: tuple[str, ...],
) -> None:
    """A regenerable cache holds no data, so it keeps no merged worktree (#6435)."""
    old = managed / "w-2100"
    _merged(github_api, _worktree_with(git, repo, "fix/2100-old", old, *names))

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert (old.exists(), new_dir.is_dir()) == (False, True)
    assert f"removed {old}" in _said(result)


@pytest.mark.parametrize(
    "names", [(*CACHES, NOTE), (".env.local",)], ids=["scratch-note", "env-file"]
)
def test_the_reclaim_keeps_a_merged_worktree_that_holds_data(
    cli: Cli,
    repo: Path,
    git: Git,
    managed: Path,
    github_api: GitHubApiFake,
    new_dir: Path,
    names: tuple[str, ...],
) -> None:
    """Each ignored file that no cache holds is data: the reclaim keeps the worktree and counts
    only that file (#6435)."""
    kept = managed / "w-2100"
    _merged(github_api, _worktree_with(git, repo, "fix/2100-old", kept, *names))

    result = _add(cli, repo, "--json")

    reasons = {item["path"]: item["reason"] for item in json.loads(result.stdout)["kept"]}
    assert result.exit_code == 0, result.output
    assert reasons == {str(kept): "holds 1 ignored data file"}
    assert [(kept / name).is_file() for name in names] == [True] * len(names)
    assert (github_api.requested, new_dir.is_dir()) == ([], True)


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


@pytest.mark.parametrize("names", [CACHES, (".data/cache/x",)], ids=["caches", "data-cache"])
def test_prune_removes_a_merged_worktree_that_holds_only_caches(
    cli: Cli,
    repo: Path,
    git: Git,
    managed: Path,
    github_api: GitHubApiFake,
    names: tuple[str, ...],
) -> None:
    old = managed / "w-2100"
    _merged(github_api, _worktree_with(git, repo, "fix/2100-old", old, *names))

    result, outcomes = _prune(cli, repo, "--confirm")

    assert result.exit_code == 0, result.output
    assert (outcomes[str(old)], old.exists()) == (("removed", None), False)


@pytest.mark.parametrize(
    "names", [(*CACHES, NOTE), (".env.local",)], ids=["scratch-note", "env-file"]
)
def test_prune_refuses_a_merged_worktree_that_holds_data(
    cli: Cli,
    repo: Path,
    git: Git,
    managed: Path,
    github_api: GitHubApiFake,
    names: tuple[str, ...],
) -> None:
    """`git worktree remove` deletes the ignored files of a worktree, so prune keeps one that
    holds data and reads no pull request for it (#6435)."""
    kept = managed / "w-2100"
    _merged(github_api, _worktree_with(git, repo, "fix/2100-old", kept, *names))

    preview, previewed = _prune(cli, repo)
    result, outcomes = _prune(cli, repo, "--confirm")

    refused = ("refused", "holds 1 ignored data file")
    assert (preview.exit_code, result.exit_code) == (0, 0), result.output
    assert (previewed[str(kept)], outcomes[str(kept)]) == (refused, refused)
    assert [(kept / name).is_file() for name in names] == [True] * len(names)
    assert github_api.requested == []


def test_prune_refuses_a_merged_worktree_outside_the_managed_folder(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, managed: Path, github_api: GitHubApiFake
) -> None:
    """A worktree outside the managed folder belongs to another tool: prune names the folder and
    reads nothing for it, and its dry run lists no request for it (#6435)."""
    outside = tmp_path / "wt_outside"
    _merged(github_api, _worktree(git, repo, "fix/2100-other", outside))

    plan = cli("repos", "worktrees", "prune", "--dry-run", "--json", "--repo-dir", str(repo))
    result, outcomes = _prune(cli, repo, "--confirm")

    planned = json.loads(plan.stdout)
    refused = ("refused", OUTSIDE.format(folder=managed))
    assert (plan.exit_code, result.exit_code) == (0, 0), result.output
    assert (outcomes[str(outside)], outside.is_dir()) == (refused, True)
    assert (planned["requests"], github_api.requested) == ([], [])
    assert {item["path"]: item["reason"] for item in planned["items"]}[str(outside)] == refused[1]


def test_prune_keeps_the_record_of_a_missing_directory_outside_the_managed_folder(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, managed: Path, github_api: GitHubApiFake
) -> None:
    """A directory can look missing from this container while another container or tool still
    uses it, so prune keeps the record of a worktree outside the folder, as the reclaim does."""
    gone = tmp_path / "wt_gone"
    _worktree(git, repo, "fix/2100-other", gone)
    shutil.rmtree(gone)
    assert "prunable" in _listed(repo), "git must list the record as prunable"

    result, outcomes = _prune(cli, repo, "--confirm")

    assert result.exit_code == 0, result.output
    assert outcomes[str(gone)] == ("refused", OUTSIDE.format(folder=managed))
    assert (str(gone) in _listed(repo), github_api.requested) == (True, [])


def test_prune_refuses_a_worktree_whose_ignored_files_are_unknown(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake
) -> None:
    broken = managed / "w-2100"
    _merged(github_api, _worktree(git, repo, "fix/2100-old", broken))
    (broken / ".git").write_text("not a gitdir file\n", encoding="utf-8")

    result, outcomes = _prune(cli, repo, "--confirm")

    reason = "ignored data files are unknown (git ls-files failed)"
    assert result.exit_code == 0, result.output
    assert (outcomes[str(broken)], broken.is_dir()) == (("refused", reason), True)
    assert github_api.requested == []


def test_prune_and_the_reclaim_give_the_reason_of_scope_refusal(
    cli: Cli, repo: Path, git: Git, tmp_path: Path, managed: Path, github_api: GitHubApiFake
) -> None:
    """One function decides the scope of both commands, so they cannot drift (#6435)."""
    outside = tmp_path / "wt_outside"
    _worktree_with(git, repo, "fix/2100-other", outside)
    noted = managed / "w-2101"
    _worktree_with(git, repo, "fix/2101-old", noted, NOTE)
    entries = {entry.path: entry for entry in inventory_worktrees(repo)}
    expected = {
        path: scope_refusal(entries[path], managed_root=managed)
        for path in (str(outside), str(noted))
    }

    pruned, outcomes = _prune(cli, repo, "--confirm")
    added = _add(cli, repo, "--json")

    kept = {item["path"]: item["reason"] for item in json.loads(added.stdout)["kept"]}
    assert (pruned.exit_code, added.exit_code) == (0, 0), added.output
    assert {path: outcomes[path][1] for path in expected} == expected
    assert kept == expected
    assert expected == {
        str(outside): OUTSIDE.format(folder=managed),
        str(noted): "holds 1 ignored data file",
    }


def test_forced_prune_removes_a_refused_worktree_but_keeps_main_and_the_current_directory(
    cli: Cli,
    repo: Path,
    git: Git,
    tmp_path: Path,
    managed: Path,
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--force` stays the way to remove a worktree that the scope refuses (#6435)."""
    here = managed / "w-2100"
    _worktree_with(git, repo, "fix/2100-here", here, NOTE)
    noted = managed / "w-2101"
    _worktree_with(git, repo, "fix/2101-old", noted, NOTE)
    outside = tmp_path / "wt_outside"
    _worktree_with(git, repo, "fix/2102-other", outside, NOTE)
    monkeypatch.chdir(here)

    result, outcomes = _prune(cli, repo, "--confirm", "--force")

    assert result.exit_code == 0, result.output
    assert outcomes == {
        str(repo): ("refused", "main worktree"),
        str(here): ("refused", "current directory"),
        str(noted): ("removed", None),
        str(outside): ("removed", None),
    }
    assert [p.exists() for p in (repo, here, noted, outside)] == [True, True, False, False]
    assert github_api.requested == []
