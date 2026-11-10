"""The files of a named pull request at its merge commit (#3447).

A plan can rest on a claim about an earlier pull request that no file of that pull request supports:
#3410 claimed that the plan of #3372 in pull request #3378 chose a move-prefix check, and the plan
of #3378 holds no move group. The verification pass reads the files of each pull request that the
issue body or the plan names, at the merge commit of that pull request, so that the pass can show a
claim that those files contradict.

The reader takes the number of each pull request from the phrases `pull request #` and `PR #` only,
because a bare `#` is an issue, a commit or a cross-link. It reads the changed files of the merge
commit with one `git diff`, then the text of each with one `git show`. A read of GitHub that fails,
and a pull request with no merge commit, add no entry and never stop the item. The text of a file is
masked and cut, and the reader holds at most `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` files over all
named pull requests, so the verification input stays inside its budget.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Protocol

from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_MAX_FILES,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.refine.refine import cited_paths, git_result
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from pathlib import Path

    from devops_cli.github.client import PullStatus

_NAMED_PULL: Final[re.Pattern[str]] = re.compile(
    r"(?:\bpull\s+request|\bPR)\s*#(\d+)", re.IGNORECASE
)
# The folder of a plan: the plan of a named pull request comes before the other changed files.
_CHANGE_FOLDER: Final[str] = "openspec/changes/"
# The largest number of a pull request that the extraction keeps, so a typo reads no huge number.
_MAX_NUMBER: Final[int] = 999_999


class PullStatusReads(Protocol):
    """The one GitHub read that the file reader makes."""

    def get_pull_status(self, repo: str, number: int) -> PullStatus:
        """The state, the merge flag and the merge commit of the pull request `number`."""
        ...


@dataclass(frozen=True)
class PullRequestFiles:
    """The files of one named pull request at its merge commit: its number, the commit, and the
    text of each file by path."""

    number: int
    merge_commit: str
    files: dict[str, str]

    def entry(self) -> dict[str, Any]:
        """The entry as the verification prompt reads it."""
        return {
            "number": self.number,
            "merge_commit": self.merge_commit,
            "files": dict(self.files),
        }


def named_numbers(*texts: str) -> tuple[int, ...]:
    """The number of each pull request that `texts` name as `pull request #` or `PR #`, each once,
    in first-seen order. A number below 1 and a number above 999999 is left out."""
    found: dict[int, None] = {}
    for text in texts:
        for match in _NAMED_PULL.finditer(text):
            number = int(match.group(1))
            if 0 < number <= _MAX_NUMBER:
                found.setdefault(number, None)
    return tuple(found)


def _ordered(paths: Sequence[str], claim: Iterable[str]) -> list[str]:
    """The paths of a pull request in read order: the plan folder, then the paths that the claim
    names, then the rest, each once."""
    wanted = set(claim)
    plan = [path for path in paths if path.startswith(_CHANGE_FOLDER)]
    named = [path for path in paths if path not in plan and path in wanted]
    rest = [path for path in paths if path not in plan and path not in wanted]
    return list(dict.fromkeys((*plan, *named, *rest)))


def _changed_paths(source: Path, merge: str) -> list[str]:
    """The paths that the merge commit `merge` changes against its first parent, in diff order."""
    code, out = git_result(
        source, "diff", "--name-only", "--no-renames", "-z", f"{merge}^1", merge, "--"
    )
    if code != 0:
        return []
    return [path for path in out.split("\0") if path]


def _read_file(source: Path, merge: str, path: str) -> str | None:
    """The text of `path` at `merge`, masked, or None for a path that is binary or is no file of
    the commit."""
    code, text = git_result(source, "show", f"{merge}:{path}")
    if code != 0 or "\0" in text:
        return None
    return mask_secrets(text)


def _bounded(text: str) -> str:
    """`text` cut to the token limit of one verification file."""
    return truncate_to_token_limit(text, CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS)


def files_at(
    source: Path,
    merge: str,
    *,
    claim: Iterable[str] = (),
    limit: int = CONST_ROADMAP_STAGE_VERIFY_MAX_FILES,
) -> dict[str, str]:
    """The text of at most `limit` files that `merge` changes, in read order, each masked and cut to
    `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens."""
    claim_paths = tuple(claim)
    files: dict[str, str] = {}
    for path in _ordered(_changed_paths(source, merge), claim_paths):
        if len(files) == limit:
            break
        text = _read_file(source, merge, path)
        if text is not None:
            files[path] = _bounded(text)
    return files


def read_named_pulls(
    source: Path,
    numbers: Iterable[int],
    *,
    reads: Callable[[], PullStatusReads] | None,
    repo: str,
    claim: Iterable[str] = (),
) -> tuple[PullRequestFiles, ...]:
    """One entry for each pull request in `numbers` whose merge commit the checkout holds, with at
    most `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` files over all of them. A read of GitHub that fails,
    and a pull request with no merge commit, add no entry."""
    if reads is None or not repo:
        return ()
    claim_paths = tuple(claim)
    found: list[PullRequestFiles] = []
    used = 0
    for number in dict.fromkeys(numbers):
        if used >= CONST_ROADMAP_STAGE_VERIFY_MAX_FILES:
            break
        try:
            status = reads().get_pull_status(repo, number)
        except GitHubOperationError:
            continue
        merge = status.merge_commit_sha
        if not merge:
            continue
        files = files_at(
            source, merge, claim=claim_paths, limit=CONST_ROADMAP_STAGE_VERIFY_MAX_FILES - used
        )
        if not files:
            continue
        used += len(files)
        found.append(PullRequestFiles(number, merge, files))
    return tuple(found)


def claim_paths_of(text: str) -> tuple[str, ...]:
    """The paths that a claim names, each once."""
    return tuple(dict.fromkeys(cited_paths(text)))


__all__ = [
    "PullRequestFiles",
    "PullStatusReads",
    "claim_paths_of",
    "files_at",
    "named_numbers",
    "read_named_pulls",
]
