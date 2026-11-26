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
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from urllib.parse import SplitResult, quote, urlsplit

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
from devops_cli.exceptions.git import (
    GitHubFileNotFoundError,
    GitHubOperationError,
    GitHubRateLimitError,
)
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
    STEP,
    WEB,
    Hit,
    HitKind,
    OptionalProvider,
    ReferenceProvider,
    Result,
    SearchKind,
    count,
    in_run,
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

_THREAD_NAME = "devops-roadmap-references"
_HTTPS = "https"
_GITHUB_HOST = "github.com"
# The path segment of a link to a file on GitHub, after the owner and the repository.
_BLOB = "blob"
# The provider of a link that a check shows from the job record of an earlier check.
RECORDED = "recorded"
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
    most 3 links of official documentation. `complete` says that the step ran to its end and each
    of its searches and reads answered. A step that did not run, that failed or that passed its
    bound is not complete: its missing links say nothing about the item."""

    permalinks: tuple[Reference, ...] = ()
    documentation: tuple[Reference, ...] = ()
    complete: bool = True

    @property
    def links(self) -> tuple[Reference, ...]:
        """Each link, the permalinks first."""
        return (*self.permalinks, *self.documentation)

    @property
    def urls(self) -> tuple[str, ...]:
        """The URL of each link, the permalinks first."""
        return tuple(link.url for link in self.links)


def _split(url: str) -> SplitResult | None:
    """The parts of `url`, or None for a text that the URL parser refuses."""
    try:
        return urlsplit(url)
    except ValueError:
        return None


def _is_plain_https(url: str) -> bool:
    """Whether `url` is an https URL written with the characters of a URL only, so it writes no
    markup into an issue."""
    parts = _split(url)
    return parts is not None and parts.scheme == _HTTPS and url == quote(url, safe=_URL_CHARS)


def _is_file_link(url: str) -> bool:
    """Whether `url` is a link to a file of a repository on GitHub."""
    parts = _split(url)
    if parts is None:
        return False
    segments = [segment for segment in parts.path.split("/") if segment]
    return (parts.hostname or "").lower() == _GITHUB_HOST and segments[2:3] == [_BLOB]


def recorded_references(record: str | None) -> References:
    """The links that `alternatives.refs` of a job record holds from an earlier check, as the
    block lists them: the links to files on GitHub as permalinks, and each other link as
    documentation. A check that writes no link of its own shows these, so its write leaves the
    links of the block as they are. A text that is no https URL is left out. The result is not
    complete: it is no result of a step."""
    urls = [url for url in (record or "").split() if _is_plain_https(url)]
    return References(
        tuple(Reference(url, RECORDED, HitKind.CODE) for url in urls if _is_file_link(url)),
        tuple(
            Reference(url, RECORDED, HitKind.DOCUMENTATION)
            for url in urls
            if not _is_file_link(url)
        ),
        complete=False,
    )


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
    then sends no new request. `failed` says that a search or a read of the item did not answer,
    so the links of the item are not complete. One item reads at most 3 documentation pages, so
    the candidates keep their fact reads."""

    code_searches: int = 0
    fact_reads: int = 0
    page_reads: int = 0
    failed: bool = False
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

    def take_page_read(self) -> bool:
        """Whether one more read of a documentation page fits; if it does, counts it. A page read
        is a fact read too."""
        if self.page_reads >= CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_LINKS:
            return False
        if not self.take_fact_read():
            return False
        self.page_reads += 1
        return True

    def fail(self) -> None:
        self.failed = True

    def stop(self) -> None:
        self.stopped.set()


# ── Searches ──────────────────────────────────────────────────────────────────


def _ask(provider: ReferenceProvider, query: str, number: int) -> list[Hit] | None:
    """The hits of `query` from `provider`, or None when the search fails. Counts the search."""
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
        return None
    count(provider.name, Result.HIT if hits else Result.EMPTY)
    return hits


