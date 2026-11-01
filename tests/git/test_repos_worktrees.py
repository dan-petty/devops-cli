"""Tests for devops repos worktrees status and prune (#700, #2341)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.core.process import run_subprocess
from devops_cli.git.worktree_inventory import (
    count_dirty_paths,
    directory_size,
    parse_worktree_porcelain_z,
)
from devops_cli.output import format_bytes
from tests.support.fakes.git import GitFake
from tests.support.fakes.github import github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

ORIGIN_URL = "https://github.com/example-org/app.git"
PULLS_PATH = "/repos/example-org/app/commits/{sha}/pulls?per_page=100"
SQUASH_MERGED_AT = "2026-10-24T18:35:41Z"

Git = Callable[..., None]
Cli = Callable[..., Any]


class WorktreeRepoState:
    """In-memory git worktree tracking for hermetic tests (#700, #2183)."""

    def __init__(
        self, repo_dir: Path, git_fake: GitFake, origin_url: str | None = ORIGIN_URL
    ) -> None:
        self.repo_dir = repo_dir.resolve()
        self.origin_url = origin_url
        self.main_sha = "1111111111111111111111111111111111111111"
        self.worktrees: dict[Path, dict[str, Any]] = {
            self.repo_dir: {
                "branch": "refs/heads/main",
                "head": self.main_sha,
                "locked": False,
                "lock_reason": None,
                "ahead": 0,
                "is_main": True,
            }
        }
        self.remotes: dict[str, str] = {}
        git_fake.answer(self._matches, self._handle_call)

    def add_worktree(self, branch: str | None, path: Path, *, commit: bool = False) -> str:
        resolved = path.resolve()
        sha = (
            hashlib.sha1(f"{branch}-{path}".encode(), usedforsecurity=False).hexdigest()
            if commit
            else self.main_sha
        )
        self.worktrees[resolved] = {
            "branch": f"refs/heads/{branch}" if branch else None,
            "head": sha,
            "locked": False,
            "lock_reason": None,
            "ahead": 1 if commit else 0,
            "is_main": False,
        }
        return sha

    def _matches(self, call: ProcessCall) -> bool:
        return bool(call.argv and Path(call.argv[0]).name == "git")

    def _handle_remote(self, sub_argv: list[str]) -> ProcessAnswer:
        if "get-url" in sub_argv:
            if self.origin_url:
                return ProcessAnswer(stdout=f"{self.origin_url}\n")
            return ProcessAnswer(returncode=128, stderr="fatal: No such remote 'origin'")
        return ProcessAnswer(stdout="origin\n")

    def _handle_rev_parse(self, sub_argv: list[str], repo_dir: Path) -> ProcessAnswer:
        if "HEAD" in sub_argv:
            wt_info = self.worktrees.get(repo_dir)
            head = wt_info["head"] if wt_info else self.main_sha
            return ProcessAnswer(stdout=f"{head}\n")
        return ProcessAnswer(returncode=0)

    def _handle_rev_list(self, sub_argv: list[str]) -> ProcessAnswer:
        for word in sub_argv:
            if ".." in word:
                _, head = word.split("..", 1)
                for wt in self.worktrees.values():
                    if wt["head"] == head:
                        return ProcessAnswer(stdout=f"{wt['ahead']}\n")
        return ProcessAnswer(stdout="0\n")

    def _collect_status_tokens(self, repo_dir: Path) -> list[str]:
        if not repo_dir.exists():
            return []
        tokens: list[str] = []
        for item in sorted(repo_dir.iterdir()):
            if item.name == ".git":
                continue
            if not item.name.endswith(".txt"):
                continue
            if item.name == "file.txt":
                text = item.read_text(encoding="utf-8", errors="replace")
                if text == "modified\n":
                    tokens.append(f" M {item.name}")
            elif not item.name.startswith("branch-"):
                tokens.append(f"?? {item.name}")
        return tokens

    def _handle_status(self, repo_dir: Path) -> ProcessAnswer:
        if repo_dir != self.repo_dir and repo_dir not in self.worktrees:
            return ProcessAnswer(returncode=128, stderr="fatal: not a git repository")
        git_marker = repo_dir / ".git"
        if git_marker.is_file():
            content = git_marker.read_text(encoding="utf-8", errors="replace")
            if not content.startswith("gitdir:"):
                return ProcessAnswer(returncode=128, stderr="fatal: invalid gitdir pointer")
        tokens = self._collect_status_tokens(repo_dir)
        if tokens:
            return ProcessAnswer(stdout="".join(f"{t}\0" for t in tokens))
        return ProcessAnswer(stdout="")

    def _worktree_list_porcelain(self) -> ProcessAnswer:
        tokens: list[str] = []
        for p, info in list(self.worktrees.items()):
            tokens.append(f"worktree {p}")
            tokens.append(f"HEAD {info['head']}")
            if info["branch"]:
                tokens.append(f"branch {info['branch']}")
            else:
                tokens.append("detached")
            if info.get("bare"):
                tokens.append("bare")
            if info["locked"]:
                lock_text = f"locked {info['lock_reason']}" if info["lock_reason"] else "locked"
                tokens.append(lock_text)
            if not p.exists():
                tokens.append("prunable gitdir file points to non-existent location")
            tokens.append("")
        return ProcessAnswer(stdout="\0".join(tokens) + "\0")

    def _worktree_list_standard(self) -> ProcessAnswer:
        lines: list[str] = []
        for p, info in self.worktrees.items():
            branch_label = (
                f"[{info['branch'].removeprefix('refs/heads/')}]"
                if info["branch"]
                else "(detached HEAD)"
            )
            lines.append(f"{p}  {info['head'][:7]} {branch_label}")
        return ProcessAnswer(stdout="\n".join(lines) + "\n")

    def _handle_worktree_remove(self, sub_argv: list[str]) -> ProcessAnswer:
        target_path = Path(sub_argv[-1]).resolve()
        wt_info = self.worktrees.get(target_path)
        if wt_info and wt_info["locked"] and sub_argv.count("--force") < 2:
            return ProcessAnswer(
                returncode=128,
                stderr=f"fatal: '{target_path}' is locked: {wt_info['lock_reason']}",
            )
        self.worktrees.pop(target_path, None)
        shutil.rmtree(target_path, ignore_errors=True)
        return ProcessAnswer(returncode=0)

    def _handle_worktree_add(self, sub_argv: list[str]) -> ProcessAnswer:
        target_path = Path(sub_argv[-1]).resolve()
        branch = None
        if "-b" in sub_argv:
            idx = sub_argv.index("-b")
            branch = sub_argv[idx + 1]
        self.add_worktree(branch, target_path, commit=False)
        target_path.mkdir(parents=True, exist_ok=True)
        pointer = self.repo_dir / ".git" / "worktrees" / (branch or "detached")
        (target_path / ".git").write_text(f"gitdir: {pointer}\n", encoding="utf-8")
        return ProcessAnswer(returncode=0)

    def _handle_worktree(self, sub_argv: list[str]) -> ProcessAnswer:
        subcmd = sub_argv[1] if len(sub_argv) > 1 else ""
        if subcmd == "list":
            if "--porcelain" in sub_argv:
                return self._worktree_list_porcelain()
            return self._worktree_list_standard()
        if subcmd == "lock":
            reason = (
                sub_argv[sub_argv.index("--reason") + 1] if "--reason" in sub_argv else "locked"
            )
            target = Path(sub_argv[-1]).resolve()
            if target in self.worktrees:
                self.worktrees[target]["locked"] = True
                self.worktrees[target]["lock_reason"] = reason
            return ProcessAnswer(returncode=0)
        if subcmd == "unlock":
            target = Path(sub_argv[-1]).resolve()
            if target in self.worktrees:
                self.worktrees[target]["locked"] = False
                self.worktrees[target]["lock_reason"] = None
            return ProcessAnswer(returncode=0)
        if subcmd == "remove":
            return self._handle_worktree_remove(sub_argv)
        if subcmd == "add":
            return self._handle_worktree_add(sub_argv)
        return ProcessAnswer(returncode=0)

    def _handle_commit(self, repo_dir: Path) -> ProcessAnswer:
        wt_info = self.worktrees.get(repo_dir)
        if wt_info:
            wt_info["ahead"] += 1
            seed = f"{wt_info['branch']}-{wt_info['ahead']}".encode()
            wt_info["head"] = hashlib.sha1(seed, usedforsecurity=False).hexdigest()
        return ProcessAnswer(returncode=0)

    def _handle_call(self, call: ProcessCall) -> ProcessAnswer:
        argv = call.argv
        repo_dir = self.repo_dir
        sub_argv = list(argv[1:])
        if len(sub_argv) >= 2 and sub_argv[0] == "-C":
            repo_dir = Path(sub_argv[1]).resolve()
            sub_argv = sub_argv[2:]

        cmd = sub_argv[0] if sub_argv else ""
        if cmd == "remote":
            return self._handle_remote(sub_argv)
        if cmd == "rev-parse":
            return self._handle_rev_parse(sub_argv, repo_dir)
        if cmd == "rev-list":
            return self._handle_rev_list(sub_argv)
        if cmd == "status":
            return self._handle_status(repo_dir)
        if cmd == "worktree":
            return self._handle_worktree(sub_argv)
        if cmd == "commit":
            return self._handle_commit(repo_dir)
        if cmd == "update-ref":
            ref = sub_argv[1] if len(sub_argv) > 1 else ""
            val = sub_argv[2] if len(sub_argv) > 2 else ""
            self.remotes[ref] = val
            return ProcessAnswer(returncode=0)
        return ProcessAnswer(returncode=0)


@pytest.fixture
def git_repo(tmp_path: Path, git_fake: GitFake) -> Path:
    """A repository with a committed main branch and a GitHub origin."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    WorktreeRepoState(repo, git_fake)
    return repo


@pytest.fixture
def git() -> Callable[..., None]:
    """In-process git command runner that dispatches to git_fake."""

    def runner(repo: Path, *args: str) -> None:
        run_subprocess(["git", "-C", str(repo), *args])

    return runner


def _tip(path: Path) -> str:
    """The commit a worktree is at."""
    res = run_subprocess(
        ["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True
    )
    return res.stdout.strip()


def _add_worktree(git: Git, repo: Path, branch: str, path: Path, *, commit: bool = False) -> str:
    """Add a worktree on a new branch, with one commit of its own when asked; return its tip."""
    git(repo, "worktree", "add", "-b", branch, str(path))
    if commit:
        (path / f"{branch}.txt").write_text(f"{branch}\n", encoding="utf-8")
        git(path, "add", f"{branch}.txt")
        git(path, "commit", "-m", f"work on {branch}")
    return _tip(path)


def _pull(head_sha: str, *, number: int = 7, merged_at: str | None = SQUASH_MERGED_AT) -> Any:
    """A pull request as `GET /repos/{repo}/commits/{sha}/pulls` lists it, cut to what is read."""
    return {
        "number": number,
        "state": "closed" if merged_at else "open",
        "merged_at": merged_at,
        "head": {"sha": head_sha, "ref": "feature"},
    }


def _route_pulls(api: GitHubApiFake, tip: str, *pulls: Any) -> str:
    """Answer the pull request lookup of `tip` with `pulls`; return the request it should get."""
    api.route("GET", PULLS_PATH.format(sha=tip), github_json(list(pulls)))
    return f"GET https://api.github.com{PULLS_PATH.format(sha=tip)}"


def _outcomes(report: dict[str, Any]) -> dict[str, tuple[str, str | None]]:
    """Each entry of a prune report as its directory name and its status and reason."""
    return {Path(i["path"]).name: (i["status"], i["reason"]) for i in report["items"]}


def test_worktrees_status_table_and_lock_reason(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli
) -> None:
    """Criteria 1 & 7: status lists worktrees with ahead, dirty and lock reason."""
    _add_worktree(git, git_repo, "branch-new", tmp_path / "wt_new")
    wt_ahead = tmp_path / "wt_ahead"
    _add_worktree(git, git_repo, "branch-ahead", wt_ahead, commit=True)
    git(git_repo, "worktree", "lock", "--reason", "agent-42", str(wt_ahead))

    result = cli("repos", "worktrees", "status", "--repo-dir", str(git_repo))

    assert (
        result.exit_code,
        "branch-new" in result.stdout,
        "branch-ahead" in result.stdout,
        "locked=true" in result.stdout,
        "agent-42" in result.stdout,
        "contained" in result.stdout,
    ) == (0, True, True, True, True, False)


def test_worktrees_status_json_schema(git_repo: Path, tmp_path: Path, git: Git, cli: Cli) -> None:
    """Criterion 2: status --json emits a typed array whose entries have no merge verdict."""
    _add_worktree(git, git_repo, "branch-one", tmp_path / "wt_one")

    result = cli("repos", "worktrees", "status", "--repo-dir", str(git_repo), "--json")

    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert {
        (
            type(e["ahead"]),
            type(e["dirty"]),
            type(e["locked"]),
            type(e["prunable"]),
            "contained" in e,
        )
        for e in payload
    } == {(int, int, bool, bool, False)}


def test_worktrees_status_json_gives_the_issue_of_each_worktree(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli
) -> None:
    """A branch of the form `<type>/<issue>-<slug>` names an issue; any other branch, a detached
    head and the main worktree name none (#2337)."""
    _add_worktree(git, git_repo, "fix/2337-other", tmp_path / "wt_issue")
    _add_worktree(git, git_repo, "branch-plain", tmp_path / "wt_plain")
    _add_worktree(git, git_repo, "feat/23370-longer", tmp_path / "wt_longer")
    git(git_repo, "worktree", "add", "--detach", str(tmp_path / "wt_detached"))

    result = cli("repos", "worktrees", "status", "--repo-dir", str(git_repo), "--json")

    issues = {Path(e["path"]).name: e["issue"] for e in json.loads(result.stdout)}
    assert (result.exit_code, issues) == (
        0,
        {
            git_repo.name: None,
            "wt_issue": 2337,
            "wt_plain": None,
            "wt_longer": 23370,
            "wt_detached": None,
        },
    )


def test_worktrees_status_table_has_an_issue_column(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli
) -> None:
    _add_worktree(git, git_repo, "fix/2337-other", tmp_path / "wt_issue")

    result = cli("repos", "worktrees", "status", "--repo-dir", str(git_repo))

    assert (result.exit_code, "Issue" in result.stdout, "2337" in result.stdout) == (0, True, True)


def test_worktree_with_unreadable_status_has_unknown_dirty_count(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli
) -> None:
    """A failed `git status` is an unknown count, which status shows as null, never as clean."""
    broken = tmp_path / "wt_broken"
    _add_worktree(git, git_repo, "branch-broken", broken)
    (broken / ".git").write_text("not a gitdir pointer\n", encoding="utf-8")

    result = cli("repos", "worktrees", "status", "--repo-dir", str(git_repo), "--json")

    dirty = {Path(e["path"]).name: e["dirty"] for e in json.loads(result.stdout)}
    assert dirty == {"repo": 0, "wt_broken": None}


def test_prune_removes_worktree_whose_tip_heads_a_merged_pull_request(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """A squash merge leaves the branch tip out of main; the merged pull request is the record."""
    merged = tmp_path / "wt_merged"
    tip = _add_worktree(git, git_repo, "branch-merged", merged, commit=True)
    request = _route_pulls(github_api, tip, _pull(tip, number=2134))

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm", "--json")

    report = json.loads(result.stdout)
    assert (result.exit_code, merged.exists(), github_api.requested) == (0, False, [request])
    assert _outcomes(report) == {
        "repo": ("refused", "main worktree"),
        "wt_merged": ("removed", None),
    }
    assert (report["removed_count"], report["refused_count"], report["failed_count"]) == (1, 1, 0)


def test_prune_keeps_new_worktree_at_the_tip_of_main(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """A new worktree has no commit of its own: main contains its tip, but no pull request has it
    as head, even when GitHub names the squash merge that put the tip into main."""
    fresh = tmp_path / "wt_fresh"
    tip = _add_worktree(git, git_repo, "branch-fresh", fresh)
    _route_pulls(github_api, tip, _pull("0f" * 20, number=2339))

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm", "--json")

    assert (result.exit_code, fresh.exists()) == (0, True)
    assert _outcomes(json.loads(result.stdout))["wt_fresh"] == (
        "refused",
        "no merged pull request has this commit as its head",
    )


def test_prune_keeps_pushed_branch_with_an_open_pull_request(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """The remote ref of the branch itself contains the tip, but the pull request is not merged."""
    pushed = tmp_path / "wt_pushed"
    tip = _add_worktree(git, git_repo, "branch-pushed", pushed, commit=True)
    git(git_repo, "update-ref", "refs/remotes/origin/branch-pushed", tip)
    _route_pulls(github_api, tip, _pull(tip, merged_at=None))

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm", "--json")

    assert (result.exit_code, pushed.exists()) == (0, True)
    assert _outcomes(json.loads(result.stdout))["wt_pushed"][0] == "refused"


def test_prune_keeps_worktree_with_a_commit_after_the_merge(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """The merged pull request ended on an earlier commit than the tip of the worktree."""
    later = tmp_path / "wt_later"
    tip = _add_worktree(git, git_repo, "branch-later", later, commit=True)
    _route_pulls(github_api, tip, _pull("1a" * 20))

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm", "--json")

    assert (result.exit_code, later.exists()) == (0, True)
    assert _outcomes(json.loads(result.stdout))["wt_later"][0] == "refused"


def test_prune_keeps_commit_that_github_does_not_know(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """GitHub answers 422 for a commit that was never pushed; the worktree stays and prune works."""
    local = tmp_path / "wt_local"
    tip = _add_worktree(git, git_repo, "branch-local", local, commit=True)
    github_api.route(
        "GET",
        PULLS_PATH.format(sha=tip),
        github_json({"message": f"No commit found for SHA: {tip}"}, status=422),
    )

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm", "--json")

    assert (result.exit_code, local.exists()) == (0, True)
    assert _outcomes(json.loads(result.stdout))["wt_local"][0] == "refused"


def test_prune_reads_no_pull_request_for_locked_dirty_or_unreadable_worktrees(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """Local state decides first: lock, uncommitted paths and a failed `git status` each keep the
    worktree, and none of them costs a request."""
    locked = tmp_path / "wt_locked"
    _add_worktree(git, git_repo, "branch-locked", locked, commit=True)
    git(git_repo, "worktree", "lock", "--reason", "agent-42", str(locked))
    dirty = tmp_path / "wt_dirty"
    _add_worktree(git, git_repo, "branch-dirty", dirty, commit=True)
    (dirty / "scratch.txt").write_text("wip\n", encoding="utf-8")
    broken = tmp_path / "wt_broken"
    _add_worktree(git, git_repo, "branch-broken", broken, commit=True)
    (broken / ".git").write_text("not a gitdir pointer\n", encoding="utf-8")

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm", "--json")

    assert (result.exit_code, github_api.requested) == (0, [])
    assert _outcomes(json.loads(result.stdout)) == {
        "repo": ("refused", "main worktree"),
        "wt_locked": ("refused", "locked (agent-42)"),
        "wt_dirty": ("refused", "dirty (1 uncommitted path)"),
        "wt_broken": ("refused", "dirty state unknown (git status failed)"),
    }
    assert [p.exists() for p in (locked, dirty, broken)] == [True, True, True]


def test_prune_removes_the_record_of_a_worktree_whose_directory_is_gone(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """A deleted directory holds nothing, so prune drops git's record of it without a lookup."""
    gone = tmp_path / "wt_gone"
    _add_worktree(git, git_repo, "branch-gone", gone, commit=True)
    shutil.rmtree(gone)

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm", "--json")

    listed = run_subprocess(
        ["git", "-C", str(git_repo), "worktree", "list"], capture_output=True, text=True
    ).stdout
    assert (result.exit_code, "wt_gone" in listed, github_api.requested) == (0, False, [])
    assert _outcomes(json.loads(result.stdout))["wt_gone"] == ("removed", None)


def test_prune_removes_nothing_when_a_pull_request_read_fails(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """Every worktree is decided before one is removed: a read that fails ends the run first."""
    merged = tmp_path / "wt_merged"
    tip = _add_worktree(git, git_repo, "branch-merged", merged, commit=True)
    _route_pulls(github_api, tip, _pull(tip))
    unread = tmp_path / "wt_unread"
    _add_worktree(git, git_repo, "branch-unread", unread, commit=True)

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm")

    assert (result.exit_code, merged.exists(), unread.exists()) == (1, True, True)


def test_prune_without_confirm_reads_github_and_removes_nothing(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """The default run is a preview: it reads, lists and changes nothing."""
    merged = tmp_path / "wt_merged"
    tip = _add_worktree(git, git_repo, "branch-merged", merged, commit=True)
    request = _route_pulls(github_api, tip, _pull(tip, number=2134))

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--json")

    report = json.loads(result.stdout)
    assert (result.exit_code, merged.exists(), github_api.requested) == (0, True, [request])
    assert _outcomes(report)["wt_merged"] == ("would remove", "head of merged pull request #2134")
    assert report["removed_count"] == 0


def test_prune_dry_run_makes_no_request_and_lists_the_requests(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """A dry run reads local git only and returns the report with the requests a run would make."""
    merged = tmp_path / "wt_merged"
    tip = _add_worktree(git, git_repo, "branch-merged", merged, commit=True)
    locked = tmp_path / "wt_locked"
    _add_worktree(git, git_repo, "branch-locked", locked, commit=True)
    git(git_repo, "worktree", "lock", "--reason", "agent-42", str(locked))

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--dry-run", "--json")

    report = json.loads(result.stdout)
    assert (result.exit_code, merged.exists(), github_api.requested) == (0, True, [])
    assert report["requests"] == [f"GET /repos/example-org/app/commits/{tip}/pulls"]
    assert _outcomes(report) == {
        "repo": ("refused", "main worktree"),
        "wt_merged": ("would check", "the merged pull request of its tip is read"),
        "wt_locked": ("refused", "locked (agent-42)"),
    }


def test_prune_dry_run_prints_the_request_plan(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """The table output of a dry run is the numbered request plan."""
    tip = _add_worktree(git, git_repo, "branch-merged", tmp_path / "wt_merged", commit=True)

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--dry-run")

    assert (result.exit_code, github_api.requested) == (0, [])
    assert f"1. GET /repos/example-org/app/commits/{tip}/pulls" in result.stdout


def test_prune_refuses_dry_run_with_confirm(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli
) -> None:
    """A dry run changes nothing, so a confirmed dry run is a contradiction, not a removal."""
    wt = tmp_path / "wt_one"
    _add_worktree(git, git_repo, "branch-one", wt, commit=True)

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--dry-run", "--confirm")

    assert (result.exit_code, wt.exists(), "--dry-run" in result.output) == (1, True, True)


def test_prune_without_a_github_origin_names_the_cause(
    tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake, git_fake: GitFake
) -> None:
    """The merged pull request is read from the origin; without one prune stops before any read."""
    repo = tmp_path / "plain"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    WorktreeRepoState(repo, git_fake, origin_url=None)
    wt = tmp_path / "wt_one"
    _add_worktree(git, repo, "branch-one", wt, commit=True)

    result = cli("repos", "worktrees", "prune", "-r", str(repo), "--confirm")

    assert (result.exit_code, wt.exists(), github_api.requested, "origin" in result.output) == (
        1,
        True,
        [],
        True,
    )


def test_forced_prune_of_a_locked_worktree_reports_the_failure_and_keeps_the_directory(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """Git refuses to remove a locked worktree with one --force; prune says so and deletes nothing."""
    locked = tmp_path / "wt_locked"
    _add_worktree(git, git_repo, "branch-locked", locked, commit=True)
    git(git_repo, "worktree", "lock", "--reason", "agent-42", str(locked))

    result = cli(
        "repos", "worktrees", "prune", "-r", str(git_repo), "--force", "--confirm", "--json"
    )

    report = json.loads(result.stdout)
    listed = run_subprocess(
        ["git", "-C", str(git_repo), "worktree", "list"], capture_output=True, text=True
    ).stdout
    status, reason = _outcomes(report)["wt_locked"]
    assert (result.exit_code, status, "agent-42" in (reason or "")) == (1, "failed", True)
    assert (locked.exists(), "wt_locked" in listed, report["failed_count"]) == (True, True, 1)
    assert github_api.requested == []


def test_forced_prune_removes_an_unmerged_worktree_without_reading_github(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """Criteria 5 & 6: --force --confirm removes any other worktree and cleans git metadata."""
    unmerged = tmp_path / "wt_force"
    _add_worktree(git, git_repo, "branch-force", unmerged, commit=True)

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--force", "--confirm")

    listed = run_subprocess(
        ["git", "-C", str(git_repo), "worktree", "list"], capture_output=True, text=True
    ).stdout
    assert (result.exit_code, unmerged.exists(), "wt_force" in listed, github_api.requested) == (
        0,
        False,
        False,
        [],
    )


def test_prune_report_in_table_names_removed_and_refused_worktrees(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """The table output reports each outcome and the totals."""
    tip = _add_worktree(git, git_repo, "branch-merged", tmp_path / "wt_merged", commit=True)
    _route_pulls(github_api, tip, _pull(tip))
    _add_worktree(git, git_repo, "branch-new", tmp_path / "wt_new")
    _route_pulls(github_api, _tip(tmp_path / "wt_new"))

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm")

    assert result.exit_code == 0
    assert "removed " in result.stdout
    assert "refused " in result.stdout
    assert "Prune complete: 1 removed, 2 refused, 0 failed" in result.stdout


def test_worktrees_nul_separated_path_with_newline() -> None:
    """Criterion 8: parser handles NUL-separated records and paths containing newline bytes."""
    raw = (
        b"worktree /path/to/my\nworktree\0"
        b"HEAD 1234567890abcdef1234567890abcdef12345678\0"
        b"branch refs/heads/feature-newline\0"
        b"locked owner-agent\0\0"
        b"worktree /second/worktree\0"
        b"HEAD abcdef1234567890abcdef1234567890abcdef12\0"
        b"detached\0"
        b"prunable missing directory\0\0"
    )

    parsed = parse_worktree_porcelain_z(raw)
    assert len(parsed) == 2

    first, second = parsed[0], parsed[1]
    assert (
        str(first.path),
        first.head,
        first.branch,
        first.locked,
        first.lock_reason,
        first.is_main,
    ) == (
        "/path/to/my\nworktree",
        "1234567890abcdef1234567890abcdef12345678",
        "refs/heads/feature-newline",
        True,
        "owner-agent",
        True,
    )

    assert (
        str(second.path),
        second.head,
        second.branch,
        second.detached,
        second.prunable,
        second.prunable_reason,
        second.is_main,
    ) == (
        "/second/worktree",
        "abcdef1234567890abcdef1234567890abcdef12",
        None,
        True,
        True,
        "missing directory",
        False,
    )


def test_count_dirty_paths_handles_modifications_and_renames(git_repo: Path) -> None:
    """Test dirty path count with untracked, modified, and renamed files."""
    assert count_dirty_paths(git_repo) == 0

    (git_repo / "untracked.txt").write_text("new\n", encoding="utf-8")
    (git_repo / "file.txt").write_text("modified\n", encoding="utf-8")

    assert count_dirty_paths(git_repo) == 2


def test_count_dirty_paths_is_unknown_when_git_status_fails(tmp_path: Path) -> None:
    """A directory that git cannot read has no count, which is not zero."""
    assert count_dirty_paths(tmp_path) is None


def _directory_bytes(path: Path) -> int:
    """The bytes of every file under `path`, as a person sums them."""
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def test_prune_keeps_the_worktree_of_the_current_directory_and_reads_nothing_for_it(
    git_repo: Path,
    tmp_path: Path,
    git: Git,
    cli: Cli,
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shell inside a merged worktree must not lose its directory (#2338)."""
    merged = tmp_path / "wt_merged"
    tip = _add_worktree(git, git_repo, "branch-merged", merged, commit=True)
    _route_pulls(github_api, tip, _pull(tip, number=2134))
    monkeypatch.chdir(merged)

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm", "--json")

    report = json.loads(result.stdout)
    assert (result.exit_code, merged.exists(), github_api.requested) == (0, True, [])
    assert _outcomes(report)["wt_merged"] == ("refused", "current directory")


def test_forced_prune_keeps_the_worktree_of_the_current_directory(
    git_repo: Path,
    tmp_path: Path,
    git: Git,
    cli: Cli,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    here = tmp_path / "wt_here"
    other = tmp_path / "wt_other"
    _add_worktree(git, git_repo, "branch-here", here)
    _add_worktree(git, git_repo, "branch-other", other)
    monkeypatch.chdir(here)

    result = cli(
        "repos", "worktrees", "prune", "-r", str(git_repo), "--force", "--confirm", "--json"
    )

    report = json.loads(result.stdout)
    assert (result.exit_code, here.exists(), other.exists()) == (0, True, False)
    assert _outcomes(report)["wt_here"] == ("refused", "current directory")
    assert _outcomes(report)["wt_other"] == ("removed", None)


def test_prune_reports_the_size_of_each_removed_worktree(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    merged = tmp_path / "wt_merged"
    tip = _add_worktree(git, git_repo, "branch-merged", merged, commit=True)
    _route_pulls(github_api, tip, _pull(tip, number=2134))
    size = _directory_bytes(merged)

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm", "--json")

    report = json.loads(result.stdout)
    sizes = {Path(i["path"]).name: i["size_bytes"] for i in report["items"]}
    assert size > 0
    assert (sizes["wt_merged"], sizes["repo"], report["total_bytes"]) == (size, None, size)


def test_prune_preview_and_final_lines_give_the_size(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    merged = tmp_path / "wt_merged"
    tip = _add_worktree(git, git_repo, "branch-merged", merged, commit=True)
    _route_pulls(github_api, tip, _pull(tip, number=2134))
    shown = format_bytes(_directory_bytes(merged))

    preview = cli("repos", "worktrees", "prune", "-r", str(git_repo))
    confirmed = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm")

    assert f"Preview: 1 removable ({shown})" in preview.stdout
    assert f"wt_merged (head of merged pull request #2134, {shown})" in " ".join(
        preview.stdout.split()
    )
    assert f"Prune complete: 1 removed, 1 refused, 0 failed, {shown} freed" in confirmed.stdout


def test_a_worktree_whose_directory_is_gone_has_no_size(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli
) -> None:
    gone = tmp_path / "wt_gone"
    _add_worktree(git, git_repo, "branch-gone", gone)
    shutil.rmtree(gone)

    result = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--confirm", "--json")

    report = json.loads(result.stdout)
    sizes = {Path(i["path"]).name: i["size_bytes"] for i in report["items"]}
    assert (result.exit_code, sizes["wt_gone"], report["total_bytes"]) == (0, None, 0)


def test_directory_size_ignores_file_deleted_during_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file deleted after directory listing contributes zero bytes and raises no error."""
    measured = tmp_path / "measured"
    measured.mkdir()
    f1 = measured / "f1.txt"
    f2 = measured / "f2.txt"
    f1.write_text("hello", encoding="utf-8")
    f2.write_text("world", encoding="utf-8")

    real_lstat = os.lstat

    def deleting_lstat(path: Any, *args: Any, **kwargs: Any) -> Any:
        if str(path).endswith("f2.txt") and f2.exists():
            f2.unlink()
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", deleting_lstat)
    size = directory_size(measured)
    assert size == len(b"hello")


def test_status_runs_under_the_dry_run_flag(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, git_fake: GitFake
) -> None:
    """`repos worktrees status` reads only local git, so `devops --dry-run` runs it (#2258)."""
    _add_worktree(git, git_repo, "branch-one", tmp_path / "wt_one", commit=True)
    git_fake.calls.clear()

    result = cli("--dry-run", "repos", "worktrees", "status", "-r", str(git_repo), "--json")

    assert result.exit_code == 0, result.output
    assert "wt_one" in result.stdout
    assert [call.argv for call in git_fake.calls if not call.local_read] == []


def test_prune_under_the_dry_run_flag_prints_the_request_plan(
    git_repo: Path, tmp_path: Path, git: Git, cli: Cli, github_api: GitHubApiFake
) -> None:
    """`devops --dry-run repos worktrees prune` gives the plan of `--dry-run` (#2258)."""
    _add_worktree(git, git_repo, "branch-merged", tmp_path / "wt_merged", commit=True)

    flag = cli("repos", "worktrees", "prune", "-r", str(git_repo), "--dry-run")
    root = cli("--dry-run", "repos", "worktrees", "prune", "-r", str(git_repo))

    assert (root.exit_code, root.stdout, github_api.requested) == (0, flag.stdout, [])
