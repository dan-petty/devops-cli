"""The git calls of the implement job that reach `origin` (GHSA).

**The invariant.** No git call that holds the GitHub token reads a configuration, hook, attribute
or credential file that the agent can write, and no process that the agent, or a git call without
the token, started is alive when a git call with the token starts. The shell of the agent runs as
the user of the Job, so it can write the git configuration of the home folder and of the clone,
the hooks of the clone and the attribute files of the checkout. A program that such a file names
runs as a child of git, with the environment of git. The process runner gives the token only to a
git child that reaches a remote (`git_reaches_remote`), so a local git call of the job, such as
`git add` or `git commit`, holds none.

**A network call** (`OriginGit`: the read of the heads and the push, which the withdraw of the
review step uses) ends every leftover process of the job, and makes a new folder with
`tempfile.mkdtemp`. In it, a new bare git folder gets the object folder of the clone as a link,
and an empty folder becomes the home folder of the call. The new folder gets a copy of the
`shallow` file of a shallow clone. The copy follows no link at the `shallow` file: a link there
stops the item with `GitSettingsError`. The job ends every leftover process again, and then runs
the call with the token (`CONST_GIT_TOKEN_CALL_CONFIG`, `CONST_GIT_ISOLATED_CONFIG_ENV`): git
reads no global, system or clone configuration, no hook and no attribute file, and gets the
credential from the trusted helper alone. The remote is the URL of `origin` that the job read
before its first step. After a push, the job writes the remote-tracking ref of the branch into the
clone, and removes the folder. Every call but the one with the token runs with no token.
"""

from __future__ import annotations

import errno
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from devops_cli.config.commands import BIN_GIT
from devops_cli.config.constants import (
    CONST_GIT_ISOLATED_CONFIG_ENV,
    CONST_GIT_NONINTERACTIVE_ENV,
    CONST_GIT_SHALLOW_FILE,
    CONST_GIT_TOKEN_CALL_CONFIG,
)
from devops_cli.config.settings import load_settings
from devops_cli.core import process_hardening
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import GitSettingsError
from devops_cli.git.worktree_inventory import git_message
from devops_cli.lang import MESSAGES
from devops_cli.security.sanitizer import mask_secrets

# The operation that a failed call names; the value of `implement.GIT_OPERATION`.
_OPERATION = "roadmap.implement"
_ORIGIN_REFS = "refs/remotes/origin/"


def _git(where: Sequence[str], *args: str, stdin: str | None = None) -> str:
    """The output of a git call with no token: `git <where> <args>`, with the global and the system
    configuration off. Raises `GitOperationError` with git's reason, masked."""
    proc = run_subprocess(
        [BIN_GIT, *where, *args],
        input=stdin,
        env=dict(CONST_GIT_ISOLATED_CONFIG_ENV),
        check=False,
        quiet=True,
    )
    if proc.returncode != 0:
        raise GitOperationError(
            MESSAGES.roadmap.git_failed.format(
                command=" ".join(args), reason=mask_secrets(git_message(proc))
            ),
            operation=_OPERATION,
        )
    return proc.stdout


