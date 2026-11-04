"""The open plans and metric senders that a stage context names (#3252).

A plan is written without knowledge of the open pull requests that edit the same files. Two plans
that edit `INSTRUMENTS` or the generated `docs/TELEMETRY.md` can merge one after the other and
force a regenerate. This module reads the open pull requests with their changed files in one
GraphQL request for each 100 through the session, compares them with the paths that the item body
cites, and marks a plan pull request by its title. It also lists the other files that hold a cited
metric name, from `git grep -w` at the staged commit. The stage context carries both lists, and
`check_proposal` refuses a plan that names no overlap.

The reads are data: a title is masked with the secret masker, and a failed read adds no entry and
never stops the item.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Protocol

from devops_cli.exceptions.git import GitOperationError
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.commit_title import commit_scope, commit_type
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry.instruments import INSTRUMENTS

# The most pull requests that one GraphQL page holds.
PULL_PAGE_SIZE: Final[int] = 100
# The type and scope of a pull request that only plans an item.
_PLAN_TYPE: Final[str] = "docs"
_PLAN_SCOPE: Final[str] = "openspec"
# A metric name of devops-cli, as `INSTRUMENTS` writes it.
_METRIC: Final[re.Pattern[str]] = re.compile(r"\bdevops_cli_[a-z0-9_]+\b")

_OPEN_PULLS_QUERY: Final[str] = f"""
query OpenPullRequests($owner: String!, $name: String!, $cursor: String) {{
  repository(owner: $owner, name: $name) {{
    pullRequests(states: OPEN, first: {PULL_PAGE_SIZE}, after: $cursor) {{
      nodes {{
        number
        title
        state
        files(first: {PULL_PAGE_SIZE}) {{
          nodes {{ path }}
        }}
      }}
      pageInfo {{ hasNextPage endCursor }}
    }}
  }}
}}
"""


class PullReads(Protocol):
    """The one GraphQL read of the open pull requests that the context makes."""

    def graphql(self, query: str, variables: Mapping[str, Any] | None = None) -> Any:
        """The answer to one GraphQL request."""
        ...


@dataclass(frozen=True)
class OpenPull:
    """One open pull request, with the files it changes and whether it is a plan."""

    number: int
    title: str
    state: str
    files: tuple[str, ...]
    plan: bool = False


@dataclass(frozen=True)
class Overlap:
    """An open pull request that changes a path the item cites."""

    number: int
    title: str
    state: str
    plan: bool
    paths: tuple[str, ...]

    def entry(self) -> dict[str, Any]:
        """The entry as the model reads it."""
        return {
            "number": self.number,
            "title": self.title,
            "state": self.state,
            "plan": self.plan,
            "paths": list(self.paths),
        }


@dataclass(frozen=True)
class OpenPulls:
    """The open pull requests and the number of GraphQL requests that read them."""

    pulls: tuple[OpenPull, ...]
    requests: int


def session_pull_reads() -> PullReads:
    """The client of the process's GitHub session, read when the context is built, so a plan that
    names no cited path needs no GitHub identity."""
    from devops_cli.github.session import get_github_session

    return get_github_session().client


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _pull_connection(answer: Any) -> Mapping[str, Any]:
    """The `pullRequests` connection of a GraphQL answer, or an empty mapping."""
    repository = _mapping(_mapping(answer).get("data"))
    repository = _mapping(repository.get("repository"))
    return _mapping(repository.get("pullRequests"))


def _file_paths(files: Any) -> tuple[str, ...]:
    """The paths of the `files` connection of one pull request."""
    nodes = _mapping(files).get("nodes")
    if not isinstance(nodes, list):
        return ()
    return tuple(
        path for node in nodes if isinstance(path := _mapping(node).get("path"), str) and path
    )


def _open_pull(node: Any) -> OpenPull | None:
    """One pull request of a GraphQL page, or None when the node has no number."""
    fields = _mapping(node)
    number = fields.get("number")
    if not isinstance(number, int):
        return None
    title = mask_secrets(str(fields.get("title") or ""))
    plan = commit_type(title) == _PLAN_TYPE and commit_scope(title) == _PLAN_SCOPE
    return OpenPull(
        number=number,
        title=title,
        state=str(fields.get("state") or "").lower(),
        files=_file_paths(fields.get("files")),
        plan=plan,
    )


def open_pulls(reads: PullReads, repo: str) -> OpenPulls:
    """The open pull requests of `repo` (`owner/name`), with the files each changes, in one
    GraphQL request for each `PULL_PAGE_SIZE` pull requests."""
    owner, _, name = repo.partition("/")
    if not owner or not name:
        return OpenPulls((), 0)
    pulls: list[OpenPull] = []
    cursor: str | None = None
    requests = 0
    while True:
        answer = reads.graphql(_OPEN_PULLS_QUERY, {"owner": owner, "name": name, "cursor": cursor})
        requests += 1
        connection = _pull_connection(answer)
        nodes = connection.get("nodes")
        if isinstance(nodes, list):
            pulls.extend(pull for node in nodes if (pull := _open_pull(node)) is not None)
        page = _mapping(connection.get("pageInfo"))
        cursor = page.get("endCursor") if page.get("hasNextPage") else None
        if not isinstance(cursor, str) or not cursor:
            break
    return OpenPulls(tuple(pulls), requests)


def overlaps(pulls: Sequence[OpenPull], paths: Iterable[str]) -> tuple[Overlap, ...]:
    """One entry for each pull whose files meet `paths`, with the shared paths sorted."""
    cited = {path for path in paths if path}
    found: list[Overlap] = []
    for pull in pulls:
        shared = tuple(sorted(set(pull.files) & cited))
        if shared:
            found.append(Overlap(pull.number, pull.title, pull.state, pull.plan, shared))
    return tuple(found)


def metric_senders(
    names: Iterable[str], grep: Callable[[str], Iterable[str]]
) -> dict[str, tuple[str, ...]]:
    """For each name that `INSTRUMENTS` holds, the other files that `grep` finds it in, sorted.
    A name that no instrument holds, and a name that no file holds, lists nothing."""
    known = {instrument.name for instrument in INSTRUMENTS}
    senders: dict[str, tuple[str, ...]] = {}
    for name in sorted(set(names) & known):
        files = tuple(sorted({path for path in grep(name) if path}))
        if files:
            senders[name] = files
    return senders


def cited_instruments(text: str) -> list[str]:
    """The metric names that `text` cites and that `INSTRUMENTS` holds."""
    known = {instrument.name for instrument in INSTRUMENTS}
    return sorted(set(_METRIC.findall(text)) & known)


def grep_at(source: Path, sha: str, name: str, *, operation: str) -> tuple[str, ...]:
    """The files that hold `name` at `sha`, from `git grep -w`. A name that no file holds, and a
    failed read, gives no file."""
    try:
        listing = git(source, "grep", "-w", "-l", "-e", name, sha, operation=operation)
    except GitOperationError:
        return ()
    prefix = f"{sha}:"
    return tuple(sorted({line.removeprefix(prefix) for line in listing.splitlines() if line}))


__all__ = [
    "PULL_PAGE_SIZE",
    "OpenPull",
    "OpenPulls",
    "Overlap",
    "PullReads",
    "cited_instruments",
    "grep_at",
    "metric_senders",
    "open_pulls",
    "overlaps",
    "session_pull_reads",
]
