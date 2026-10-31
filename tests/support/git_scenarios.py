"""The scenarios of the git transcripts: each builds a repository, starts the code of `src/` over
it, and returns what that code gave (#2146, ADR 0007).

A scenario is one function of a `Workspace`. `ws.git(...)` builds the repository: when the scenario
is recorded (`tests/support/git_recording.py`) it runs the real git, and when it is replayed it
does nothing, except that `ws.git("repo", "init", ...)` leaves the `.git` marker that the code
reads without git. `ws.write` and `ws.link` write the files in both runs. The code of `src/` that
the scenario starts reaches git through the process runner: recorded, it runs the real git and
the record keeps each command; replayed, `GitFake` or a `ProcessFake` answers from the record.
One function gives both runs, so a scenario cannot drift from its transcript.

Every scenario names its repositories under the workspace root (`repo`, `remote.git`, `clone`),
and a test that replays the scenario puts them at the same names under its `tmp_path`. The
return value holds what JSON holds. Text that names the root goes through `ws.shown`.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.research.edges import extract_git_co_changes
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import get_repo_origin_name, own_source_state, reset_repo_caches
from devops_cli.git.operations import (
    clone_repo,
    commit_snapshot,
    create_branch,
    current_branch,
    delete_merged_branches,
    fetch_all,
    get_latest_git_tag,
    is_git_clean,
    list_branches,
    list_changed_files,
    pull_tracking,
    read_file_at_revision,
    resolve_merge_base,
)
from devops_cli.git.worktree import (
    add_detached_worktree,
    fetch_pr_head,
    remove_worktree,
    review_worktrees_context,
)

ROOT_MARK = "{root}"
IDENTITY_NAME = "Example Author"
IDENTITY_EMAIL = "author@example.com"
COMMIT_DATE = "2026-10-01T00:00:00+00:00"
Scenario = Callable[["Workspace"], Any]
SCENARIOS: dict[str, Scenario] = {}


def scenario(function: Scenario) -> Scenario:
    """Register a scenario under its function's name."""
    SCENARIOS[function.__name__] = function
    return function


def setup_env(root: Path) -> dict[str, str]:
    """The environment that builds a repository the same way on every host: no configuration
    file, one identity on `example.com`, one date, the C locale."""
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(root / ".home"),
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": IDENTITY_NAME,
        "GIT_AUTHOR_EMAIL": IDENTITY_EMAIL,
        "GIT_AUTHOR_DATE": COMMIT_DATE,
        "GIT_COMMITTER_NAME": IDENTITY_NAME,
        "GIT_COMMITTER_EMAIL": IDENTITY_EMAIL,
        "GIT_COMMITTER_DATE": COMMIT_DATE,
    }


@dataclass(frozen=True)
class Workspace:
    """The directory a scenario works in, and whether the real git builds it."""

    root: Path
    recording: bool

    def path(self, *parts: str) -> Path:
        """A path under the root."""
        return self.root.joinpath(*parts)

    def shown(self, text: str) -> str:
        """`text`, with the root written as the placeholder that a transcript holds."""
        return text.replace(str(self.root.resolve()), ROOT_MARK).replace(str(self.root), ROOT_MARK)

    def write(self, rel_path: str, text: str) -> Path:
        """Write a file of the working tree."""
        target = self.path(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def link(self, rel_path: str, target: str) -> None:
        """Write a symbolic link of the working tree."""
        link = self.path(rel_path)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)

    def git(self, rel_dir: str, *args: str) -> None:
        """Run git in `rel_dir` to build the repository. A replay runs nothing."""
        directory = self.path(rel_dir)
        directory.mkdir(parents=True, exist_ok=True)
        if not self.recording:
            if args and args[0] == "init":
                (directory / ".git").mkdir(exist_ok=True)
            return
        subprocess.run(
            ["git", *args],
            cwd=directory,
            env=setup_env(self.root),
            check=True,
            capture_output=True,
        )

    @contextmanager
    def environment(self) -> Iterator[None]:
        """The process environment that the code of `src/` runs in: its own home and data root,
        and the C locale."""
        wanted = {
            "HOME": str(self.root / ".home"),
            "LC_ALL": "C",
            "DEVOPS_CLI_USER_DATA_ROOT": str(self.root / "user-data"),
        }
        saved = {key: os.environ.get(key) for key in wanted}
        os.environ.update(wanted)
        try:
            yield
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def outcome(call: Callable[[], Any], ws: Workspace) -> list[Any]:
    """`["ok", value]` for a call that returned, `["error", class name, text]` for one that raised."""
    try:
        return ["ok", call()]
    except Exception as exc:
        return ["error", type(exc).__name__, ws.shown(str(exc))]