def _common_dir(checkout: Path) -> Path:
    """The git folder that the clone and each of its worktrees share."""
    found = _git(["-C", str(checkout)], "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(found.strip())


def _sweep() -> None:
    """End every leftover process of the job, in a runner (`end_leftover_processes`)."""
    if load_settings().roadmap.implement.in_runner:
        process_hardening.end_leftover_processes()


# ── The network calls ─────────────────────────────────────────────────────────────────────


def origin_url(checkout: Path) -> str:
    """The URL of `origin` that the configuration of the clone holds. The job reads it before its
    first step, when no agent has run."""
    found = _git(["-C", str(checkout)], "config", "--local", "--get", "remote.origin.url")
    return found.strip()


def _shallow_refused() -> GitSettingsError:
    return GitSettingsError(
        MESSAGES.roadmap.implement_git_settings_refused.format(
            settings=f"`{CONST_GIT_SHALLOW_FILE}`"
        ),
        settings=(CONST_GIT_SHALLOW_FILE,),
    )


def _read_shallow(path: Path) -> bytes | None:
    """The text of the `shallow` file at `path`, or None when the clone is not shallow. git never
    makes the file a link, so it is opened with `O_NOFOLLOW` (and `O_NONBLOCK`, so that a FIFO does
    not block): a link or anything but a regular file raises `GitSettingsError`, which stops the
    item with the class `git_config`."""
    try:
        handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise _shallow_refused() from error
        raise
    with os.fdopen(handle, "rb") as file:
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            raise _shallow_refused()
        return file.read()


@dataclass(frozen=True)
class _Folder:
    """The new git folder of one network call and the empty home folder of the call."""

    git_dir: Path
    home: Path

    def call(self, *args: str) -> str:
        """Run `git <args>` with the token in the new git folder, and give its output."""
        config = [word for value in CONST_GIT_TOKEN_CALL_CONFIG for word in ("-c", value)]
        env = {
            **CONST_GIT_ISOLATED_CONFIG_ENV,
            **CONST_GIT_NONINTERACTIVE_ENV,
            "HOME": str(self.home),
            "GH_CONFIG_DIR": str(self.home),
        }
        proc = run_subprocess(
            [BIN_GIT, f"--git-dir={self.git_dir}", *config, *args],
            cwd=self.git_dir,
            env=env,
            check=False,
            quiet=True,
        )
        if proc.returncode != 0:
            raise GitOperationError(
                MESSAGES.roadmap.git_failed.format(
                    command=" ".join(args), reason=mask_secrets(git_message(proc))
                ),
                operation=_OPERATION,
            )
        return proc.stdout


@dataclass(frozen=True)
class OriginGit:
    """The git calls of the implement job that reach `origin` of the clone of `repository` (the
    clone or one of its worktrees), at `url`. Each call runs in a new git folder, as the module
    text says. A call that git refuses raises `GitOperationError`, and a `shallow` file of the
    clone that is a link raises `GitSettingsError`."""

    repository: Path
    url: str

    @contextmanager
    def _folder(self) -> Iterator[_Folder]:
        """A new git folder with the objects of the clone. The leftover processes end before the
        folder exists, and again before the caller runs the call with the token. The folder goes
        when the block ends."""
        _sweep()
        parent = Path(tempfile.mkdtemp(prefix="devops-origin-"))
        try:
            common = _common_dir(self.repository)
            shallow = _read_shallow(common / CONST_GIT_SHALLOW_FILE)
            folder = _Folder(parent / "repo.git", parent / "home")
            folder.home.mkdir()
            _git([], "init", "--quiet", "--bare", str(folder.git_dir))
            shutil.rmtree(folder.git_dir / "objects")
            (folder.git_dir / "objects").symlink_to(common / "objects", target_is_directory=True)
            if shallow is not None:
                (folder.git_dir / CONST_GIT_SHALLOW_FILE).write_bytes(shallow)
            _sweep()
            yield folder
        finally:
            shutil.rmtree(parent, ignore_errors=True)

    def heads(self, *branches: str) -> str:
        """The lines of `git ls-remote --heads` for `branches`, or for every branch."""
        with self._folder() as folder:
            return folder.call(
                "ls-remote", "--heads", self.url, *(f"refs/heads/{name}" for name in branches)
            ).strip()

    def push(self, branch: str, tip: str | None, *, lease: str | None = None) -> None:
        """Push the commit `tip` to `branch` of `origin`, or delete the branch when `tip` is None.
        `lease` is the tip of the branch that `origin` must still hold. The remote-tracking ref of
        the branch in the clone follows the push."""
        ref = f"refs/heads/{branch}"
        leased = [f"--force-with-lease={ref}:{lease}"] if lease is not None else []
        with self._folder() as folder:
            folder.call("push", "--quiet", "--no-verify", *leased, self.url, f"{tip or ''}:{ref}")
        tracking = f"{_ORIGIN_REFS}{branch}"
        change = f"update {tracking} {tip}\n" if tip else f"delete {tracking}\n"
        _git(["-C", str(self.repository)], "update-ref", "--stdin", stdin=change)


__all__ = ["OriginGit", "origin_url"]
