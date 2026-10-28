"""The repository and the job row whose work sends a GitHub request, as the `repo` and `row`
labels of `devops_cli_github_requests_total` (#2475).

The roadmap Service sends the requests of every repository and every job row from one process,
so the request counter names who sent each one: an alert on the Service's writes then finds the
repository and the row that spent them. A worker of the Service names its repository for the
rounds it runs, and a round names each job row while the row runs. A value that no scope names
is `other`. The Service makes a worker only for each repository of `service.repos`, and a round
runs only the rows of its due table, so each label has a bounded set of values.

The scope is a context variable. The GitHub session paces a request in a thread of its portal,
and anyio copies the context of the sending thread into that thread, so a request of the session
counts under the scope of the thread that sent it, as a gh command does.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Final

from devops_cli.config.constants import CONST_GITHUB_REQUEST_SCOPE_OTHER


@dataclass(frozen=True)
class RequestScope:
    """The repository and the job row that the requests of a block are sent for."""

    repo: str = CONST_GITHUB_REQUEST_SCOPE_OTHER
    row: str = CONST_GITHUB_REQUEST_SCOPE_OTHER


_NO_SCOPE: Final[RequestScope] = RequestScope()
"""The scope of a request that no Service worker and no job row sent."""

_SCOPE: ContextVar[RequestScope] = ContextVar("github_request_scope", default=_NO_SCOPE)


@contextmanager
def request_scope(*, repo: str | None = None, row: str | None = None) -> Iterator[RequestScope]:
    """Name `repo` and `row` for each GitHub request sent in the block. A value not given keeps
    the one of the enclosing scope, so a row's scope keeps its worker's repository."""
    current = _SCOPE.get()
    scope = replace(
        current,
        repo=current.repo if repo is None else repo,
        row=current.row if row is None else row,
    )
    token = _SCOPE.set(scope)
    try:
        yield scope
    finally:
        _SCOPE.reset(token)


def request_labels() -> dict[str, str]:
    """The `repo` and `row` labels of a request sent now."""
    scope = _SCOPE.get()
    return {"repo": scope.repo, "row": scope.row}


__all__ = ["RequestScope", "request_labels", "request_scope"]
