"""Close issues whose pull requests merged into a non-default branch.

GitHub acts on a closing keyword only when the pull request merges into the repository's
**default** branch. Every task pull request here targets a release branch, so `Closes #317`
in a body does nothing, and the issue stays open until someone notices. The keyword is not
recovered at release time either: the merge commits carry `(#317)` as a reference, which is
not a closing keyword, so shipping the release does not close them either.

This module performs the closure GitHub declines to, using the same links the author
already wrote, so the pull request body stays the single place the relationship is
declared.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from devops_cli.config.constants import (
    CONST_ISSUE_CLOSING_KEYWORDS,
    CONST_ISSUE_STATE_CLOSED,
    CONST_ISSUE_STATE_OPEN,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.rate_limiter import run_gh

logger = logging.getLogger(__name__)

# A closing keyword, optional colon, then the issue reference. Matched case-insensitively.
# The owner/repo prefix is captured so a cross-repository link is recognised and skipped
# rather than closing the same-numbered issue in this repository.
_CLOSING_REFERENCE_RE = re.compile(
    r"\b(?P<keyword>[a-z]+)\b\s*:?\s+(?:(?P<repo>[\w.-]+/[\w.-]+))?#(?P<number>\d+)",
    re.IGNORECASE,
)
# Fenced code blocks and inline code are stripped before scanning: a body that documents
# the syntax, as this project's own docs do, must not be read as a live link.
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
# A quoted line is someone else's text, not this author's declaration.
_QUOTE_LINE_RE = re.compile(r"^\s*>.*$", re.MULTILINE)


@dataclass(frozen=True)
class LinkedIssue:
    """An issue a pull request body declares it closes."""

    number: int
    keyword: str


@dataclass
class ClosureResult:
    """The outcome of attempting to close the issues behind one pull request."""

    pull_request: int
    base_ref: str = ""
    merged: bool = False
    closed: list[int] = field(default_factory=list)
    already_closed: list[int] = field(default_factory=list)
    skipped: list[tuple[int, str]] = field(default_factory=list)
    reason: str = ""
    error: str = ""

    @property
    def acted(self) -> bool:
        """Whether this pull request resulted in any issue being closed."""
        return bool(self.closed)

    def as_dict(self) -> dict[str, Any]:
        """Render as a JSON-serializable mapping."""
        return {
            "pull_request": self.pull_request,
            "base_ref": self.base_ref,
            "merged": self.merged,
            "closed": self.closed,
            "already_closed": self.already_closed,
            "skipped": [{"issue": number, "reason": why} for number, why in self.skipped],
            "reason": self.reason,
            "error": self.error,
        }


def strip_non_prose(body: str) -> str:
    """Remove code blocks and quoted text before scanning for closing keywords.

    A body that documents the syntax, or quotes a review comment that mentions an issue,
    must not be read as a live declaration; closing an unrelated issue is not recoverable
    by the person who wrote the prose.
    """
    without_fences = _FENCED_CODE_RE.sub(" ", body or "")
    without_inline = _INLINE_CODE_RE.sub(" ", without_fences)
    return _QUOTE_LINE_RE.sub(" ", without_inline)


def extract_linked_issues(body: str, repo: str | None = None) -> list[LinkedIssue]:
    """Extract the issues a pull request body declares it closes.

    Only the keywords GitHub itself honours are accepted, so what this closes is exactly
    what GitHub would have closed had the pull request targeted the default branch. A bare
    `#317`, or a reference qualified with a different repository, is deliberately ignored.
    """
    found: dict[int, str] = {}
    for match in _CLOSING_REFERENCE_RE.finditer(strip_non_prose(body)):
        keyword = match.group("keyword").lower()
        if keyword not in CONST_ISSUE_CLOSING_KEYWORDS:
            continue
        qualifier = match.group("repo")
        if qualifier and repo and qualifier.lower() != repo.lower():
            logger.debug("Ignoring cross-repository closing reference '%s'.", match.group(0))
            continue
        number = int(match.group("number"))
        found.setdefault(number, keyword)
    return [
        LinkedIssue(number=number, keyword=keyword) for number, keyword in sorted(found.items())
    ]


def _gh_json(args: list[str]) -> Any:
    """Run a gh command expected to emit JSON."""
    result = run_gh(args, check=False, quiet=True)
    if result.returncode != 0:
        raise GitHubOperationError(
            f"GitHub CLI command failed ({' '.join(args[:3])}): {result.stderr.strip()}"
        )
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(f"Malformed JSON from GitHub CLI: {exc}") from exc


def get_pull_request(repo: str, number: int) -> dict[str, Any]:
    """Fetch the fields needed to decide whether a pull request should close issues."""
    payload = _gh_json(
        [
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,body,state,mergedAt,baseRefName,url",
        ]
    )
    if not isinstance(payload, dict):
        raise GitHubOperationError(f"Unexpected response for pull request #{number}.")
    return payload


def get_default_branch(repo: str) -> str:
    """Resolve a repository's default branch."""
    payload = _gh_json(["repo", "view", repo, "--json", "defaultBranchRef"])
    if isinstance(payload, dict):
        ref = payload.get("defaultBranchRef")
        if isinstance(ref, dict) and isinstance(ref.get("name"), str):
            return str(ref["name"])
    raise GitHubOperationError(f"Could not resolve the default branch for '{repo}'.")