def _search(
    queries: Sequence[str], providers: Sequence[ReferenceProvider], budget: Budget, number: int
) -> list[Hit]:
    """The hits of `queries`: each query goes to one code search provider of the run, in turn.
    A query that an optional provider fails goes to the first provider, the GitHub code search,
    when the bound has a code search for it. A query that no provider answers marks the links
    of the item as not complete."""
    hits: list[Hit] = []
    for index, query in enumerate(queries):
        code = [p for p in providers if p.kind is SearchKind.CODE and in_run(p)]
        if not code or not budget.take_code_search():
            continue
        provider = code[index % len(code)]
        found = _ask(provider, query, number)
        if found is None and provider is not code[0] and budget.take_code_search():
            found = _ask(code[0], query, number)
        if found is None:
            budget.fail()
        hits += found or []
    return hits


def _search_facts(
    hits: Sequence[Hit], providers: Sequence[ReferenceProvider], budget: Budget, number: int
) -> dict[str, ReferenceFacts]:
    """The facts of the repositories of `hits`, by repository name in lower case: one search of
    each repository search provider for all of them, which leaves the reads that verify the
    links. A repository that no search answers has no entry: the read of its head then gives its
    facts, so a failed repository search loses no link."""
    names = list(dict.fromkeys(hit.repository for hit in hits))
    known: dict[str, ReferenceFacts] = {}
    if not names:
        return known
    reserve = CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_LINKS
    for provider in providers:
        skipped = provider.kind is SearchKind.CODE or not in_run(provider)
        if skipped or not budget.take_fact_read(reserve=reserve):
            continue
        for found in _ask(provider, repositories_query(names), number) or []:
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
    characters of a URL only. A text that the URL parser refuses is no URL."""
    parts = _split(url)
    host = (parts.hostname or "").lower() if parts is not None else ""
    return _is_plain_https(url) and host in CONST_ROADMAP_ALTERNATIVES_REFERENCE_DOC_DOMAINS


def _documentation(
    hits: Sequence[Hit], request: ReferenceRequest, linked: frozenset[str], budget: Budget
) -> tuple[Reference, ...]:
    """The verified documentation links, at most 3: the documentation hits of the providers and
    the sources of the check whose host is on the allowlist, that the item does not link, and
    whose page answers. The request is for the URL as its source gave it: a host answers the page
    of a directory with its last slash only, and a redirect is no answer. The step reads at most
    3 pages for an item."""
    pages = [(hit.url, hit.provider) for hit in hits if hit.kind is HitKind.DOCUMENTATION]
    pages += [(url, WEB) for url in request.sources]
    kept: dict[str, Reference] = {}
    for url, provider in pages:
        key = normalize_url(url)
        if key in kept or key in linked or not _on_allowlist(url):
            continue
        full = len(kept) >= CONST_ROADMAP_ALTERNATIVES_REFERENCE_MAX_LINKS
        if full or not budget.take_page_read():
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
            budget.fail()
            continue
        if answers:
            kept[key] = Reference(url, provider, HitKind.DOCUMENTATION)
    return tuple(kept.values())


# ── Candidates ────────────────────────────────────────────────────────────────


def _read_facts(
    store: RoadmapStore, hit: Hit, number: int, budget: Budget
) -> ReferenceFacts | None:
    """The reference facts of the repository of `hit`, or None when the read fails or GitHub has
    no such repository. A failed read marks the links of the item as not complete."""
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
        budget.fail()
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
        facts = _read_facts(store, hit, request.number, budget)
        if facts is None or facts.head_sha is None or facts_gate(facts, request.now) is not None:
            continue
        candidates.append(_with_rank_facts(Candidate(hit, facts), request, budget))
    return candidates


# ── Verification ──────────────────────────────────────────────────────────────


def _lines_of(text: str, query: str) -> tuple[int, int]:
    """The line range of the link into `text`: from the first line that holds the longest word of
    `query`, or else any word of it, or else line 1, for the span of one link. A line ends at a
    line feed only, as GitHub counts the lines of a file: `str.splitlines` also ends a line at a
    form feed and at U+2028. A last line feed opens no line."""
    lines = [line.casefold() for line in text.removesuffix("\n").split("\n")]
    words = sorted({word.casefold() for word in query.split()}, key=len, reverse=True)
    matches = (
        number for word in words for number, line in enumerate(lines, start=1) if word in line
    )
    first = next(matches, 1)
    last = min(first + CONST_ROADMAP_ALTERNATIVES_REFERENCE_SPAN_LINES - 1, len(lines))
    return first, max(first, last)


def _permalink(
    store: RoadmapStore, candidate: Candidate, number: int, budget: Budget
) -> str | None:
    """The permalink of `candidate` at the head commit of its repository, or None when
    `repository_file` does not answer its path at that commit. A read that fails for another
    cause than a missing file marks the links of the item as not complete."""
    hit, sha = candidate.hit, candidate.facts.head_sha
    if sha is None:
        return None
    try:
        text = store.repository_file(hit.path, ref=sha, repository=hit.repository)
    except GitHubRateLimitError:
        raise
    except GitHubFileNotFoundError:
        logger.info(
            "The reference step of #%d dropped %s of %s: the head commit does not hold the path.",
            number,
            hit.path,
            hit.repository,
        )
        return None
    except GitHubOperationError as exc:
        logger.warning(
            "The reference step of #%d could not read %s of %s at its head commit (%s).",
            number,
            hit.path,
            hit.repository,
            type(exc).__name__,
        )
        budget.fail()
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
        url = _permalink(store, candidate, number, budget)
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
    permalinks = tuple(reference for _, reference in kept)
    return References(permalinks, documentation, complete=not budget.failed)


class _Ended(StrEnum):
    """How the work of a step ended with no result: it passed the bound, or its thread ended with
    an error that is no project error."""

    BOUND = "bound"
    ERROR = "error"


def _bounded(work: Callable[[], References], budget: Budget, seconds: float) -> References | _Ended:
    """What `work` returns, or how it ended with no result.

    The work runs in a daemon thread of its own, with the context of the caller, and the caller
    waits `seconds` for it. A project error of the work raises here. Another error ends the
    thread, which reports it with its trace through `threading.excepthook`, and gives
    `_Ended.ERROR`: the error of the work is never read as the bound.

    After the bound the budget is stopped, and the result is `_Ended.BOUND`. The work then sends
    no new request. A request in flight is not cut: it goes on until its own timeout, and the
    thread ends after it. The thread is a daemon, so it never holds the interpreter at its
    exit."""
    done: list[References] = []
    failed: list[DevOpsCLIError] = []

    def run() -> None:
        try:
            done.append(work())
        except DevOpsCLIError as exc:
            failed.append(exc)

    worker = threading.Thread(
        target=contextvars.copy_context().run, args=(run,), name=_THREAD_NAME, daemon=True
    )
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        budget.stop()
        return _Ended.BOUND
    if failed:
        raise failed[0]
    return done[0] if done else _Ended.ERROR


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
        quota, another error of a provider and a passed time bound give a warning and a result
        that is not complete, with no link. Mode `plan` writes each link to the log and counts
        it. Mode `off` runs nothing, so its result is not complete either."""
        stopped = References(complete=False)
        if self.mode == "off":
            return stopped
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
            return stopped
        if isinstance(found, _Ended):
            self._log_ended(request.number, found)
            return stopped
        if self.mode == "plan":
            self._log_plan(request.number, found)
        return found

    def _log_ended(self, number: int, ended: _Ended) -> None:
        if ended is _Ended.BOUND:
            logger.warning(
                "The reference step of #%d passed its bound of %.0f s and gave no link.",
                number,
                self.seconds,
            )
            count(STEP, Result.TIMEOUT)
            return
        logger.warning(
            "The reference step of #%d ended with an error that is no project error, and gave "
            "no link. Its thread reported the error with its trace.",
            number,
        )
        count(STEP, Result.FAILED)

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
    "recorded_references",
]
