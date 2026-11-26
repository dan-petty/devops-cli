"""The search providers of the reference step, as data (#4672).

A provider answers one query with hits. A hit is a file of a repository (a code hit), a repository
with its facts (a repository hit) or a page of documentation. Each provider says which bound one
of its searches spends: a code search or a fact read.

- `github-code` is GitHub's code search: it answers a query of an item with code hits.
  `github-repository` is GitHub's repository search: it answers one query for an item, which
  names the repositories of all code hits, with the facts of each. Both go through the roadmap
  store, which sends them on the paced GitHub session.
- An optional provider needs a connection at the start of a run. `open_providers` connects each
  one. A provider whose server is down raises `RoadmapMcpUnavailableError` and leaves the list of
  the run, and the check continues with the other providers. A provider that fails at a search
  ends its connection, and `in_run` then leaves it out of the later queries. A private repository gets the two
  GitHub providers only, so no text of its items leaves GitHub.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_CODE_SEARCHES,
    CONST_ROADMAP_ALTERNATIVES_REFERENCE_SEARCH_RESULTS,
)
from devops_cli.exceptions.roadmap import RoadmapMcpUnavailableError
from devops_cli.github.repo_ref import is_repository_name
from devops_cli.telemetry.instruments import BRAIN_REFERENCES_TOTAL, emit

if TYPE_CHECKING:
    from devops_cli.roadmap.stores.store import ReferenceFacts, RoadmapStore

logger = logging.getLogger(__name__)

GITHUB_CODE = "github-code"
GITHUB_REPOSITORY = "github-repository"
# The provider of a documentation link that the sources of the check give.
WEB = "web"
# The provider label of what the step counts for itself: a query that the guard refused, a step
# that passed its time bound, and a step whose work ended with an error.
STEP = "step"
# The most repositories of one item: each result of each code search.
_MAX_REPOSITORIES = (
    CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_CODE_SEARCHES
    * CONST_ROADMAP_ALTERNATIVES_REFERENCE_SEARCH_RESULTS
)


class HitKind(StrEnum):
    """What a hit names: a file of a repository, a repository, or a page of documentation."""

    CODE = "code"
    REPOSITORY = "repository"
    DOCUMENTATION = "documentation"


class SearchKind(StrEnum):
    """The bound that one search of a provider spends."""

    CODE = "code"
    FACT = "fact"


class Result(StrEnum):
    """The result label of `devops_cli_brain_references_total`. A search gives `hit`, `empty` or
    `failed`. A verified link gives `verified` in mode `plan` and `linked` when mode `on` writes
    it. `unavailable` is an optional provider that was down at the start. Under the provider
    `step`, `refused` is a query that the guard of the web search refused, `timeout` is a step
    that passed its time bound, and `failed` is a step whose work ended with an error."""

    HIT = "hit"
    EMPTY = "empty"
    FAILED = "failed"
    VERIFIED = "verified"
    LINKED = "linked"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    REFUSED = "refused"


@dataclass(frozen=True)
class Hit:
    """One hit of a provider for `query`. A code hit has a `repository` and a `path`, a repository
    hit has a `repository` and its `facts`, and a documentation hit has a `url`."""

    provider: str
    kind: HitKind
    query: str = ""
    repository: str = ""
    path: str = ""
    url: str = ""
    facts: ReferenceFacts | None = None


class ReferenceProvider(Protocol):
    """A search provider: its name, which is the provider label of the counter, the bound that a
    search spends, and the search."""

    @property
    def name(self) -> str: ...

    @property
    def kind(self) -> SearchKind: ...

    def search(self, query: str) -> list[Hit]:
        """The hits of `query`. A search that cannot complete raises a `DevOpsCLIError`."""
        ...


@runtime_checkable
class OptionalProvider(ReferenceProvider, Protocol):
    """A provider that needs a connection. `connect` raises `RoadmapMcpUnavailableError` when its
    server is down, and `close` ends the connection and raises the same error when it fails.
    `connected` is false after a failed search: the provider then left the run."""

    @property
    def connected(self) -> bool: ...

    def connect(self) -> None: ...

    def close(self) -> None: ...


def in_run(provider: ReferenceProvider) -> bool:
    """Whether `provider` still takes a query of the run: each provider but an optional provider
    that is not connected."""
    return not isinstance(provider, OptionalProvider) or provider.connected


@dataclass(frozen=True)
class GitHubCodeSearch:
    """GitHub's code search: `GET /search/code`, at most 10 requests a minute."""

    store: RoadmapStore
    name: str = GITHUB_CODE
    kind: SearchKind = SearchKind.CODE

    def search(self, query: str) -> list[Hit]:
        found = self.store.search_code(
            query, limit=CONST_ROADMAP_ALTERNATIVES_REFERENCE_SEARCH_RESULTS
        )
        return [
            Hit(self.name, HitKind.CODE, query, repository=hit.repository, path=hit.path)
            for hit in found
        ]


