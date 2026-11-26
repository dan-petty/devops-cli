"""The releases of a repository and the closed issues each one carries (#2917).

A release names its pull requests in its changelog, as `([#N](url))`. The body of each pull
request that `devops pr create` opens holds a `Closes #<issue>` line, so the issues of a release
come from those bodies and not from the changelog text, which names few of them. The feed reads
through `run_gh`, as the roadmap store does, and sends only `GET` requests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, TypeAdapter
from pydantic import ValidationError as MalformedPayloadError

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.error_classifier import classify_gh_failure, gh_http_status
from devops_cli.github.issue_answer import (
    NO_ISSUE_STATUSES,
    CurrentName,
    answered_repository,
    answers_request,
)
from devops_cli.github.rate_limiter import run_gh
from devops_cli.roadmap.stores.github_store import GhRunner

_PULL_LINK = re.compile(r"\(\[#(\d+)\]\(")
_CLOSING = re.compile(
    r"^[ \t]*(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)[ \t]+#(\d+)\b", re.I | re.M
)
_OPERATION = "roadmap.release_feed"


@dataclass(frozen=True)
class ReleaseInfo:
    """A release as GitHub lists it: its tag, page, publication time, flags and changelog."""

    tag: str
    url: str
    published_at: datetime
    draft: bool
    prerelease: bool
    body: str


class _ReleasePayload(BaseModel):
    tag_name: str
    html_url: str
    # Null for a draft: a release is one until its files are attached (#7328).
    published_at: datetime | None
    draft: bool = False
    prerelease: bool = False
    body: str | None = None

    def release(self, published_at: datetime) -> ReleaseInfo:
        return ReleaseInfo(
            self.tag_name,
            self.html_url,
            published_at,
            self.draft,
            self.prerelease,
            self.body or "",
        )


class _IssuePayload(BaseModel):
    number: int
    state: str
    body: str | None = None
    pull_request: dict[str, object] | None = None
    repository_url: str | None = None
    url: str | None = None
    html_url: str | None = None

    def answers(self, number: int, current: CurrentName) -> bool:
        """Whether the payload is the answer for number `number` of the repository of `current`,
        and not the issue at another place that GitHub gives for a transferred issue
        (`issue_answer`)."""
        named = answered_repository(
            repository_url=self.repository_url, url=self.url, html_url=self.html_url
        )
        return answers_request(
            current.repo, number, answered=self.number, named=named, current=current
        )


class _RepositoryPayload(BaseModel):
    full_name: str


_RELEASES = TypeAdapter(list[_ReleasePayload])
_ISSUE = TypeAdapter(_IssuePayload)
_REPOSITORY = TypeAdapter(_RepositoryPayload)


def _unique(numbers: list[int]) -> tuple[int, ...]:
    return tuple(dict.fromkeys(numbers))


def pull_numbers(body: str) -> tuple[int, ...]:
    """The numbers that a changelog links as `([#N](url))`, once each, in text order."""
    return _unique([int(number) for number in _PULL_LINK.findall(body)])


def closing_numbers(body: str) -> tuple[int, ...]:
    """The numbers after `Closes`, `Fixes` or `Resolves` at the start of a line of `body`, in any
    case and in any of the forms of GitHub, once each, in text order."""
    return _unique([int(number) for number in _CLOSING.findall(body)])


class GitHubReleaseFeed:
    """Reads the releases of `repo` and the closed issues of one release."""

    def __init__(self, repo: str, runner: GhRunner = run_gh) -> None:
        self._repo = repo
        self._runner = runner
        self._name = CurrentName(repo, self._full_name)

    def releases(self, limit: int) -> tuple[ReleaseInfo, ...]:
        """The published releases among the `limit` newest ones, newest first. A release with no
        publication time is not out yet, so it is left out. Raises GitHubOperationError."""
        text = self._read(f"repos/{self._repo}/releases?per_page={limit}", "the releases")
        return tuple(
            payload.release(payload.published_at)
            for payload in self._validate(_RELEASES, text, "releases")
            if payload.published_at is not None
        )

    def closed_issues(self, release: ReleaseInfo) -> tuple[int, ...]:
        """The closed issues that the pull requests of `release` close, once each, in ascending
        order. A number that names a pull request or an open issue is left out, and so is one
        that is no issue of the repository now: GitHub answers 404, 301 or 410 for it, or
        answers with the issue at another place (#7337). Raises GitHubOperationError for any
        other failure."""
        numbers: list[int] = []
        for pull in pull_numbers(release.body):
            payload = self._issue(pull)
            if payload is not None:
                numbers.extend(closing_numbers(payload.body or ""))
        closed: set[int] = set()
        for number in dict.fromkeys(numbers):
            payload = self._issue(number)
            if payload and payload.state == "closed" and payload.pull_request is None:
                closed.add(number)
        return tuple(sorted(closed))

    def _issue(self, number: int) -> _IssuePayload | None:
        """The issue or the pull request `number` of the repository, or None when the repository
        holds none now."""
        text = self._read(f"repos/{self._repo}/issues/{number}", f"#{number}", absent_ok=True)
        if text is None:
            return None
        payload = self._validate(_ISSUE, text, f"#{number}")
        return payload if payload.answers(number, self._name) else None

    def _full_name(self) -> str | None:
        """The name that GitHub gives the repository now, or None when it gives none."""
        text = self._read(f"repos/{self._repo}", "the repository", absent_ok=True)
        return None if text is None else self._validate(_REPOSITORY, text, "repository").full_name

    def _read(self, path: str, what: str, *, absent_ok: bool = False) -> str | None:
        proc = self._runner(["api", path], input=None, check=False, quiet=True, use_cache=False)
        if proc.returncode == 0:
            return proc.stdout or ""
        if absent_ok and gh_http_status(proc.stderr or "") in NO_ISSUE_STATUSES:
            return None
        classified = classify_gh_failure(
            proc.stderr or "", exit_code=proc.returncode, operation=_OPERATION
        )
        output = f"{proc.stderr or ''} {proc.stdout or ''}".strip()
        raise classified or GitHubOperationError(
            f"Could not read {what} in {self._repo} (exit {proc.returncode}): {output[:256]}",
            operation=_OPERATION,
            details={"repo": self._repo[:256], "exit_code": proc.returncode},
        )

    def _validate[PayloadT](
        self, adapter: TypeAdapter[PayloadT], text: str | None, what: str
    ) -> PayloadT:
        try:
            return adapter.validate_json(text or "")
        except MalformedPayloadError as exc:
            raise GitHubOperationError(
                f"GitHub returned malformed {what} for {self._repo}.",
                operation=_OPERATION,
                details={"repo": self._repo[:256], "error": str(exc)[:256]},
            ) from exc


__all__ = [
    "GitHubReleaseFeed",
    "ReleaseInfo",
    "closing_numbers",
    "pull_numbers",
]
