"""The git calls of the implement job that reach `origin`, and the check of its git settings (GHSA).

**The invariant.** No git call that holds the GitHub token reads a configuration, hook, attribute
or credential file that the agent can write, and no process that the agent, or a git call without
the token, started is alive when a git call with the token starts. The shell of the agent runs as
the user of the Job, so it can write the git configuration of the home folder and of the clone,
the hooks of the clone and the attribute files of the checkout. A program that such a file names
runs as a child of git, with the environment of git. The process runner gives the token only to a
git child that reaches a remote (`git_reaches_remote`), so a local git call of the job, such as
`git add` or `git commit`, holds none.

**A network call** (`OriginGit`) ends every leftover process of the job, checks the settings of
the checkout, ends every leftover process again, and makes a new folder with `tempfile.mkdtemp`. In it, a new bare git folder gets the
object folder of the clone as a link, and an empty folder becomes the home folder of the call. A
fetch first gets the remote-tracking refs of the clone, so that it asks only for the objects that
the clone lacks. The new folder gets a copy of the `shallow` file of a shallow clone, and a fetch
that changes it writes it back. Neither step follows a link at the `shallow` file or at a
temporary file: a link at `shallow` stops the item with `GitSettingsError`. The job ends every leftover process again, and then runs the call
with the token
(`CONST_GIT_TOKEN_CALL_CONFIG`, `CONST_GIT_ISOLATED_CONFIG_ENV`): git reads no global, system or
clone configuration, no hook and no attribute file, and gets the credential from the trusted helper
alone. The remote is the URL of `origin` that the job read before its first step. The job writes
the remote-tracking ref that the call changed into the clone, and removes the folder. Every call
but the one with the token runs with no token.

**The check of the settings** (`check_settings`) reads the keys of the scopes `local` and
`worktree`, the attributes `filter`, `diff` and `merge` of each path that git would stage, and the
alternates file of the clone. A key outside `CONST_GIT_ALLOWED_SETTINGS`, a driver that git does
not define itself, or an alternates file raises `GitSettingsError`, which stops the item with the
failure class `git_config`. The error names each key or attribute, and never a value. A call with
the token reads none of these settings, so the check is a signal and a second guard. It runs only
in a runner, as `end_leftover_processes` does: a person can keep a filter of their own.
"""

from __future__ import annotations

import errno
import fnmatch
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
    CONST_GIT_ALLOWED_SETTING_PATTERNS,
    CONST_GIT_ALLOWED_SETTINGS,
    CONST_GIT_ALTERNATES_FILE,
    CONST_GIT_ATTRIBUTE_DRIVERS,
    CONST_GIT_ATTRIBUTE_STATES,
    CONST_GIT_BUILTIN_DRIVERS,
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
# The scopes of `git config --list --show-scope` that the clone and its worktree hold.
_CHECKED_SCOPES = frozenset({"local", "worktree"})
_ORIGIN_REFS = "refs/remotes/origin/"


