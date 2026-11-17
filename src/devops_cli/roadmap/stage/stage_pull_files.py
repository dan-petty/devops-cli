"""The files of the pull requests that an issue or a plan names (#3447).

A plan can rest on a claim about an earlier pull request, such as "the plan of #3372 in pull
request #3378 chose a whole-prefix check". The verification pass reads the issue, the plan and the
files of the repository that the plan cites, but it never read the named pull request, so a plan
could open a draft on a premise that the pull request contradicts (#3410). This module reads the
changed files of each pull request that the issue body or a plan text names, at the merge commit of
that pull request, and gives them to the verification input as evidence.

Only the phrase `pull request #` or `PR #` names a pull request (`named_pull_requests`): a bare
`#` is an issue reference and reads nothing. A pull request that is not merged, or that cannot be
read, gives no entry and never stops the plan (`pull_request_files`). The reads are data: the text
of each file is masked with the secret masker, cut to
`CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens, and at most
`CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` files are kept, the OpenSpec change folder first.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_MAX_FILES,
)
from devops_cli.exceptions.git import GitHubOperationError, GitOperationError
from devops_cli.github.client import PullRequest
from devops_cli.roadmap.clone_git import git
from devops_cli.security.sanitizer import mask_secrets

# The phrase that names a pull request: `pull request #3378` or `PR #3378`, in any case. A bare
# `#3410` is an issue reference and reads no pull request.
_NAMED_PULL: Final[re.Pattern[str]] = re.compile(r"(?:pull request|PR) #(\d+)", re.IGNORECASE)
# The folder that the stage job writes: its files come first in the bounded read.
_CHANGE_FOLDER: Final[str] = "openspec/changes/"


class PullReads(Protocol):
    """The one REST read of a pull request that the stage job makes."""

    def get_pull(self, repo: str, number: int) -> PullRequest:
        """The pull request `number` of `repo` (`owner/name`)."""
        ...


@dataclass(frozen=True)
class PullRequestFiles:
    """The changed files of one named pull request at its merge commit: the `number` of the pull
    request, the `commit` it merged on, and the text of each kept path."""

    number: int
    commit: str
    files: Mapping[str, str]


def named_pull_requests(texts: Iterable[str]) -> list[int]:
    """The numbers of the pull requests that `texts` name with the phrase `pull request #` or
    `PR #`, each once, in first-seen order. A bare `#` names no pull request."""
    found: dict[int, None] = {}
    for text in texts:
        for number in _NAMED_PULL.findall(text):
            found.setdefault(int(number), None)
    return list(found)


def pull_request_files(
    source: Path,
    repo: str,
    numbers: Iterable[int],
    reads: Callable[[], PullReads],
    *,
    operation: str,
) -> dict[int, PullRequestFiles]:
    """The changed files of each pull request in `numbers`, read at its merge commit from `source`.

    A pull request that is not merged, or whose read fails, gives no entry: the pass still runs and
    the plan is not stopped by the read."""
    found: dict[int, PullRequestFiles] = {}
    for number in numbers:
        entry = _read_one(source, repo, number, reads, operation=operation)
        if entry is not None:
            found[number] = entry
    return found


def _read_one(
    source: Path,
    repo: str,
    number: int,
    reads: Callable[[], PullReads],
    *,
    operation: str,
) -> PullRequestFiles | None:
    """The files of pull request `number` at its merge commit, or None when it cannot be read."""
    if number < 1:
        return None
    try:
        pull = reads().get_pull(repo, number)
    except GitHubOperationError:
        return None
    commit = pull.merge_commit_sha
    if not pull.merged or not commit:
        return None
    try:
        git(source, "fetch", "-q", "origin", commit, operation=operation)
        names = _changed_paths(source, commit, operation=operation)
    except GitOperationError:
        return None
    files = _files_at(source, commit, names, operation=operation)
    if not files:
        return None
    return PullRequestFiles(number, commit, files)


def _changed_paths(source: Path, commit: str, *, operation: str) -> list[str]:
    """The paths that `commit` changed against its first parent. A commit that a clean merge made
    changes nothing against its first parent, so the second parent is no source of the files of the
    pull request."""
    listing = git(source, "diff", "--name-only", f"{commit}^", commit, operation=operation)
    return [line for line in listing.splitlines() if line]


def _files_at(source: Path, commit: str, names: Iterable[str], *, operation: str) -> dict[str, str]:
    """The text of each path of `names` at `commit`, at most
    `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` of them, the OpenSpec change folder first, each cut to
    `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens and with a secret masked. A path that
    `commit` does not hold, such as a deleted file, is left out."""
    files: dict[str, str] = {}
    for name in sorted(names, key=_priority):
        if len(files) == CONST_ROADMAP_STAGE_VERIFY_MAX_FILES:
            break
        text = _show(source, commit, name, operation=operation)
        if text is not None:
            files[name] = mask_secrets(
                truncate_to_token_limit(text, CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS)
            )
    return files


def _show(source: Path, commit: str, name: str, *, operation: str) -> str | None:
    """The text of `name` at `commit`, or None when `commit` holds no such file or the file is no
    text."""
    try:
        return git(source, "show", f"{commit}:{name}", operation=operation)
    except GitOperationError, UnicodeDecodeError:
        return None


def _priority(name: str) -> tuple[int, str]:
    """A sort key that puts the OpenSpec change folder first, then the other paths by name."""
    return (0 if name.startswith(_CHANGE_FOLDER) else 1, name)


__all__ = [
    "PullReads",
    "PullRequestFiles",
    "named_pull_requests",
    "pull_request_files",
]