def get_issue_state(repo: str, number: int) -> str | None:
    """Return an issue's state, or ``None`` if it cannot be read.

    A pull request number passed where an issue was expected reads as ``None`` here, which
    keeps the caller from closing a pull request by mistake.
    """
    result = run_gh(
        ["issue", "view", str(number), "--repo", repo, "--json", "number,state"],
        check=False,
        quiet=True,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout or "null")
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict) and isinstance(payload.get("state"), str):
        return str(payload["state"]).lower()
    return None


def close_issue(repo: str, number: int, comment: str) -> bool:
    """Close one issue with an explanatory comment, reporting whether it succeeded."""
    args = ["issue", "close", str(number), "--repo", repo]
    if comment:
        args += ["--comment", comment]
    result = run_gh(args, check=False, quiet=True)
    if result.returncode != 0:
        logger.debug("Failed closing issue #%d: %s", number, result.stderr.strip())
        return False
    return True


def closure_comment(pull_request: int, base_ref: str, url: str = "") -> str:
    """Build the comment recorded on a closed issue.

    The issue says why it closed and what closed it. A silent close leaves no way to tell a
    completed issue from one someone tidied away.
    """
    target = url or f"#{pull_request}"
    return (
        f"Closed by {target}, merged into `{base_ref}`.\n\n"
        f"GitHub only acts on closing keywords when a pull request merges into the "
        f"default branch, so this was closed by `devops gh issues close-merged`."
    )


def close_issues_for_pull_request(
    repo: str,
    number: int,
    *,
    default_branch: str | None = None,
    dry_run: bool = False,
) -> ClosureResult:
    """Close the issues a merged pull request declared, if GitHub has not already.

    Refuses on an unmerged pull request: a closing keyword is a statement about what
    merging *will* do, and acting on it early closes issues whose work may never land.
    """
    pull = get_pull_request(repo, number)
    base_ref = str(pull.get("baseRefName") or "")
    # gh exposes mergedAt, not a boolean; it is null until the pull request actually merges.
    merged = bool(pull.get("mergedAt"))
    result = ClosureResult(pull_request=number, base_ref=base_ref, merged=merged)

    if not merged:
        result.reason = "pull request is not merged"
        return result

    resolved_default = default_branch if default_branch is not None else get_default_branch(repo)
    if base_ref == resolved_default:
        # GitHub already honoured the keywords; doing it again would post a misleading
        # comment claiming this tool closed something it did not.
        result.reason = f"merged into the default branch '{resolved_default}'; GitHub closes these"
        return result

    linked = extract_linked_issues(str(pull.get("body") or ""), repo)
    if not linked:
        result.reason = "no closing keywords in the pull request body"
        return result

    comment = closure_comment(number, base_ref, str(pull.get("url") or ""))
    for issue in linked:
        state = get_issue_state(repo, issue.number)
        if state is None:
            result.skipped.append((issue.number, "not an accessible issue"))
            continue
        if state == CONST_ISSUE_STATE_CLOSED:
            result.already_closed.append(issue.number)
            continue
        if state != CONST_ISSUE_STATE_OPEN:
            result.skipped.append((issue.number, f"unexpected state '{state}'"))
            continue
        if dry_run:
            result.closed.append(issue.number)
            continue
        if close_issue(repo, issue.number, comment):
            result.closed.append(issue.number)
        else:
            result.skipped.append((issue.number, "close request failed"))
    return result


def list_merged_pull_requests(repo: str, base: str | None = None, limit: int = 100) -> list[int]:
    """List merged pull request numbers, newest first, optionally filtered by base branch."""
    args = [
        "pr",
        "list",
        "--repo",
        repo,
        "--state",
        "merged",
        "--limit",
        str(limit),
        "--json",
        "number,baseRefName",
    ]
    if base:
        args += ["--base", base]
    payload = _gh_json(args)
    if not isinstance(payload, list):
        return []
    return [int(item["number"]) for item in payload if isinstance(item, dict) and "number" in item]


def close_issues_for_merged_pull_requests(
    repo: str,
    *,
    base: str | None = None,
    limit: int = 100,
    dry_run: bool = False,
) -> list[ClosureResult]:
    """Sweep merged pull requests and close the issues they declared.

    The default branch is resolved once rather than per pull request, so a sweep costs one
    extra API call instead of one per candidate.
    """
    default_branch = get_default_branch(repo)
    results: list[ClosureResult] = []
    for number in list_merged_pull_requests(repo, base=base, limit=limit):
        try:
            results.append(
                close_issues_for_pull_request(
                    repo, number, default_branch=default_branch, dry_run=dry_run
                )
            )
        except GitHubOperationError as exc:
            # One unreadable pull request must not abandon the rest of the sweep, but it
            # must not be recorded as a clean result either: a sweep where every lookup
            # failed would otherwise report that nothing needed closing, which is the same
            # output as a genuinely up-to-date repository.
            logger.debug("Skipping pull request #%d: %s", number, exc)
            results.append(ClosureResult(pull_request=number, error=str(exc)))
    return results


__all__ = [
    "ClosureResult",
    "LinkedIssue",
    "close_issue",
    "close_issues_for_merged_pull_requests",
    "close_issues_for_pull_request",
    "closure_comment",
    "extract_linked_issues",
    "get_default_branch",
    "get_issue_state",
    "get_pull_request",
    "list_merged_pull_requests",
    "strip_non_prose",
]
