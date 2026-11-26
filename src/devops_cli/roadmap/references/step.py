"""The reference step of one item (#4672): the searches, the gates, the rank and the verified
links, inside the bounds of the step.

**The run.** The step merges the rule queries of the item text with the queries of the model reply
and sends each query to one code search provider, in turn. One repository search then gives the
facts of the repositories of all code hits. The step keeps the code hits that pass the gates
(`candidates`), the repositories with the most stars first. For each one it reads the head commit
and the rank facts, while the bound allows. It ranks the candidates and verifies the file of each
one at the head commit of its repository with `repository_file`. A verified file gives a permalink from `render_permalink`. The link starts at
the first line that holds the longest word of the query, or at line 1. The step keeps at most
`CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_LINKS` permalinks.

**Documentation.** A documentation hit is a page that a provider found or a source of the check.
The step keeps it only when its URL is `https`, its host is on
`CONST_ROADMAP_ALTERNATIVES_REFERENCE_DOC_DOMAINS`, the item does not link it already and one
request of the page through `devops_cli.http.entry` at the public egress level answers 200.

**Bounds.** One item gets at most 3 code searches and 15 fact reads, and the step makes no
generative call. A fact read is each request that is no code search. The reads of the candidates
leave a reserve for the verification of the links. The step runs in a thread of its own and its
caller waits at most `CONST_ROADMAP_ALTERNATIVES_REFERENCE_SECONDS`. After that the step is
stopped: it sends no new request, and its caller gets no link.

**It fails soft.** A failed search, a failed read, a spent GitHub quota and a passed time bound
each give a warning in the log and fewer links, never an error of the check. The counter
`devops_cli_brain_references_total` counts each search by provider and result.

**Modes.** `off` runs nothing. `plan` writes each verified link to the log and counts it with the
result `verified`. `on` gives the links to the check, whose writer writes them and counts each with
`linked`. In every mode the step itself writes nothing to GitHub.

**The decision point.** With a chain of `brain.reference_relevance`, the step asks it about each
permalink that it keeps. The point runs in shadow, so its band changes no link.
"""

from __future__ import annotations

import contextvars
import logging
import threading
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

import httpx2
from pydantic import ValidationError

from devops_cli.ai.web_search import normalize_url
from devops_cli.citation import render_permalink
from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_REFERENCE_DOC_DOMAINS,
    CONST_ROADMAP_ALTERNATIVES_REFERENCE_DOC_TIMEOUT_SECONDS,
    CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_CODE_SEARCHES,
    CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_FACT_READS,
    CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_LINKS,
    CONST_ROADMAP_ALTERNATIVES_REFERENCE_SECONDS,
    CONST_ROADMAP_ALTERNATIVES_REFERENCE_SPAN_LINES,
)
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from devops_cli.roadmap.inventory import (
    Inventory,
    direct_dependents,
    newest_pypi_release,
    project_of,
)
from devops_cli.roadmap.page_fetch import named_urls
from devops_cli.roadmap.references.candidates import Candidate, facts_gate, hit_gate, ranked
from devops_cli.roadmap.references.providers import (
    WEB,
    Hit,
    HitKind,
    OptionalProvider,
    ReferenceProvider,
    Result,
    SearchKind,
    count,
    open_providers,
    repositories_query,
)
from devops_cli.roadmap.references.queries import merged_queries, rule_queries
from devops_cli.roadmap.references.relevance import RelevanceCase

if TYPE_CHECKING:
    from devops_cli.config.defaults import RowMode
    from devops_cli.roadmap.decision_point import ResolverChain
    from devops_cli.roadmap.stores.store import ReferenceFacts, RoadmapStore

logger = logging.getLogger(__name__)

# The provider label of a step that passed its time bound.
_STEP = "step"
_HTTPS = "https"
# The reserved and the unreserved punctuation of a URL (RFC 3986), and the percent sign.
_URL_CHARS = ":/?#[]@!$&'()*+,;=-._~%"
# The failed reads of deps.dev that the step takes as no fact.
_READ_ERRORS = (httpx2.HTTPError, ValidationError)


@dataclass(frozen=True)
class Reference:
    """One verified link: its URL, the provider that found it and its kind."""

    url: str
    provider: str
    kind: HitKind