def _commit(ws: Workspace, rel_dir: str, message: str, *paths: str) -> None:
    """Add `paths` (everything when there are none) and commit them."""
    ws.git(rel_dir, "add", *(paths or (".",)))
    ws.git(rel_dir, "commit", "--quiet", "-m", message)


@scenario
def revision_reads(ws: Workspace) -> Any:
    """`repo` holds a regular file `mod.py` of two functions, a rule file under `.cursor/rules`,
    a file `docs/rules.md` with a link `AGENTS.md` to it and a link `linked` to `docs`, and files
    in `my project` and `café`. All are committed on `main`."""
    repo = ws.path("repo")
    ws.git("repo", "init", "--quiet", "-b", "main")
    ws.write("repo/mod.py", "def kept(): pass\ndef gone(): pass\n")
    ws.write("repo/.cursor/rules/style.mdc", "Rule.\n")
    ws.write("repo/docs/rules.md", "Rules.\n")
    ws.link("repo/AGENTS.md", "docs/rules.md")
    ws.link("repo/linked", "docs")
    ws.write("repo/my project/AGENTS.md", "Spaced.\n")
    ws.write("repo/café/mod.py", "x = 1\n")
    _commit(ws, "repo", "files")
    with ws.environment():
        return {
            path: read_file_at_revision(repo, "main", path)
            for path in (
                "mod.py",
                ".cursor/rules",
                ".cursor/rules/style.mdc",
                "AGENTS.md",
                "linked/rules.md",
                "docs/rules.md",
                "my project/AGENTS.md",
                "café/mod.py",
            )
        }


@scenario
def revision_failures(ws: Workspace) -> Any:
    """`repo` holds one commit on `main`. The revision `nosuch` is in no ref."""
    repo = ws.path("repo")
    ws.git("repo", "init", "--quiet", "-b", "main")
    ws.write("repo/mod.py", "x = 1\n")
    _commit(ws, "repo", "base")
    with ws.environment():
        return {
            "read": read_file_at_revision(repo, "nosuch", "mod.py"),
            "merge_base": resolve_merge_base(repo, "nosuch", "main"),
            "changed": [c.model_dump() for c in list_changed_files(repo, "nosuch")],
        }


@scenario
def renamed_files(ws: Workspace) -> Any:
    """`repo` holds `main` with `old_name.py` and `gone.py`, and `feature`, which renames the first
    file, deletes the second and adds `fresh.py`."""
    repo = ws.path("repo")
    outline = "".join(f"def step_{n}():\n    return {n}\n\n\n" for n in range(8))
    ws.git("repo", "init", "--quiet", "-b", "main")
    ws.write("repo/old_name.py", outline)
    ws.write("repo/gone.py", "x = 1\n")
    _commit(ws, "repo", "base")
    ws.git("repo", "switch", "--quiet", "-c", "feature")
    (repo / "old_name.py").unlink()
    ws.write("repo/new_name.py", outline + "def step_9():\n    return 9\n")
    (repo / "gone.py").unlink()
    ws.write("repo/fresh.py", "y = 2\n")
    _commit(ws, "repo", "rename")
    with ws.environment():
        changes = list_changed_files(repo, "main", "feature")
        return {
            "changes": sorted((c.model_dump() for c in changes), key=lambda c: c["path"]),
            "merge_base": resolve_merge_base(repo, "main", "feature"),
        }