def _git(where: Sequence[str], *args: str, stdin: str | None = None, isolated: bool = True) -> str:
    """The output of a git call with no token: `git <where> <args>`. `isolated` turns the global
    and the system configuration off. Raises `GitOperationError` with git's reason, masked."""
    proc = run_subprocess(
        [BIN_GIT, *where, *args],
        input=stdin,
        env=dict(CONST_GIT_ISOLATED_CONFIG_ENV) if isolated else None,
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


# ── The check of the settings ─────────────────────────────────────────────────────────────


def _allowed(key: str) -> bool:
    return key in CONST_GIT_ALLOWED_SETTINGS or any(
        fnmatch.fnmatchcase(key, pattern) for pattern in CONST_GIT_ALLOWED_SETTING_PATTERNS
    )


def _refused_keys(checkout: Path) -> list[str]:
    """The keys of the scopes `local` and `worktree` outside the allowlist, each once. The keys of a
    file that `include.path` names have the scope of the file that includes it."""
    listed = _git(["-C", str(checkout)], "config", "--list", "--show-scope", "-z", isolated=False)
    fields = listed.split("\0")
    keys = (
        entry.partition("\n")[0]
        for scope, entry in zip(fields[0::2], fields[1::2], strict=False)
        if scope in _CHECKED_SCOPES
    )
    return list(dict.fromkeys(key for key in keys if not _allowed(key)))


def _driver_refused(attribute: str, value: str) -> bool:
    return value not in CONST_GIT_ATTRIBUTE_STATES and value not in CONST_GIT_BUILTIN_DRIVERS.get(
        attribute, frozenset()
    )


def _refused_attributes(checkout: Path) -> list[str]:
    """The attributes of `CONST_GIT_ATTRIBUTE_DRIVERS` that name a driver that git does not define,
    each with the first path that has it and the count of the others. `git check-attr` reads every
    attribute file that git reads for a path."""
    where = ["-C", str(checkout)]
    listed = _git(where, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if not listed:
        return []
    found = _git(where, "check-attr", "-z", "--stdin", *CONST_GIT_ATTRIBUTE_DRIVERS, stdin=listed)
    fields = found.split("\0")
    paths: dict[str, list[str]] = {}
    for path, attribute, value in zip(fields[0::3], fields[1::3], fields[2::3], strict=False):
        if _driver_refused(attribute, value):
            paths.setdefault(attribute, []).append(path)
    return [
        MESSAGES.roadmap.implement_git_attribute_refused.format(
            attribute=attribute, path=min(held), more=len(held) - 1
        )
        for attribute, held in paths.items()
    ]


def refused_settings(checkout: Path) -> list[str]:
    """What the git settings of `checkout` hold that the implement job does not allow: each key,
    each attribute with its first path, and the alternates file. Empty when it allows them all."""
    alternates = _common_dir(checkout) / CONST_GIT_ALTERNATES_FILE
    return [
        *_refused_keys(checkout),
        *_refused_attributes(checkout),
        *([CONST_GIT_ALTERNATES_FILE] if alternates.exists() else []),
    ]


def check_settings(checkout: Path) -> None:
    """In a runner, raise `GitSettingsError` when the git settings of `checkout` hold what the
    implement job does not allow (`refused_settings`)."""
    if not load_settings().roadmap.implement.in_runner:
        return
    refused = refused_settings(checkout)
    if refused:
        named = ", ".join(f"`{setting}`" for setting in refused)
        raise GitSettingsError(
            MESSAGES.roadmap.implement_git_settings_refused.format(settings=named),
            settings=tuple(refused),
        )


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
    """The new git folder of one network call, the empty home folder of the call, the git folder
    that the clone and its worktrees share, and the text of the clone's `shallow` file that the new
    git folder got (None when the clone is not shallow)."""

    git_dir: Path
    home: Path
    common: Path
    shallow: bytes | None = None

    def keep_shallow(self) -> None:
        """Write the `shallow` file of the new git folder into the clone when the call changed it.
        The text goes into a new file with a random name (`tempfile.mkstemp`, which makes the file
        with `O_EXCL` and so follows no link), and `os.replace` then puts that file in the place of
        `shallow`: a link there is replaced, not followed. The clone's file is not read again."""
        made = self.git_dir / CONST_GIT_SHALLOW_FILE
        if not made.exists():
            return
        text = made.read_bytes()
        if text == self.shallow:
            return
        handle, written = tempfile.mkstemp(prefix=f"{CONST_GIT_SHALLOW_FILE}.", dir=self.common)
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(text)
            os.replace(written, self.common / CONST_GIT_SHALLOW_FILE)
        except BaseException:
            Path(written).unlink(missing_ok=True)
            raise

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
    text says. A call that git refuses raises `GitOperationError`, and a refused setting raises
    `GitSettingsError` before any call."""

    repository: Path
    url: str

    @contextmanager
    def _folder(self, *, refs: bool) -> Iterator[_Folder]:
        """A new git folder with the objects of the clone, and with its remote-tracking refs when
        `refs` is true. The leftover processes end before the check of the settings, so that they
        are gone also when the check stops the call, before the folder exists, and again before the
        caller runs the call with the token. The folder goes when the block ends."""
        _sweep()
        check_settings(self.repository)
        _sweep()
        parent = Path(tempfile.mkdtemp(prefix="devops-origin-"))
        try:
            common = _common_dir(self.repository)
            shallow = _read_shallow(common / CONST_GIT_SHALLOW_FILE)
            folder = _Folder(parent / "repo.git", parent / "home", common, shallow)
            folder.home.mkdir()
            _git([], "init", "--quiet", "--bare", str(folder.git_dir))
            shutil.rmtree(folder.git_dir / "objects")
            (folder.git_dir / "objects").symlink_to(common / "objects", target_is_directory=True)
            if shallow is not None:
                (folder.git_dir / CONST_GIT_SHALLOW_FILE).write_bytes(shallow)
            if refs:
                self._copy_refs(["-C", str(self.repository)], [f"--git-dir={folder.git_dir}"])
            _sweep()
            yield folder
        finally:
            shutil.rmtree(parent, ignore_errors=True)

    @staticmethod
    def _copy_refs(source: Sequence[str], target: Sequence[str], *names: str) -> None:
        """Write the remote-tracking refs of `source` (only `names` when given) into `target`."""
        patterns = [f"{_ORIGIN_REFS}{name}" for name in names] or [_ORIGIN_REFS]
        listed = _git(source, "for-each-ref", "--format=update %(refname) %(objectname)", *patterns)
        if listed.strip():
            _git(target, "update-ref", "--stdin", stdin=listed)

    def heads(self, *branches: str) -> str:
        """The lines of `git ls-remote --heads` for `branches`, or for every branch."""
        with self._folder(refs=False) as folder:
            return folder.call(
                "ls-remote", "--heads", self.url, *(f"refs/heads/{name}" for name in branches)
            ).strip()

    def fetch(self, *branches: str) -> None:
        """Fetch `branches` of `origin` into `refs/remotes/origin/<branch>` of the clone."""
        specs = [f"+refs/heads/{name}:{_ORIGIN_REFS}{name}" for name in branches]
        with self._folder(refs=True) as folder:
            folder.call("fetch", "--quiet", "--no-tags", "--no-write-fetch-head", self.url, *specs)
            folder.keep_shallow()
            self._copy_refs(
                [f"--git-dir={folder.git_dir}"], ["-C", str(self.repository)], *branches
            )

    def push(self, branch: str, tip: str | None, *, lease: str | None = None) -> None:
        """Push the commit `tip` to `branch` of `origin`, or delete the branch when `tip` is None.
        `lease` is the tip of the branch that `origin` must still hold. The remote-tracking ref of
        the branch in the clone follows the push."""
        ref = f"refs/heads/{branch}"
        leased = [f"--force-with-lease={ref}:{lease}"] if lease is not None else []
        with self._folder(refs=False) as folder:
            folder.call("push", "--quiet", "--no-verify", *leased, self.url, f"{tip or ''}:{ref}")
        tracking = f"{_ORIGIN_REFS}{branch}"
        change = f"update {tracking} {tip}\n" if tip else f"delete {tracking}\n"
        _git(["-C", str(self.repository)], "update-ref", "--stdin", stdin=change)


__all__ = ["OriginGit", "check_settings", "origin_url", "refused_settings"]