@dataclass(frozen=True)
class References:
    """The verified links of one item: at most 3 permalinks of reference implementations, and at
    most 3 links of official documentation."""

    permalinks: tuple[Reference, ...] = ()
    documentation: tuple[Reference, ...] = ()

    @property
    def links(self) -> tuple[Reference, ...]:
        """Each link, the permalinks first."""
        return (*self.permalinks, *self.documentation)

    @property
    def urls(self) -> tuple[str, ...]:
        """The URL of each link, the permalinks first."""
        return tuple(link.url for link in self.links)


@dataclass(frozen=True)
class ReferenceRequest:
    """What the step reads of one item: its number and title, `text`, its body outside the block
    of the job, the name of its repository and whether that repository is private, the time, the
    `reference_queries` of the model reply, the `sources` that the tools of the check returned,
    and the inventory of the repository."""

    number: int
    title: str
    text: str
    repo: str
    now: datetime
    private: bool = False
    model_queries: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    inventory: Inventory | None = None


@dataclass
class Budget:
    """The requests that the step of one item may still send. `stop` ends the budget: the step
    then sends no new request."""

    code_searches: int = 0
    fact_reads: int = 0
    stopped: threading.Event = field(default_factory=threading.Event)

    def take_code_search(self) -> bool:
        """Whether one more code search fits; if it does, counts it."""
        limit = CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_CODE_SEARCHES
        if self.stopped.is_set() or self.code_searches >= limit:
            return False
        self.code_searches += 1
        return True

    def take_fact_read(self, *, reserve: int = 0) -> bool:
        """Whether one more fact read fits and leaves `reserve` reads; if it does, counts it."""
        limit = CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_FACT_READS - reserve
        if self.stopped.is_set() or self.fact_reads >= limit:
            return False
        self.fact_reads += 1
        return True

    def stop(self) -> None:
        self.stopped.set()


# ── Searches ──────────────────────────────────────────────────────────────────


def _ask(provider: ReferenceProvider, query: str, number: int) -> list[Hit]:
    """The hits of `query` from `provider`, none when the search fails. Counts the search."""
    try:
        hits = provider.search(query)
    except GitHubRateLimitError:
        count(provider.name, Result.FAILED)
        raise
    except DevOpsCLIError as exc:
        logger.warning(
            "A search of the reference step of #%d failed at %s (%s).",
            number,
            provider.name,
            type(exc).__name__,
        )
        count(provider.name, Result.FAILED)
        return []
    count(provider.name, Result.HIT if hits else Result.EMPTY)
    return hits


def _search(
    queries: Sequence[str], providers: Sequence[ReferenceProvider], budget: Budget, number: int
) -> list[Hit]:
    """The hits of `queries`: each query goes to one code search provider, in turn."""
    code = [provider for provider in providers if provider.kind is SearchKind.CODE]
    hits: list[Hit] = []
    for index, query in enumerate(queries):
        if code and budget.take_code_search():
            hits += _ask(code[index % len(code)], query, number)
    return hits


def _search_facts(
    hits: Sequence[Hit], providers: Sequence[ReferenceProvider], budget: Budget, number: int
) -> dict[str, ReferenceFacts]:
    """The facts of the repositories of `hits`, by repository name in lower case: one search of
    each repository search provider for all of them, which leaves the reads that verify the
    links. A repository that no search answers has no entry."""
    names = list(dict.fromkeys(hit.repository for hit in hits))
    known: dict[str, ReferenceFacts] = {}
    if not names:
        return known
    reserve = CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_LINKS
    for provider in providers:
        if provider.kind is SearchKind.CODE or not budget.take_fact_read(reserve=reserve):
            continue
        for found in _ask(provider, repositories_query(names), number):
            if found.facts is not None:
                known[found.repository.casefold()] = found.facts
    return known


# ── Documentation ─────────────────────────────────────────────────────────────


def _page_answers(url: str) -> bool:
    """Whether one request of the page at `url` answers 200. A redirect is no answer: its target
    can be a host that is not on the allowlist."""
    with (
        http_client(EgressLevel.PUBLIC) as client,
        client.stream(
            "GET", url, timeout=CONST_ROADMAP_ALTERNATIVES_REFERENCE_DOC_TIMEOUT_SECONDS
        ) as response,
    ):
        return response.status_code == httpx2.codes.OK