@scenario
def working_tree_state(ws: Workspace) -> Any:
    """`repo` has one commit and no tag, then a tag `v0.2.1`, then an edit that is not committed."""
    repo = ws.path("repo")
    ws.git("repo", "init", "--quiet", "-b", "main")
    ws.write("repo/f.txt", "one\n")
    _commit(ws, "repo", "init")
    with ws.environment():
        before = [is_git_clean(repo), get_latest_git_tag(repo)]
        ws.git("repo", "tag", "v0.2.1")
        tagged = get_latest_git_tag(repo)
        ws.write("repo/f.txt", "two\n")
        return {"before": before, "tagged": tagged, "dirty": not is_git_clean(repo)}


@scenario
def worktree_add_and_remove(ws: Workspace) -> Any:
    """`repo` holds one commit on `main` with `f.txt`. A detached worktree of `main` is added at
    `worktrees/wt1` and removed."""
    repo, dest = ws.path("repo"), ws.path("worktrees", "wt1")
    ws.git("repo", "init", "--quiet", "-b", "main")
    ws.write("repo/f.txt", "hello\n")
    _commit(ws, "repo", "init")
    with ws.environment():
        added = add_detached_worktree(repo, "main", dest)
        remove_worktree(repo, dest)
        return {"added": added}


@scenario
def pull_request_head(ws: Workspace) -> Any:
    """`remote.git` holds the head of pull request 42 at `refs/pull/42/head`; `repo` is a clone."""
    ws.git("remote.git", "init", "--quiet", "--bare", "-b", "main")
    ws.git(".", "clone", "--quiet", "remote.git", "repo")
    ws.write("repo/f.txt", "one\n")
    _commit(ws, "repo", "init")
    ws.git("repo", "push", "--quiet", "origin", "HEAD:refs/pull/42/head")
    with ws.environment():
        return {
            "found": fetch_pr_head(ws.path("repo"), 42),
            "missing": fetch_pr_head(ws.path("repo"), 43),
        }


@scenario
def review_worktrees(ws: Workspace) -> Any:
    """`repo` holds one commit on `main`. A review makes a worktree of `main` for the commit and
    one for the base, under the user data root, and removes both when it ends."""
    repo = ws.path("repo")
    ws.git("repo", "init", "--quiet", "-b", "main")
    ws.write("repo/main.py", "print('main')\n")
    _commit(ws, "repo", "initial")
    with (
        ws.environment(),
        review_worktrees_context(
            repo, commit_rev="main", base_rev="main", session_id="ctx"
        ) as worktrees,
    ):
        return {
            "commit": ws.shown(str(worktrees.commit_worktree)),
            "base": ws.shown(str(worktrees.base_worktree)),
            "partial": worktrees.partial_context,
        }


@scenario
def source_state(ws: Workspace) -> Any:
    """`own` is a checkout whose package `own/src/devops_cli` holds `__init__.py`. The states are
    read at a clean tree, after an untracked file, after two edits to the module, and after a commit."""
    package = ws.path("own", "src", "devops_cli")
    package.mkdir(parents=True)
    module = ws.write("own/src/devops_cli/__init__.py", '"""devops-cli."""\n')
    ws.git("own", "init", "--quiet", "-b", "main")
    _commit(ws, "own", "first")
    reset_repo_caches()
    with ws.environment():
        states = [own_source_state(package.resolve())]
        ws.write("own/src/devops_cli/untracked.py", "x = 1\n")
        states.append(own_source_state(package.resolve()))
        for text in ("x = 1\n", "x = 2\n"):
            module.write_text(text, encoding="utf-8")
            states.append(own_source_state(package.resolve()))
        ws.git("own", "commit", "--quiet", "-am", "second")
        states.append(own_source_state(package.resolve()))
    return [list(state) if state else None for state in states]


