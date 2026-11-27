"""Whether the answer of a request of one issue by its number is that issue (#7331, #7337).

GitHub can answer a request of `repos/<owner>/<name>/issues/<number>` for an issue that is no
issue of the repository now in four ways (REST reference, "Get an issue"): 404 for a number that
is no issue there, 301 for an issue that was transferred to another repository, 410 for an issue
that was deleted, and, when the client follows the redirect of a transferred issue, 200 with the
issue at its new place. That last answer holds the number and the repository of another issue.

GitHub also redirects each route of a repository that was renamed or moved to another owner. An
issue answer under the old name then holds the same number and the new name of the same
repository. `CurrentName` reads the name that GitHub gives the configured repository now, one
time, so that such an answer is taken and the answer of a transferred issue is not.

Three readers of one issue number use this module, so none of them takes the answer for another
issue as the issue that it asked for: the roadmap store, the release feed and
`GitHubClient.get_issue`. The commands that a person runs compare nothing: the reads of `devops gh
issue view` and `devops gh issue edit` (`get_repository_issue` and `resolve_updated_labels` of
`github/issues.py`), and the answers of the issue writes of `commands/gh.py` and
`commands/pr.py`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import PurePosixPath
from typing import Final
from urllib.parse import urlsplit

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.exceptions.validation import ValidationError as RepositoryNameError
from devops_cli.github.repo_ref import RepoRef

logger = logging.getLogger(__name__)

NO_ISSUE_STATUSES: Final = (
    HTTPStatus.NOT_FOUND,
    HTTPStatus.MOVED_PERMANENTLY,
    HTTPStatus.GONE,
)
"""The statuses of a read of one issue by its number that say that the repository holds no such
issue: 404, 301, which a client that does not follow the redirect of a transferred issue gets, and
410. Only the read of one issue number takes them so: a listing or another route that answers 301
or 410 fails (#7337)."""

# The path segment of a REST URL that the owner and the name of a repository follow.
_REPOS_SEGMENT: Final = "repos"
# The path segment that follows the repository in the page URL of an issue or a pull request.
_PAGE_KINDS: Final = frozenset({"issues", "pull"})
# The count of the path parts of such a page URL: the root, the owner, the name, the kind and
# the number.
_PAGE_PARTS: Final = 5
# The count of the path parts that name a repository: its owner and its name.
_NAME_PARTS: Final = 2


def repository_named(parts: Sequence[str]) -> RepoRef | None:
    """The repository that `parts` name as its owner and its name, or None when they are no
    `owner/name` of GitHub."""
    if len(parts) != _NAME_PARTS:
        return None
    try:
        return RepoRef("/".join(parts))
    except RepositoryNameError:
        return None


def _rest_repository(url: str) -> RepoRef | None:
    """The repository of a REST URL, `.../repos/<owner>/<name>` with or without a path after
    the name, or None when the URL names none."""
    parts = PurePosixPath(urlsplit(url).path).parts
    if _REPOS_SEGMENT not in parts:
        return None
    start = parts.index(_REPOS_SEGMENT) + 1
    return repository_named(parts[start : start + _NAME_PARTS])


def page_repository(url: str) -> RepoRef | None:
    """The repository of the page of an issue or a pull request, `/<owner>/<name>/issues/<number>`
    or `/<owner>/<name>/pull/<number>`, or None when the URL is no such page."""
    parts = PurePosixPath(urlsplit(url).path).parts
    if len(parts) != _PAGE_PARTS or parts[3] not in _PAGE_KINDS:
        return None
    return repository_named(parts[1:3])


def answered_repository(
    *, repository_url: str | None, url: str | None, html_url: str | None
) -> RepoRef | None:
    """The repository that an issue answer names: the one of `repository_url`, else the one of
    `url`, else the one of the page `html_url`. None when no field names a repository."""
    for rest_url in (repository_url, url):
        if rest_url and (named := _rest_repository(rest_url)) is not None:
            return named
    return None if html_url is None else page_repository(html_url)


def says_no_issue(error: GitHubOperationError) -> bool:
    """Whether `error`, the failure of a request, holds a status of `NO_ISSUE_STATUSES`. The
    GitHub session puts the status of the answer in the details of each error that it raises."""
    return error.details.get("status") in NO_ISSUE_STATUSES


@dataclass
class CurrentName:
    """The name that GitHub gives now for the repository that a reader holds as `repo`.

    `read` gives the `full_name` of the answer of `repos/<repo>`, or None when GitHub gives no
    repository for that name. The reader calls it at most one time in the life of this object,
    and only for an answer with the requested number and another repository name. A name that
    differs from `repo` says that the repository was renamed or moved to another owner: one
    warning says that the configured name is old."""

    repo: str
    read: Callable[[], str | None]
    _now: list[RepoRef | None] = field(default_factory=list, init=False, repr=False)

    def names(self, named: RepoRef) -> bool:
        """Whether `named` is the name that GitHub gives this repository now."""
        if not self._now:
            found = self.read()
            now = None if found is None else repository_named(found.split("/"))
            self._now.append(now)
            if now is not None and now != repository_named(self.repo.split("/")):
                logger.warning(
                    "GitHub names the repository %s as %s now. The configured name is old: give "
                    "the new name.",
                    self.repo,
                    now.display,
                )
        return self._now[0] is not None and self._now[0] == named


def answers_request(
    repo: str,
    number: int,
    *,
    answered: int,
    named: RepoRef | None,
    current: CurrentName | None = None,
) -> bool:
    """Whether an answer is the answer for number `number` of the repository `repo`: its number
    `answered` is `number`, and the repository `named` that it names is `repo`. `RepoRef`
    compares the names, so their case does not count. An answer that names no repository is
    compared by its number only.

    An answer with the number and another repository name is the answer of this repository only
    when `current` says that GitHub gives this repository that name now (a renamed repository).
    The answer of a transferred issue names a repository that is not this one under any name, so
    it stays refused, also when its number is the requested one."""
    if answered != number:
        return False
    own = repository_named(repo.split("/"))
    if named is None or own is None or named == own:
        return True
    return current is not None and current.names(named)


__all__ = [
    "NO_ISSUE_STATUSES",
    "CurrentName",
    "answered_repository",
    "answers_request",
    "page_repository",
    "repository_named",
    "says_no_issue",
]