def _on_allowlist(url: str) -> bool:
    """Whether `url` is an https URL of a host on the documentation allowlist, written with the
    characters of a URL only, so no link writes markup into an issue."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return (
        parts.scheme == _HTTPS
        and host in CONST_ROADMAP_ALTERNATIVES_REFERENCE_DOC_DOMAINS
        and url == quote(url, safe=_URL_CHARS)
    )


def _documentation(
    hits: Sequence[Hit], request: ReferenceRequest, linked: frozenset[str], budget: Budget
) -> tuple[Reference, ...]:
    """The verified documentation links: the documentation hits of the providers and the sources
    of the check whose host is on the allowlist, that the item does not link, and whose page
    answers."""
    pages = [(hit.url, hit.provider) for hit in hits if hit.kind is HitKind.DOCUMENTATION]
    pages += [(url, WEB) for url in request.sources]
    kept: dict[str, Reference] = {}
    for raw, provider in pages:
        if len(kept) >= CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_LINKS:
            break
        url = normalize_url(raw)
        if url in kept or url in linked or not _on_allowlist(url):
            continue
        if not budget.take_fact_read():
            break
        try:
            answers = _page_answers(url)
        except (httpx2.HTTPError, DevOpsCLIError) as exc:
            logger.warning(
                "The reference step of #%d could not read a documentation page of %s (%s).",
                request.number,
                urlsplit(url).hostname,
                type(exc).__name__,
            )
            count(provider, Result.FAILED)
            continue
        if answers:
            kept[url] = Reference(url, provider, HitKind.DOCUMENTATION)
    return tuple(kept.values())


# ── Candidates ────────────────────────────────────────────────────────────────


def _read_facts(store: RoadmapStore, hit: Hit, number: int) -> ReferenceFacts | None:
    """The reference facts of the repository of `hit`, or None when the read fails or GitHub has
    no such repository."""
    try:
        return store.reference_facts(hit.repository)
    except GitHubRateLimitError:
        raise
    except GitHubOperationError as exc:
        logger.warning(
            "The reference step of #%d could not read the facts of %s (%s).",
            number,
            hit.repository,
            type(exc).__name__,
        )
        return None


def _code_hits(
    hits: Sequence[Hit], request: ReferenceRequest, linked_projects: frozenset[str]
) -> list[Hit]:
    """The hits that pass the gates of a hit, one for each repository, in the order of the hits:
    a code hit, of another repository than this one, that the item does not link."""
    seen: set[str] = set()
    kept: list[Hit] = []
    for hit in hits:
        key = hit.repository.casefold()
        if key not in seen and hit_gate(hit, own=request.repo, linked=linked_projects) is None:
            seen.add(key)
            kept.append(hit)
    return kept


def _by_known_facts(
    hits: Sequence[Hit], known: dict[str, ReferenceFacts], now: datetime
) -> list[Hit]:
    """`hits` without each one whose repository fails a gate on the facts that a repository
    search gave, so it costs no read of its own. The repositories with the most stars come first,
    so the reads of the bound go to them, and a repository with no known facts comes last, in the
    order of the hits."""
    kept = [
        hit
        for hit in hits
        if (facts := known.get(hit.repository.casefold())) is None or facts_gate(facts, now) is None
    ]
    return sorted(kept, key=lambda hit: -_known_stars(hit, known))


def _known_stars(hit: Hit, known: dict[str, ReferenceFacts]) -> int:
    facts = known.get(hit.repository.casefold())
    return facts.stars if facts is not None else -1


def _with_rank_facts(candidate: Candidate, request: ReferenceRequest, budget: Budget) -> Candidate:
    """`candidate` with the two deps.dev facts of its rank, each 0 when its read does not fit the
    bound or fails."""
    project = project_of(candidate.facts.url)
    reserve = CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_LINKS
    if project is None or not budget.take_fact_read(reserve=reserve):
        return candidate
    try:
        shared = request.inventory.shared_packages(project) if request.inventory else 0
        release = newest_pypi_release(project)
        dependents = 0
        if release is not None and budget.take_fact_read(reserve=reserve):
            dependents = direct_dependents(*release)
    except _READ_ERRORS as exc:
        logger.warning(
            "The reference step of #%d could not read the deps.dev facts of %s (%s).",
            request.number,
            candidate.hit.repository,
            type(exc).__name__,
        )
        return candidate
    return replace(candidate, shared=shared, dependents=dependents)


def _candidates(
    store: RoadmapStore, hits: Sequence[Hit], request: ReferenceRequest, budget: Budget
) -> list[Candidate]:
    """A candidate for each of `hits` whose repository passes the gates at its head, with the
    facts of its rank, while the bound has a read that the verification does not need. The read
    of a candidate gives its head commit and whether it holds tests."""
    reserve = CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_LINKS
    candidates: list[Candidate] = []
    for hit in hits:
        if not budget.take_fact_read(reserve=reserve):
            break
        facts = _read_facts(store, hit, request.number)
        if facts is None or facts.head_sha is None or facts_gate(facts, request.now) is not None:
            continue
        candidates.append(_with_rank_facts(Candidate(hit, facts), request, budget))
    return candidates


# ── Verification ──────────────────────────────────────────────────────────────


def _lines_of(text: str, query: str) -> tuple[int, int]:
    """The line range of the link into `text`: from the first line that holds the longest word of
    `query`, or else any word of it, or else line 1, for the span of one link."""
    lines = [line.casefold() for line in text.splitlines()]
    words = sorted({word.casefold() for word in query.split()}, key=len, reverse=True)
    matches = (
        number for word in words for number, line in enumerate(lines, start=1) if word in line
    )
    first = next(matches, 1)
    last = min(first + CONST_ROADMAP_ALTERNATIVES_REFERENCE_SPAN_LINES - 1, max(len(lines), 1))
    return first, max(first, last)


def _permalink(store: RoadmapStore, candidate: Candidate, number: int) -> str | None:
    """The permalink of `candidate` at the head commit of its repository, or None when
    `repository_file` does not answer its path at that commit."""
    hit, sha = candidate.hit, candidate.facts.head_sha
    if sha is None:
        return None
    try:
        text = store.repository_file(hit.path, ref=sha, repository=hit.repository)
    except GitHubRateLimitError:
        raise
    except GitHubOperationError as exc:
        logger.info(
            "The reference step of #%d dropped %s of %s: the head commit does not answer the "
            "path (%s).",
            number,
            hit.path,
            hit.repository,
            type(exc).__name__,
        )
        return None
    # A path is text of another repository, and git allows a line break and markup in it. The
    # link holds the path percent-encoded, so no path writes markup into an issue.
    return render_permalink(hit.repository, sha, quote(hit.path), _lines_of(text, hit.query))


def _verified(
    store: RoadmapStore, candidates: Sequence[Candidate], number: int, budget: Budget
) -> list[tuple[Candidate, Reference]]:
    """The first candidates, in their order, whose permalink is verified, at most 3."""
    kept: list[tuple[Candidate, Reference]] = []
    for candidate in candidates:
        if len(kept) >= CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_LINKS:
            break
        if not budget.take_fact_read():
            break
        url = _permalink(store, candidate, number)
        if url is not None:
            kept.append((candidate, Reference(url, candidate.hit.provider, HitKind.CODE)))
    return kept


def _shadow_relevance(
    chain: ResolverChain[RelevanceCase] | None,
    kept: Sequence[tuple[Candidate, Reference]],
    request: ReferenceRequest,
    budget: Budget,
) -> None:
    """Ask the decision point about each kept link. The point runs in shadow: the chain writes
    its record and its count, and no band changes a link. A private repository asks nothing."""
    if chain is None or request.private:
        return
    for candidate, _ in kept:
        if budget.stopped.is_set():
            return
        chain.decide(
            RelevanceCase(
                need=request.title,
                path=candidate.hit.path,
                description=candidate.facts.description,
                license=candidate.facts.license or "",
                symbols=candidate.hit.query,
            ),
            subject=f"#{request.number}",
        )


# ── The step ──────────────────────────────────────────────────────────────────


def find_references(
    store: RoadmapStore,
    request: ReferenceRequest,
    providers: Sequence[ReferenceProvider],
    budget: Budget,
    *,
    relevance: ResolverChain[RelevanceCase] | None = None,
) -> References:
    """The verified links of the item of `request`, inside `budget`. Raises
    `GitHubRateLimitError` when the GitHub quota is spent."""
    queries = merged_queries(
        rule_queries(request.text),
        request.model_queries,
        limit=CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_CODE_SEARCHES,
    )
    named = named_urls(request.text)
    linked_projects = frozenset(project for url in named if (project := project_of(url)))
    hits = _search(queries, providers, budget, request.number)
    documentation = _documentation(hits, request, named, budget)
    code_hits = _code_hits(hits, request, linked_projects)
    known = _search_facts(code_hits, providers, budget, request.number)
    gated = _by_known_facts(code_hits, known, request.now)
    rank = ranked(_candidates(store, gated, request, budget))
    kept = _verified(store, rank, request.number, budget)
    _shadow_relevance(relevance, kept, request, budget)
    return References(tuple(reference for _, reference in kept), documentation)


def _bounded(work: Callable[[], References], budget: Budget, seconds: float) -> References | None:
    """What `work` returns, or None when it does not end in `seconds`. The work runs in a thread
    of its own with the context of the caller, and an error of the work raises here. After the
    bound the budget is stopped, so the work sends no new request and its thread ends after the
    request in flight."""
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="devops-roadmap-references")
    future = pool.submit(contextvars.copy_context().run, work)
    try:
        return future.result(timeout=seconds)
    except TimeoutError:
        if future.done():
            raise
        budget.stop()
        return None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


@dataclass(frozen=True)
class ReferenceStep:
    """The reference step of one run: its mode, the providers of the run, the chain of the
    decision point when it runs, and the time bound of one item."""

    mode: RowMode
    providers: tuple[ReferenceProvider, ...] = ()
    relevance: ResolverChain[RelevanceCase] | None = None
    seconds: float = CONST_ROADMAP_ALTERNATIVES_REFERENCE_SECONDS

    def run(self, store: RoadmapStore, request: ReferenceRequest) -> References:
        """The verified links of the item of `request`. The step fails soft: a spent GitHub
        quota, another error of a provider and a passed time bound give no link and a warning.
        Mode `plan` writes each link to the log and counts it, and mode `off` runs nothing."""
        if self.mode == "off":
            return References()
        budget = Budget()
        try:
            found = _bounded(
                lambda: find_references(
                    store, request, self.providers, budget, relevance=self.relevance
                ),
                budget,
                self.seconds,
            )
        except DevOpsCLIError as exc:
            logger.warning(
                "The reference step of #%d stopped with no link (%s).",
                request.number,
                type(exc).__name__,
            )
            return References()
        if found is None:
            logger.warning(
                "The reference step of #%d passed its bound of %.0f s and gave no link.",
                request.number,
                self.seconds,
            )
            count(_STEP, Result.TIMEOUT)
            return References()
        if self.mode == "plan":
            self._log_plan(request.number, found)
        return found

    @staticmethod
    def _log_plan(number: int, found: References) -> None:
        for link in found.links:
            logger.info(
                "The reference step of #%d verified %s (%s, mode plan: not written).",
                number,
                link.url,
                link.provider,
            )
            count(link.provider, Result.VERIFIED)


@contextmanager
def open_reference_step(
    store: RoadmapStore,
    *,
    mode: RowMode,
    private: bool,
    optional: Sequence[OptionalProvider] = (),
    relevance: ResolverChain[RelevanceCase] | None = None,
) -> Iterator[ReferenceStep]:
    """The reference step of one run in `mode`, with the providers that `open_providers` gives:
    mode `off` opens no provider."""
    if mode == "off":
        yield ReferenceStep(mode)
        return
    with open_providers(store, private=private, optional=optional) as providers:
        yield ReferenceStep(mode, tuple(providers), relevance)


__all__ = [
    "Budget",
    "Reference",
    "ReferenceRequest",
    "ReferenceStep",
    "References",
    "find_references",
    "open_reference_step",
]