@scenario
def repository_origin(ws: Workspace) -> Any:
    """`repo` has the remote `origin` at `https://github.com/example/service.git`."""
    ws.git("repo", "init", "--quiet", "-b", "main")
    ws.git("repo", "remote", "add", "origin", "https://github.com/example/service.git")
    reset_repo_caches()
    with ws.environment():
        return get_repo_origin_name(ws.path("repo"))


def _seeded_remote(ws: Workspace, clone: str = "clone") -> None:
    """`remote.git` is a bare repository with `f.txt` on `main`, pushed from `clone`, which keeps
    `origin` as its upstream."""
    ws.git("remote.git", "init", "--quiet", "--bare", "-b", "main")
    ws.git(".", "clone", "--quiet", "remote.git", clone)
    ws.write(f"{clone}/f.txt", "one\n")
    _commit(ws, clone, "one")
    ws.git(clone, "push", "--quiet", "-u", "origin", "main")


def _commit_and_push(ws: Workspace, clone: str, name: str) -> None:
    """Add the file `name` to `clone` and push it to `origin`."""
    ws.write(f"{clone}/{name}", f"{name}\n")
    _commit(ws, clone, name)
    ws.git(clone, "push", "--quiet", "origin", "main")


@scenario
def branch_creation(ws: Workspace) -> Any:
    """`repo` holds one commit on `main` and the branch `feature`. A branch `feature/x` cannot be
    made beside `feature`; `main` is taken; `feat/test` is new and becomes the current branch."""
    repo = ws.path("repo")
    ws.git("repo", "init", "--quiet", "-b", "main")
    ws.git("repo", "commit", "--quiet", "--allow-empty", "-m", "init")
    ws.git("repo", "branch", "feature")
    with ws.environment():
        return {
            "refused": outcome(lambda: create_branch(repo, "feature/x"), ws),
            "taken": outcome(lambda: create_branch(repo, "main"), ws),
            "hyphen": outcome(lambda: create_branch(repo, "-invalid"), ws),
            "new": outcome(lambda: create_branch(repo, "feat/test"), ws),
            "current": current_branch(repo),
        }


@scenario
def branch_listing(ws: Workspace) -> Any:
    """`clone` is on `main`, with the local branch `feat/xyz`, the remote branches
    `origin/feat/remote` and `origin/main`, and `origin/HEAD`. The listings are read on the branch
    and with HEAD detached."""
    clone = ws.path("clone")
    _seeded_remote(ws)
    ws.git("clone", "branch", "feat/xyz")
    ws.git("clone", "push", "--quiet", "origin", "main:feat/remote")
    ws.git("clone", "fetch", "--quiet", "origin")
    ws.git("clone", "remote", "set-head", "origin", "main")
    with ws.environment():
        on_branch = (list_branches(clone), list_branches(clone, all_branches=True))
        ws.git("clone", "checkout", "--quiet", "--detach")
        detached = list_branches(clone)
        return {
            "local": on_branch[0].model_dump(),
            "all": on_branch[1].model_dump(),
            "detached": detached.model_dump(),
        }


@scenario
def merged_branches(ws: Workspace) -> Any:
    """`work` is on `main`, which holds the merged branch `feat/merged`; `feat/open` is not
    merged. `empty` has no commit."""
    work, empty = ws.path("work"), ws.path("empty")
    ws.git("work", "init", "--quiet", "-b", "main")
    ws.git("work", "commit", "--quiet", "--allow-empty", "-m", "init")
    ws.git("work", "branch", "feat/merged")
    ws.git("work", "switch", "--quiet", "-c", "feat/open")
    ws.git("work", "commit", "--quiet", "--allow-empty", "-m", "open")
    ws.git("work", "switch", "--quiet", "main")
    ws.git("empty", "init", "--quiet", "-b", "main")
    with ws.environment():
        return {
            "dry_run": delete_merged_branches(work, dry_run=True),
            "deleted": delete_merged_branches(work),
            "left": list_branches(work).branches,
            "empty": delete_merged_branches(empty),
        }


