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
from pathlib import Path
from typing import Any

from devops_cli.core.repo import get_repo_origin_name, own_source_state, reset_repo_caches
from devops_cli.git.operations import (
    get_latest_git_tag,
    is_git_clean,
    list_changed_files,
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
