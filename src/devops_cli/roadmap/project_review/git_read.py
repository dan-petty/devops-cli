"""The git commands of a project review, and the one function that runs them (#4686).

Each builder gives the arguments of one command after `git -C <checkout>`. The review runs them,
and its dry run lists them with placeholders, so the plan cannot drift from the run. Every command
reads the checkout and makes no network request. The parsers read the `-z` forms, so a path with
a space, a tab or a newline is read whole.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.git.operations import git_argv
from devops_cli.lang import MESSAGES

# The bound of one git read. The 7-day log of this repository takes 5 s to 15 s, and the review
# runs under the deadline of its Job.
_GIT_TIMEOUT_SECONDS: Final = 300.0
_RELEASE_TAGS: Final = "refs/tags/v*"
_COMMIT_FORMAT: Final = "--format=%H%x09%ct"
_LOG_FORMAT: Final = "--format=%x1e%H%x1f%ct%x1f%s"
_GENERATED: Final = "linguist-generated"
# The values of `git check-attr` that mark a path as generated.
_GENERATED_VALUES: Final = frozenset({"set", "true"})


@dataclass(frozen=True)
class FileChange:
    """One path of a numstat: its lines, and its old path when git found a rename."""

    path: str
    added: int
    deleted: int
    old_path: str | None = None


@dataclass(frozen=True)
class Commit:
    """One first-parent commit of the window, newest first."""

    sha: str
    time: datetime
    subject: str
    changes: tuple[FileChange, ...]


def tag_args() -> tuple[str, ...]:
    """The release tags, with the creation time of each in Unix seconds."""
    return ("for-each-ref", "--format=%(refname:short)%09%(creatordate:unix)", _RELEASE_TAGS)


def default_ref_args() -> tuple[str, ...]:
    """The default branch of the origin, as `origin/<name>`."""
    return ("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")


def tag_commit_args(tag: str) -> tuple[str, ...]:
    """The commit of `tag`, and its commit time."""
    return ("log", "-1", _COMMIT_FORMAT, "--end-of-options", f"{tag}^{{commit}}")


def commit_before_args(ref: str, at: str) -> tuple[str, ...]:
    """The last first-parent commit of `ref` at or before the time `at`, and its commit time."""
    return (
        "log",
        "-1",
        "--first-parent",
        f"--before={at}",
        _COMMIT_FORMAT,
        "--end-of-options",
        ref,
    )


def log_args(base: str, head: str) -> tuple[str, ...]:
    """The first-parent commits after `base` up to `head`, with the numstat of each and renames."""
    return ("log", "--first-parent", "-M", "--numstat", "-z", _LOG_FORMAT, f"{base}..{head}")


def diff_args(base: str, head: str) -> tuple[str, ...]:
    """The numstat of the change from the tree of `base` to the tree of `head`."""
    return ("diff", "-M", "--numstat", "-z", base, head)


def generated_args(head: str) -> tuple[str, ...]:
    """The `linguist-generated` attribute of the paths on standard input, as `head` sets it."""
    return ("check-attr", f"--source={head}", "-z", "--stdin", _GENERATED)


def blob_args(rev: str, path: str) -> tuple[str, ...]:
    """The contents of `path` at `rev`."""
    return ("cat-file", "blob", f"{rev}:{path}")


def query_text(args: tuple[str, ...]) -> str:
    """The command as a fact names it: `git` and its arguments, with no checkout path."""
    return " ".join(("git", *args))


def run_git(checkout: Path, args: tuple[str, ...], *, stdin: str | None = None) -> str:
    """The standard output of `git -C <checkout> <args>`. A non-zero exit raises."""
    done = run_subprocess(
        git_argv(checkout, *args),
        input=stdin,
        quiet=True,
        local_read=True,
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    if done.returncode != 0:
        error = (done.stderr or "").strip().splitlines()
        raise RoadmapReviewError(
            MESSAGES.roadmap.review_git_failed.format(
                command=query_text(args), error=error[-1] if error else done.returncode
            )
        )
    return done.stdout


def try_git(checkout: Path, args: tuple[str, ...]) -> str | None:
    """The standard output of the command, or None when git exits non-zero."""
    done = run_subprocess(
        git_argv(checkout, *args), quiet=True, local_read=True, timeout=_GIT_TIMEOUT_SECONDS
    )
    return done.stdout if done.returncode == 0 else None


def commit_line(text: str) -> tuple[str, datetime] | None:
    """The commit and its UTC time from a line `<sha>\\t<unix seconds>`, or None for no line."""
    sha, _, seconds = text.strip().partition("\t")
    return (sha, datetime.fromtimestamp(int(seconds), UTC)) if sha else None


def _lines(count: str) -> int:
    """The lines of a numstat column: git writes `-` for a binary file."""
    return 0 if count == "-" else int(count)


def numstat(text: str) -> tuple[FileChange, ...]:
    """The paths of a `--numstat -z` output. A rename is `<a>\\t<d>\\t` then the old and the new
    path, each ended by a NUL."""
    tokens = iter(text.lstrip("\n").split("\0"))
    changes: list[FileChange] = []
    for token in tokens:
        if not token.strip("\n"):
            continue
        added, deleted, path = token.lstrip("\n").split("\t", 2)
        old = None
        if not path:
            old, path = next(tokens), next(tokens)
        changes.append(FileChange(path, _lines(added), _lines(deleted), old))
    return tuple(changes)


def commits(text: str) -> list[Commit]:
    """The commits of a `log_args` output, newest first."""
    found: list[Commit] = []
    for record in text.split("\x1e")[1:]:
        header, _, body = record.partition("\0")
        sha, seconds, subject = header.split("\x1f", 2)
        when = datetime.fromtimestamp(int(seconds), UTC)
        found.append(Commit(sha, when, subject, numstat(body)))
    return found


def generated_paths(checkout: Path, head: str, paths: set[str]) -> frozenset[str]:
    """The paths that the `.gitattributes` of `head` mark `linguist-generated`."""
    if not paths:
        return frozenset()
    stdin = "".join(f"{path}\0" for path in sorted(paths))
    words = run_git(checkout, generated_args(head), stdin=stdin).split("\0")
    triples = zip(words[0::3], words[1::3], words[2::3], strict=False)
    return frozenset(path for path, _, value in triples if value in _GENERATED_VALUES)