@scenario
def fetch_and_pull_updates(ws: Workspace) -> Any:
    """`clone2` is one commit behind `origin/main` after `clone1` pushes it; it fetches and pulls
    to catch up."""
    clone2 = ws.path("clone2")
    _seeded_remote(ws, "clone1")
    ws.git(".", "clone", "--quiet", "remote.git", "clone2")
    _commit_and_push(ws, "clone1", "g.txt")
    with ws.environment():
        fetch_all(clone2)
        pull_tracking(clone2)
        return {"head": current_branch(clone2)}


@scenario
def pull_divergent(ws: Workspace) -> Any:
    """`diverged` has a commit that `origin/main` lacks, and `origin/main` has one that `diverged`
    lacks, so a pull cannot fast-forward."""
    diverged = ws.path("diverged")
    _seeded_remote(ws, "pusher")
    ws.git(".", "clone", "--quiet", "remote.git", "diverged")
    _commit_and_push(ws, "pusher", "g.txt")
    ws.write("diverged/h.txt", "h\n")
    _commit(ws, "diverged", "local")
    with ws.environment():
        return outcome(lambda: pull_tracking(diverged), ws)


@scenario
def pull_without_a_remote_branch(ws: Workspace) -> Any:
    """A pull does nothing in `untracked`, whose branch has no upstream, and in `detached`, whose
    HEAD is detached. In `orphaned` the branch tracks the remote `gone`, which does not exist."""
    for name in ("untracked", "detached", "orphaned"):
        ws.git(name, "init", "--quiet", "-b", "main")
        ws.git(name, "commit", "--quiet", "--allow-empty", "-m", "init")
    ws.git("detached", "checkout", "--quiet", "--detach")
    ws.git("orphaned", "config", "branch.main.remote", "gone")
    ws.git("orphaned", "config", "branch.main.merge", "refs/heads/main")
    with ws.environment():
        return {
            name: outcome(lambda name=name: pull_tracking(ws.path(name)), ws)
            for name in ("untracked", "detached", "orphaned")
        }


@scenario
def fetch_refused(ws: Workspace) -> Any:
    """`repo` has the remote `origin` at a path that holds no repository."""
    ws.git("repo", "init", "--quiet", "-b", "main")
    ws.git("repo", "remote", "add", "origin", str(ws.path("missing.git")))
    with ws.environment():
        return outcome(lambda: fetch_all(ws.path("repo")), ws)


@scenario
def clone(ws: Workspace) -> Any:
    """`remote.git` holds `f.txt` on `main`. It is cloned to `first`; `missing.git` is no
    repository."""
    _seeded_remote(ws, "seed")
    with ws.environment():
        return {
            "cloned": outcome(lambda: clone_repo(str(ws.path("remote.git")), ws.path("first")), ws),
            "missing": outcome(
                lambda: clone_repo(str(ws.path("missing.git")), ws.path("second")), ws
            ),
        }


@scenario
def commit_snapshots(ws: Workspace) -> Any:
    """`one` and `two` hold the same two files. Each becomes a repository of one commit made with
    one author, no e-mail, one date and one message."""
    when = datetime(2026, 10, 3, tzinfo=UTC)
    commits = []
    counts = []
    with ws.environment():
        for name in ("one", "two"):
            ws.write(f"{name}/app/db.py", "query = f'{x}'\n")
            ws.write(f"{name}/a.py", "x = 1\n")
            commits.append(
                commit_snapshot(
                    ws.path(name),
                    ["app/db.py", "a.py"],
                    "The golden review set's files, for a path review\n",
                    author="devops-cli golden",
                    email="",
                    date=when,
                )
            )
            count = run_subprocess(
                ["git", "-C", str(ws.path(name)), "rev-list", "--count", "HEAD"],
                quiet=True,
                local_read=True,
            )
            counts.append(count.stdout.strip())
        return {"commits": commits, "branch": current_branch(ws.path("one")), "counts": counts}