def repositories_query(names: Sequence[str]) -> str:
    """The query that asks GitHub's repository search for the repositories `names`, forks too: a
    `repo:` qualifier for each name that is `owner/name`. GitHub reads several of them as any of
    them."""
    qualifiers = [f"repo:{name}" for name in names if is_repository_name(name)]
    return " ".join([*qualifiers, "fork:true"])


@dataclass(frozen=True)
class GitHubRepositorySearch:
    """GitHub's repository search: `GET /search/repositories`, at most 30 requests a minute. The
    step sends it one query for an item, `repositories_query` of the repositories of all code
    hits, and takes the facts of the answer: the gates then drop a repository with no read of its
    own. A repository names no file, so its hit is no link."""

    store: RoadmapStore
    name: str = GITHUB_REPOSITORY
    kind: SearchKind = SearchKind.FACT

    def search(self, query: str) -> list[Hit]:
        found = self.store.search_repositories(query, limit=_MAX_REPOSITORIES)
        return [
            Hit(self.name, HitKind.REPOSITORY, query, repository=facts.full_name, facts=facts)
            for facts in found
        ]


def count(provider: str, result: Result) -> None:
    """Add 1 to the counter of the reference step for `provider` and `result`."""
    emit(BRAIN_REFERENCES_TOTAL, 1, {"provider": provider, "result": result.value})


@contextmanager
def open_providers(
    store: RoadmapStore, *, private: bool, optional: Sequence[OptionalProvider] = ()
) -> Iterator[list[ReferenceProvider]]:
    """The providers of one run: the two GitHub providers, and each provider of `optional` that
    connects, for a public repository. A provider that is down at the start is left out, and the
    run goes on. Each connected provider is closed at the end."""
    providers: list[ReferenceProvider] = [GitHubCodeSearch(store), GitHubRepositorySearch(store)]
    with ExitStack() as connections:
        for provider in () if private else optional:
            try:
                provider.connect()
            except RoadmapMcpUnavailableError as exc:
                logger.warning(
                    "The reference provider %s is down at the start (%s), so the run leaves it "
                    "out.",
                    provider.name,
                    type(exc).__name__,
                )
                count(provider.name, Result.UNAVAILABLE)
                continue
            connections.callback(_close, provider)
            providers.append(provider)
        yield providers


def _close(provider: OptionalProvider) -> None:
    """Close the connection of `provider` at the end of the run. A close that fails is logged,
    and the run ends as it would."""
    try:
        provider.close()
    except RoadmapMcpUnavailableError as exc:
        logger.warning(
            "The reference provider %s did not close its connection (%s).",
            provider.name,
            type(exc.__cause__ or exc).__name__,
        )


__all__ = [
    "GITHUB_CODE",
    "GITHUB_REPOSITORY",
    "STEP",
    "WEB",
    "GitHubCodeSearch",
    "GitHubRepositorySearch",
    "Hit",
    "HitKind",
    "OptionalProvider",
    "ReferenceProvider",
    "Result",
    "SearchKind",
    "count",
    "in_run",
    "open_providers",
    "repositories_query",
]
