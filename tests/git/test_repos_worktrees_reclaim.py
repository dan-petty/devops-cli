"""Tests for the reclaim of merged worktrees that `devops repos worktrees add` runs first (#2338).

The repositories are real. `origin` is a bare repository at `example-org/app.git` in `tmp_path`,
so git reaches no network and `get_repo_origin_name` reads `example-org/app`, the repository whose
pull requests the GitHub fake answers for.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.core import process
from devops_cli.git.worktree_inventory import inventory_worktrees, prune_worktrees
from devops_cli.output import format_bytes
from tests.support.fakes.github import github_json

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

# The command also claims the issue on the roadmap (#2910). The roadmap is in memory.
pytestmark = pytest.mark.usefixtures("roadmap_store")

Git = Callable[..., None]
Cli = Callable[..., Any]

PULLS_PATH = "/repos/example-org/app/commits/{sha}/pulls?per_page=100"


@pytest.fixture
def new_dir(managed: Path) -> Path:
    """Where the worktree of issue 2345 goes."""
    return managed / "w-2345"


def _worktree(git: Git, repo: Path, branch: str, path: Path) -> str:
    """Add a worktree on a new branch with one commit of its own; return its tip."""
    git(repo, "worktree", "add", "-b", branch, str(path))
    (path / "work.txt").write_text(f"{branch}\n", encoding="utf-8")
    git(path, "add", "work.txt")
    git(path, "commit", "-m", f"work on {branch}")
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _merged(api: GitHubApiFake, tip: str, number: int = 2134) -> str:
    """Answer the lookup of `tip` with a merged pull request headed by it; return the request."""
    pull = {
        "number": number,
        "state": "closed",
        "merged_at": "2026-10-24T18:35:41Z",
        "head": {"sha": tip, "ref": "branch"},
    }
    api.route("GET", PULLS_PATH.format(sha=tip), github_json([pull]))
    return f"GET https://api.github.com{PULLS_PATH.format(sha=tip)}"


def _directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _head(repo: Path) -> str:
    """The commit that the clone has checked out."""
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _add(cli: Cli, repo: Path, *extra: str, issue: int = 2345) -> Any:
    return cli(
        "repos",
        "worktrees",
        "add",
        str(issue),
        "--type",
        "feat",
        "--slug",
        "next",
        "--repo-dir",
        str(repo),
        *extra,
    )


def test_add_removes_a_merged_worktree_and_creates_the_new_one(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake, new_dir: Path
) -> None:
    merged = managed / "wt_merged"
    tip = _worktree(git, repo, "fix/2100-old", merged)
    request = _merged(github_api, tip)
    size = _directory_bytes(merged)

    result = _add(cli, repo, "--json")

    report = json.loads(result.stdout)
    assert (result.exit_code, merged.exists(), new_dir.is_dir()) == (0, False, True)
    assert github_api.requested == [request]
    assert [(Path(i["path"]).name, i["status"], i["size_bytes"]) for i in report["reclaimed"]] == [
        ("wt_merged", "removed", size)
    ]
    assert size > 0
    assert report["reclaim_error"] is None


def test_a_failed_read_of_origin_removes_no_worktree(
    cli: Cli,
    repo: Path,
    git: Git,
    managed: Path,
    github_api: GitHubApiFake,
    new_dir: Path,
    tmp_path: Path,
) -> None:
    """The run reads `origin` before it reclaims, so a failed read changes nothing (#6340)."""
    merged = managed / "wt_merged"
    _merged(github_api, _worktree(git, repo, "fix/2100-old", merged))
    git(repo, "remote", "set-url", "origin", str(tmp_path / "gone" / "app.git"))
    before = _head(repo)

    result = _add(cli, repo)

    said = " ".join(result.output.split())
    assert result.exit_code == 1, result.output
    assert merged.is_dir()
    assert not new_dir.exists()
    assert _head(repo) == before
    assert github_api.requested == []
    assert "git ls-remote --heads origin" in said
    assert "credential.https://github.com.helper" not in said


class _Challenge(BaseHTTPRequestHandler):
    """Answers each request with 401 and a Basic challenge, and keeps its `Authorization`."""

    seen: list[str | None]

    def do_GET(self) -> None:
        self.seen.append(self.headers.get("Authorization"))
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="example"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        return None


@pytest.fixture
def challenge() -> Iterator[tuple[str, list[str | None]]]:
    """The URL of a private repository on a loopback server that asks for Basic credentials, and
    the `Authorization` header of each request that it received."""
    seen: list[str | None] = []
    server = HTTPServer(("127.0.0.1", 0), type("Handler", (_Challenge,), {"seen": seen}))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/example-org/app.git", seen
    finally:
        server.shutdown()
        server.server_close()


def test_the_read_of_origin_uses_the_credential_helper_of_the_environment(
    cli: Cli,
    repo: Path,
    git: Git,
    github_api: GitHubApiFake,
    new_dir: Path,
    challenge: tuple[str, list[str | None]],
    pin_github_session: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The devcontainer sets the credential helper with `GIT_CONFIG_*` keys. The read of a private
    `origin` gets its credential from that helper, which reads the session's token, and no git
    command holds a `-c` value of devops-cli (#6340, #6653). Each git child gets the token, so the
    recorder sees the local reads too (#6691). The server always refuses, so the run stops after
    the read."""
    url, seen = challenge
    git(repo, "remote", "set-url", "origin", url)
    helper = '!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f'
    # The home of the tests refuses every transport but `file` (#4711), so the keys also allow
    # http for the loopback server.
    configured = {
        "GIT_CONFIG_COUNT": "3",
        "GIT_CONFIG_KEY_0": "credential.helper",
        "GIT_CONFIG_VALUE_0": "",
        "GIT_CONFIG_KEY_1": "credential.helper",
        "GIT_CONFIG_VALUE_1": helper,
        "GIT_CONFIG_KEY_2": "protocol.http.allow",
        "GIT_CONFIG_VALUE_2": "always",
    }
    for key, value in configured.items():
        monkeypatch.setenv(key, value)
    started: list[list[str]] = []
    run_in_own_session = process._run_in_own_session

    def record(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        started.append(list(cmd))
        return run_in_own_session(cmd, **kwargs)

    monkeypatch.setattr(process, "_run_in_own_session", record)

    result = _add(cli, repo)

    credential = base64.b64encode(f"x-access-token:{pin_github_session}".encode()).decode()
    assert (result.exit_code, f"Basic {credential}" in seen, new_dir.exists()) == (1, True, False)
    assert (
        ["git", "-C", str(repo), "ls-remote", "--heads", "origin"] in started,
        [cmd for cmd in started if "-c" in cmd],
    ) == (True, [])
    assert github_api.requested == []


def test_the_table_output_names_each_removed_worktree_with_its_size(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake
) -> None:
    merged = managed / "wt_merged"
    _merged(github_api, _worktree(git, repo, "fix/2100-old", merged))
    shown = format_bytes(_directory_bytes(merged))

    result = _add(cli, repo)

    said = " ".join(result.stdout.split())
    assert result.exit_code == 0, result.output
    assert f"removed {merged} ({shown})" in said
    assert "Created worktree" in said


def test_a_merged_worktree_no_longer_holds_its_issue(
    cli: Cli,
    repo: Path,
    git: Git,
    managed: Path,
    github_api: GitHubApiFake,
    isolate_data_dir: Path,
) -> None:
    merged = managed / "wt_merged"
    _merged(github_api, _worktree(git, repo, "chore/2344-old", merged))

    result = _add(cli, repo, issue=2344)

    assert result.exit_code == 0, result.output
    assert not merged.exists()
    assert (isolate_data_dir / "agent" / "worktrees" / "w-2344").is_dir()


def test_a_dirty_a_locked_and_an_unmerged_worktree_stay(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake, new_dir: Path
) -> None:
    dirty, locked, unmerged = (managed / name for name in ("wt_dirty", "wt_locked", "wt_unmerged"))
    _worktree(git, repo, "fix/2101-dirty", dirty)
    (dirty / "scratch.txt").write_text("wip\n", encoding="utf-8")
    _worktree(git, repo, "fix/2102-locked", locked)
    git(repo, "worktree", "lock", "--reason", "agent-42", str(locked))
    tip = _worktree(git, repo, "fix/2103-unmerged", unmerged)
    github_api.route("GET", PULLS_PATH.format(sha=tip), github_json([]))

    result = _add(cli, repo, "--json")

    report = json.loads(result.stdout)
    assert (result.exit_code, report["reclaimed"]) == (0, [])
    assert [p.exists() for p in (dirty, locked, unmerged)] == [True, True, True]
    assert github_api.requested == [f"GET https://api.github.com{PULLS_PATH.format(sha=tip)}"]
    assert new_dir.is_dir()


def test_no_reclaim_keeps_the_merged_worktree_reads_nothing_and_refuses_its_issue(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake
) -> None:
    merged = managed / "wt_merged"
    _merged(github_api, _worktree(git, repo, "chore/2344-old", merged))

    result = _add(cli, repo, "--no-reclaim", issue=2344)

    assert (result.exit_code, merged.exists(), github_api.requested) == (1, True, [])
    assert "wt_merged" in " ".join(result.output.split())


def test_a_failed_read_becomes_a_reason_and_the_worktree_is_created(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake, new_dir: Path
) -> None:
    unread = managed / "wt_unread"
    _worktree(git, repo, "fix/2100-unread", unread)

    result = _add(cli, repo, "--json")

    report = json.loads(result.stdout)
    assert (result.exit_code, unread.exists(), new_dir.is_dir()) == (0, True, True)
    assert report["reclaimed"] == []
    assert report["reclaim_error"]


def test_a_failed_read_is_said_once_in_the_table_output(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake, new_dir: Path
) -> None:
    _worktree(git, repo, "fix/2100-unread", managed / "wt_unread")

    result = _add(cli, repo)

    assert result.exit_code == 0, result.output
    assert result.output.count("not reclaimed") == 1
    assert new_dir.is_dir()


def test_the_dry_run_lists_the_reads_of_the_reclaim_and_removes_nothing(
    cli: Cli, repo: Path, git: Git, managed: Path, github_api: GitHubApiFake, new_dir: Path
) -> None:
    merged = managed / "wt_merged"
    tip = _worktree(git, repo, "fix/2100-old", merged)

    result = _add(cli, repo, "--dry-run", "--json")

    report = json.loads(result.stdout)
    assert (result.exit_code, merged.exists(), github_api.requested) == (0, True, [])
    assert report["requests"][0] == f"GET /repos/example-org/app/commits/{tip}/pulls"
    # Five of the reclaim and the worktree, three of the claim of the issue, and four of its
    # Status In Progress with the read-back of the Status writer (#4685, #5018).
    assert len(report["requests"]) == 12
    assert not new_dir.exists()


def test_the_worktree_of_the_current_directory_is_kept(
    cli: Cli,
    repo: Path,
    git: Git,
    managed: Path,
    github_api: GitHubApiFake,
    new_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    merged = managed / "wt_merged"
    _merged(github_api, _worktree(git, repo, "fix/2100-old", merged))
    monkeypatch.chdir(merged)

    result = _add(cli, repo, "--json")

    report = json.loads(result.stdout)
    assert (result.exit_code, merged.exists(), github_api.requested) == (0, True, [])
    assert report["reclaimed"] == []
    assert new_dir.is_dir()


def test_add_succeeds_when_merged_worktree_file_is_deleted_during_reclaim(
    cli: Cli,
    repo: Path,
    git: Git,
    managed: Path,
    github_api: GitHubApiFake,
    new_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worktrees add succeeds when a file in a merged worktree is deleted during reclaim."""
    merged = managed / "wt_merged"
    tip = _worktree(git, repo, "fix/2100-old", merged)
    _merged(github_api, tip)

    real_lstat = os.lstat

    def deleting_lstat(path: Any, *args: Any, **kwargs: Any) -> Any:
        work_file = merged / "work.txt"
        if str(path).endswith("work.txt") and work_file.exists():
            work_file.unlink()
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", deleting_lstat)
    result = _add(cli, repo)

    assert result.exit_code == 0
    assert new_dir.is_dir()


def test_prune_reports_a_parallel_removed_worktree_as_removed(
    repo: Path, git: Git, managed: Path, github_api: GitHubApiFake
) -> None:
    """A worktree that a parallel run already removed is reported as removed, not failed (#2408).

    `add` inventories the worktrees, then removes each merged one. Between the two, a run in
    parallel removes one: its record and its directory are gone. `git worktree remove` of it fails
    with `is not a working tree`; the run reports it as `removed`, so it counts as done, not as a
    failed reclaim.
    """
    merged = managed / "wt_merged"
    request = _merged(github_api, _worktree(git, repo, "fix/2100-old", merged))
    entries = inventory_worktrees(repo)
    git(repo, "worktree", "remove", str(merged))

    report = prune_worktrees(
        repo, entries, repo="example-org/app", managed_root=managed, confirm=True
    )

    item = next(i for i in report.items if Path(i.path).name == "wt_merged")
    assert item.status == "removed"
    assert (report.removed_count, report.failed_count) == (1, 0)
    assert (github_api.requested, merged.exists()) == ([request], False)


def test_add_says_nothing_of_a_failed_reclaim_when_a_parallel_run_removed_the_worktree(
    cli: Cli,
    repo: Path,
    git: Git,
    managed: Path,
    github_api: GitHubApiFake,
    new_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a run in parallel removes a merged worktree while `add` reclaims, `add` reports it as
    removed, not as a failed reclaim, and creates the new worktree (#2408)."""
    merged = managed / "wt_merged"
    _merged(github_api, _worktree(git, repo, "fix/2100-old", merged))
    real_lstat = os.lstat

    def removing_lstat(path: Any, *args: Any, **kwargs: Any) -> Any:
        if str(path).startswith(str(merged) + os.sep) and merged.exists():
            subprocess.run(
                ["git", "-C", str(repo), "worktree", "remove", str(merged)],
                check=True,
                capture_output=True,
            )
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", removing_lstat)
    result = _add(cli, repo, "--json")

    report = json.loads(result.stdout)
    assert result.exit_code == 0, result.output
    assert [(Path(i["path"]).name, i["status"]) for i in report["reclaimed"]] == [
        ("wt_merged", "removed")
    ]
    assert report["reclaim_error"] is None
    assert new_dir.is_dir()
    assert "not reclaimed" not in " ".join(result.output.split())