@scenario
def co_changes(ws: Workspace) -> Any:
    """In `repo`, `a.py` changes in three commits: with `b.py` and `c.py`, with `b.py`, and with
    `d.py` and `sp ace.py`. A merge brings a branch that changes `e.py`. `lonely.py` is committed
    alone."""
    repo = ws.path("repo")
    ws.git("repo", "init", "--quiet", "-b", "main")
    for name in ("a.py", "b.py", "c.py"):
        ws.write(f"repo/{name}", "v1\n")
    _commit(ws, "repo", "first")
    for name in ("a.py", "b.py"):
        ws.write(f"repo/{name}", "v2\n")
    _commit(ws, "repo", "second")
    for name in ("a.py", "d.py", "sp ace.py"):
        ws.write(f"repo/{name}", "v3\n")
    _commit(ws, "repo", "third")
    ws.git("repo", "switch", "--quiet", "-c", "side")
    ws.write("repo/e.py", "e\n")
    _commit(ws, "repo", "side")
    ws.git("repo", "switch", "--quiet", "main")
    ws.git("repo", "merge", "--quiet", "--no-ff", "-m", "merge", "side")
    ws.write("repo/lonely.py", "x\n")
    _commit(ws, "repo", "lonely")

    def edges(name: str, limit: int = 100) -> list[dict[str, Any]]:
        found = extract_git_co_changes(repo / name, repo, limit)
        return [edge.model_dump() for edge in found]

    with ws.environment():
        return {"a": edges("a.py"), "latest_only": edges("a.py", 1), "alone": edges("lonely.py")}


@pytest.fixture
def known_hosts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The `~/.ssh/known_hosts` of a home in `tmp_path`, which the clone code writes (#2146).

    A test asserts on this file, not on a call to the private function that writes it.
    """
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    return home / ".ssh" / "known_hosts"


@pytest.fixture
def git() -> Callable[..., None]:
    """Run `git -C <repo> <args>` with a throwaway identity; a git error fails the test.

    Tests that build real repositories and worktrees in `tmp_path` share it.
    """

    def run(repo: Path, *args: str) -> None:
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@example.com",
                *args,
            ],
            check=True,
            capture_output=True,
        )

    return run


@pytest.fixture
def nested_worktree(tmp_path: Path, git: Callable[..., None]) -> tuple[Path, Path]:
    """A checkout and a linked worktree nested under its `.claude/worktrees/`, as Claude Code
    places them; the checkout ignores `.claude/`, and its pyproject enables only ruff's
    unused-import rule."""
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "--quiet")
    (main / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (main / "pyproject.toml").write_text(
        '[project]\nname = "main"\n\n[tool.ruff.lint]\nselect = ["F401"]\n',
        encoding="utf-8",
    )
    git(main, "add", ".")
    git(main, "commit", "--quiet", "-m", "first")
    nested = main / ".claude" / "worktrees" / "wt"
    git(main, "worktree", "add", "--quiet", "-b", "nested", str(nested))
    return main, nested


@pytest.fixture
def symbol_removal_repo(tmp_path: Path, git: Callable[..., None]) -> Path:
    """A real repository whose `main` defines two functions and whose `feature` branch
    removes one of them and adds another."""
    git(tmp_path, "init", "--quiet", "-b", "main")
    (tmp_path / "mod.py").write_text("def kept(): pass\ndef gone(): pass\n", encoding="utf-8")
    git(tmp_path, "add", "mod.py")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    git(tmp_path, "switch", "--quiet", "-c", "feature")
    (tmp_path / "mod.py").write_text("def kept(): pass\ndef added(): pass\n", encoding="utf-8")
    git(tmp_path, "commit", "--quiet", "-am", "remove gone")
    return tmp_path
