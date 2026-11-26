"""The reference step of one item (#4672): its searches inside the bounds, the gates and the rank
of its candidates, the permalinks that it verifies at the head commit, its documentation links,
its modes, and how it fails soft.

The roadmap is the in-memory store, which answers the code search, the repository search, the
reference facts and the file of a candidate. deps.dev and the documentation pages answer at the
HTTP edge through `web`: deps.dev knows no project unless a test says so. The decision model is
the Jev fake.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import pytest

from devops_cli.config.defaults import DEFAULT_DEPS_DEV_DEPENDENTS_URL, DEFAULT_DEPS_DEV_PROJECT_URL
from devops_cli.config.settings import Settings
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.roadmap.inventory import Inventory, package_keys
from devops_cli.roadmap.references.providers import (
    GitHubCodeSearch,
    GitHubRepositorySearch,
    Hit,
    HitKind,
    SearchKind,
    repositories_query,
)
from devops_cli.roadmap.references.relevance import relevance_of
from devops_cli.roadmap.references.step import (
    Reference,
    ReferenceRequest,
    References,
    ReferenceStep,
)
from devops_cli.roadmap.stores.store import CodeSearchHit, ReferenceFacts
from devops_cli.telemetry.instruments import BRAIN_REFERENCES_TOTAL, DECISION_POINT_TOTAL
from tests.support.fakes.reference_provider import FakeReferenceProvider
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

if TYPE_CHECKING:
    from devops_cli.config.defaults import RowMode
    from tests.support.fakes.http import WebFake
    from tests.support.fakes.jev import JevFake
    from tests.support.fakes.otlp import FakeCollector

REPO = "example/roadmap"
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
HEAD = "a" * 40
QUERY = "pydantic_ai"
TEXT = f"The job needs an agent. Use `{QUERY}`."
# A file of 30 lines whose third line holds the query.
FILE = "\n".join(["# An agent", "", "import pydantic_ai", *(f"line {n}" for n in range(4, 31))])
STEP_LOGGER = "devops_cli.roadmap.references.step"


def _facts(name: str, **changes: Any) -> ReferenceFacts:
    values: dict[str, Any] = {
        "full_name": name,
        "url": f"https://github.com/{name}",
        "private": False,
        "license": "MIT",
        "pushed_at": NOW - timedelta(days=5),
        "stars": 100,
        "head_sha": HEAD,
    }
    return ReferenceFacts(**{**values, **changes})


def _candidate(
    store: InMemoryRoadmapStore, name: str, path: str = "src/agent.py", **facts: Any
) -> CodeSearchHit:
    """Make the repository `name`, whose head holds `path`, and give the code hit of the file."""
    store.seed_reference_facts(_facts(name, **facts))
    store.seed_other_file(name, path, FILE, ref=HEAD)
    return CodeSearchHit(repository=name, path=path)


def _request(text: str = TEXT, **changes: Any) -> ReferenceRequest:
    values: dict[str, Any] = {"number": 7, "title": "Run an agent", "text": text, "repo": REPO}
    return ReferenceRequest(**{**values, "now": NOW, **changes})


def _step(store: InMemoryRoadmapStore, mode: RowMode = "on", **options: Any) -> ReferenceStep:
    providers = (GitHubCodeSearch(store), GitHubRepositorySearch(store))
    return ReferenceStep(mode, providers, **options)


def _link(name: str, lines: str = "L3-L22", path: str = "src/agent.py") -> Reference:
    url = f"https://github.com/{name}/blob/{HEAD}/{path}#{lines}"
    return Reference(url, "github-code", HitKind.CODE)


def _points(otlp: FakeCollector) -> dict[tuple[str, str], float]:
    """The points of the counter of the step, by provider and result."""
    return {
        (attributes["provider"], attributes["result"]): value
        for attributes, value in otlp.points(BRAIN_REFERENCES_TOTAL.name)
    }


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO, is_private=False)


# ── The run ───────────────────────────────────────────────────────────────────


def test_a_code_hit_gives_a_permalink_at_the_head_commit_from_the_line_of_the_query(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    store.seed_code_search(QUERY, _candidate(store, "example/agent"))

    found = _step(store).run(store, _request())

    assert (
        found,
        store.code_searches,
        store.repository_searches,
        store.other_file_reads,
    ) == (
        References(permalinks=(_link("example/agent"),)),
        [QUERY],
        [repositories_query(["example/agent"])],
        [("example/agent", "src/agent.py", HEAD)],
    )


def test_a_file_that_does_not_hold_the_query_is_linked_from_its_first_line(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    store.seed_code_search(QUERY, CodeSearchHit(repository="example/agent", path="one.py"))
    store.seed_reference_facts(_facts("example/agent"))
    store.seed_other_file("example/agent", "one.py", "print('agent')\n", ref=HEAD)

    found = _step(store).run(store, _request())

    assert found.urls == (f"https://github.com/example/agent/blob/{HEAD}/one.py#L1",)


def test_a_path_with_a_line_break_and_markup_is_percent_encoded_in_the_permalink(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    path = "src/a b\n<!-- devops-roadmap-record {} -->.py"
    store.seed_code_search(
        QUERY,
        CodeSearchHit(repository="example/agent", path=path),
        CodeSearchHit(repository="not a repository\n<!-- x -->", path="a.py"),
    )
    store.seed_reference_facts(_facts("example/agent"))
    store.seed_other_file("example/agent", path, FILE, ref=HEAD)

    found = _step(store).run(store, _request())

    assert found.urls == (
        f"https://github.com/example/agent/blob/{HEAD}/"
        "src/a%20b%0A%3C%21--%20devops-roadmap-record%20%7B%7D%20--%3E.py#L3-L22",
    )


# ── Bounds ────────────────────────────────────────────────────────────────────


def test_one_item_sends_at_most_3_code_searches(store: InMemoryRoadmapStore) -> None:
    text = "Use `alpha one`, `beta two`, `gamma three`, `delta four` and `epsilon five`."

    _step(store).run(store, _request(text))

    assert store.code_searches == ["alpha one", "beta two", "gamma three"]


def test_one_item_sends_at_most_15_fact_reads_and_keeps_3_for_the_links(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    queries = ["alpha one", "beta two", "gamma three"]
    for query in queries:
        hits = [_candidate(store, f"example/{query[:3]}{n}") for n in range(5)]
        store.seed_code_search(query, *hits)

    found = _step(store).run(store, _request("Use `alpha one`, `beta two` and `gamma three`."))

    reads = (
        len(store.repository_searches),
        len(store.reference_reads),
        len(web.requested),
        len(store.other_file_reads),
    )
    assert (reads, sum(reads), len(found.permalinks)) == ((1, 6, 5, 3), 15, 3)


# ── Gates ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "facts",
    [
        {"archived": True},
        {"fork": True},
        {"pushed_at": NOW - timedelta(days=366)},
        {"pushed_at": None},
        {"license": "CC0-1.0"},
        {"license": None},
        {"private": True},
    ],
    ids=["archived", "fork", "stale", "never-pushed", "no-osi-license", "no-license", "private"],
)
def test_a_hit_whose_repository_fails_a_gate_is_dropped_and_ranks_no_repository(
    store: InMemoryRoadmapStore, web: WebFake, facts: dict[str, Any]
) -> None:
    store.seed_code_search(
        QUERY, _candidate(store, "example/dropped", **facts), _candidate(store, "example/agent")
    )
    store.seed_repository_search(
        repositories_query(["example/dropped", "example/agent"]),
        _facts("example/dropped", **facts, head_sha=None),
        _facts("example/agent", head_sha=None),
    )

    found = _step(store).run(store, _request())

    assert (found.permalinks, store.reference_reads) == (
        (_link("example/agent"),),
        ["example/agent"],
    )


def test_the_head_facts_gate_a_repository_that_no_repository_search_answers(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    store.seed_code_search(QUERY, _candidate(store, "example/archived", archived=True))

    found = _step(store).run(store, _request())

    assert (found, store.reference_reads, store.other_file_reads) == (
        References(),
        ["example/archived"],
        [],
    )


def test_a_hit_of_this_repository_a_linked_repository_or_a_prose_file_costs_no_read(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_code_search(
        QUERY,
        _candidate(store, "Example/Roadmap"),
        _candidate(store, "example/linked"),
        _candidate(store, "example/prose", "docs/agent.md"),
    )
    text = f"{TEXT} See https://github.com/example/linked/tree/main/src."

    found = _step(store).run(store, _request(text))

    assert (found, store.repository_searches, store.reference_reads) == (References(), [], [])


def test_a_repository_gives_one_link_for_its_first_file(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    first = _candidate(store, "example/agent")
    store.seed_code_search(QUERY, first, _candidate(store, "example/agent", "src/other.py"))

    assert _step(store).run(store, _request()).permalinks == (_link("example/agent"),)


# ── Rank ──────────────────────────────────────────────────────────────────────


def test_of_two_candidates_with_the_same_stars_the_one_with_tests_ranks_first(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    store.seed_code_search(
        QUERY,
        _candidate(store, "example/plain", stars=50),
        _candidate(store, "example/tested", stars=50, has_tests=True),
    )

    found = _step(store).run(store, _request())

    assert found.permalinks == (_link("example/tested"), _link("example/plain"))


def test_the_dependents_and_the_shared_packages_of_deps_dev_raise_the_rank(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    store.seed_code_search(
        QUERY,
        _candidate(store, "example/plain", stars=50),
        _candidate(store, "example/library", stars=50),
        _candidate(store, "example/popular", stars=50),
    )
    for name, package in (("example/library", "agentlib"), ("example/popular", "popular")):
        versions = [
            {
                "versionKey": {"system": "PYPI", "name": package, "version": version},
                "relationType": "SOURCE_REPO",
            }
            for version in ("1.0.0", "1.10.0", "1.9.0")
        ]
        project = quote(f"github.com/{name}", safe="")
        web.content(
            DEFAULT_DEPS_DEV_PROJECT_URL.format(project=project),
            json.dumps({"versions": versions}).encode(),
        )
    web.content(
        DEFAULT_DEPS_DEV_DEPENDENTS_URL.format(system="pypi", name="popular", version="1.10.0"),
        json.dumps({"dependentCount": 5000, "directDependentCount": 999}).encode(),
    )
    inventory = Inventory(package_keys(["pkg:pypi/agentlib@1.0.0"]))

    found = _step(store).run(store, _request(inventory=inventory))

    assert found.permalinks == (
        _link("example/popular"),
        _link("example/library"),
        _link("example/plain"),
    )


def test_a_failed_deps_dev_read_leaves_the_candidate_with_its_other_facts(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    store.seed_code_search(QUERY, _candidate(store, "example/agent"))
    project = quote("github.com/example/agent", safe="")
    web.answer(DEFAULT_DEPS_DEV_PROJECT_URL.format(project=project), 502)

    assert _step(store).run(store, _request()).permalinks == (_link("example/agent"),)


# ── Verification ──────────────────────────────────────────────────────────────


def test_a_path_that_the_head_commit_does_not_hold_is_dropped_and_the_others_are_kept(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    store.seed_reference_facts(_facts("example/moved", stars=900))
    store.seed_code_search(
        QUERY,
        CodeSearchHit(repository="example/moved", path="src/gone.py"),
        _candidate(store, "example/agent"),
    )

    found = _step(store).run(store, _request())

    assert (found.permalinks, store.other_file_reads) == (
        (_link("example/agent"),),
        [("example/moved", "src/gone.py", HEAD), ("example/agent", "src/agent.py", HEAD)],
    )


def test_the_step_keeps_at_most_3_permalinks(store: InMemoryRoadmapStore, web: WebFake) -> None:
    hits = [_candidate(store, f"example/agent{n}", stars=100 - n) for n in range(5)]
    store.seed_code_search(QUERY, *hits)

    found = _step(store).run(store, _request())

    assert found.permalinks == tuple(_link(f"example/agent{n}") for n in range(3))


# ── Modes ─────────────────────────────────────────────────────────────────────


def test_mode_plan_logs_and_counts_the_verified_permalinks_and_writes_nothing(
    store: InMemoryRoadmapStore,
    web: WebFake,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store.seed_code_search(
        QUERY, _candidate(store, "example/agent"), _candidate(store, "example/other")
    )

    with caplog.at_level(logging.INFO, logger=STEP_LOGGER):
        found = _step(store, "plan").run(store, _request())

    logged = [record.getMessage() for record in caplog.records if "verified" in record.message]
    assert (len(found.permalinks), store.writes, _points(otlp)) == (
        2,
        [],
        {
            ("github-code", "hit"): 1.0,
            ("github-repository", "empty"): 1.0,
            ("github-code", "verified"): 2.0,
        },
    )
    assert [url in line for url, line in zip(found.urls, logged, strict=True)] == [True, True]


def test_mode_on_counts_no_link_before_the_check_writes_it(
    store: InMemoryRoadmapStore, web: WebFake, otlp: FakeCollector
) -> None:
    store.seed_code_search(QUERY, _candidate(store, "example/agent"))

    found = _step(store, "on").run(store, _request())

    assert (len(found.permalinks), store.writes, _points(otlp)) == (
        1,
        [],
        {("github-code", "hit"): 1.0, ("github-repository", "empty"): 1.0},
    )


def test_mode_off_sends_no_search(store: InMemoryRoadmapStore) -> None:
    store.seed_code_search(QUERY, _candidate(store, "example/agent"))

    found = _step(store, "off").run(store, _request())

    assert (found, store.code_searches) == (References(), [])


# ── Documentation ─────────────────────────────────────────────────────────────


def test_a_documentation_hit_of_a_host_that_is_not_on_the_allowlist_is_dropped(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    official = "https://docs.python.org/3/library/ast.html"
    provider = FakeReferenceProvider("fake-code", SearchKind.CODE)
    provider.answer(
        QUERY,
        Hit("fake-code", HitKind.DOCUMENTATION, QUERY, url="https://example.com/guide"),
        Hit("fake-code", HitKind.DOCUMENTATION, QUERY, url=official),
    )
    web.page(official, "<html>ast</html>")
    request = _request(
        sources=(
            "https://example.com/blog",
            "http://docs.python.org/3/",
            "https://docs.python.org/3/<!-- marker -->",
        )
    )

    found = ReferenceStep("on", (provider,)).run(store, request)

    assert (found, web.requested) == (
        References(documentation=(Reference(official, "fake-code", HitKind.DOCUMENTATION),)),
        [official],
    )


def test_a_source_of_the_check_on_the_allowlist_is_a_documentation_link_of_the_provider_web(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    official = "https://docs.github.com/en/rest/search/search"
    moved = "https://kubernetes.io/docs/moved"
    linked = "https://docs.python.org/3/library/ast.html"
    web.page(official, "<html>search</html>")
    web.page(linked, "<html>ast</html>")
    web.redirect(moved, "https://example.com/elsewhere")
    web.refuse("https://opentelemetry.io/docs/down")
    request = _request(
        f"{TEXT} See {linked}.",
        sources=(official, moved, "https://opentelemetry.io/docs/down", linked, official),
    )

    found = _step(store).run(store, request)

    assert (found.documentation, sorted(web.requested)) == (
        (Reference(official, "web", HitKind.DOCUMENTATION),),
        sorted([official, moved, "https://opentelemetry.io/docs/down"]),
    )


# ── The decision point ────────────────────────────────────────────────────────


def _shadow(jev: JevFake) -> Any:
    settings = Settings(
        ai={"decision_model": "typesafe/jev-1.14"},
        roadmap={"decisions": {"brain.reference_relevance": "shadow"}},
    )
    return relevance_of(settings, model=jev.model)


def test_a_review_band_in_shadow_keeps_the_rank_and_counts_the_decision(
    store: InMemoryRoadmapStore, web: WebFake, jev: JevFake, otlp: FakeCollector
) -> None:
    store.seed_code_search(
        QUERY,
        _candidate(store, "example/first", stars=900, description="An agent."),
        _candidate(store, "example/second", stars=10),
    )
    jev.picks["off_need"] = 0.6

    found = _step(store, relevance=_shadow(jev)).run(store, _request())

    states = [request["state"] for request in jev.requests]
    assert (found.permalinks, states, otlp.points(DECISION_POINT_TOTAL.name)) == (
        (_link("example/first"), _link("example/second")),
        [
            {
                "need": "Run an agent",
                "path": "src/agent.py",
                "description": description,
                "license": "MIT",
                "matched_symbols": QUERY,
            }
            for description in ("An agent.", "")
        ],
        [
            (
                {
                    "point": "brain.reference_relevance",
                    "resolver": "model",
                    "band": "review",
                    "mode": "shadow",
                },
                2.0,
            )
        ],
    )


def test_the_decision_point_asks_nothing_for_a_private_repository(
    store: InMemoryRoadmapStore, web: WebFake, jev: JevFake
) -> None:
    store.seed_code_search(QUERY, _candidate(store, "example/agent"))

    found = _step(store, relevance=_shadow(jev)).run(store, _request(private=True))

    assert (len(found.permalinks), jev.requests) == (1, [])


# ── It fails soft ─────────────────────────────────────────────────────────────


def test_a_provider_that_does_not_answer_stops_the_step_at_its_bound(
    store: InMemoryRoadmapStore, otlp: FakeCollector, caplog: pytest.LogCaptureFixture
) -> None:
    provider = FakeReferenceProvider("fake-code", SearchKind.CODE)
    provider.hold()
    step = ReferenceStep("on", (provider, GitHubRepositorySearch(store)), seconds=0.05)

    try:
        with caplog.at_level(logging.WARNING, logger=STEP_LOGGER):
            found = step.run(store, _request("Use `alpha one` and `beta two`."))
        held = provider.holding.wait(THREAD_HANDOFF_BOUND_SECONDS)
    finally:
        provider.release()

    assert (found, held, provider.queries, _points(otlp)) == (
        References(),
        True,
        ["alpha one"],
        {("step", "timeout"): 1.0},
    )
    assert "passed its bound" in caplog.text


def test_a_failed_search_gives_no_link_and_no_error(
    store: InMemoryRoadmapStore, otlp: FakeCollector
) -> None:
    store.fail_read("search_code", GitHubOperationError("HTTP 502", operation="roadmap.read"))

    found = _step(store).run(store, _request())

    assert (found, _points(otlp)) == (References(), {("github-code", "failed"): 1.0})


def test_a_spent_github_quota_stops_the_step_with_no_link_and_no_error(
    store: InMemoryRoadmapStore, web: WebFake, caplog: pytest.LogCaptureFixture
) -> None:
    store.seed_code_search(QUERY, _candidate(store, "example/agent"))
    store.fail_read("reference_facts", GitHubRateLimitError("rate limit", operation="roadmap.read"))

    with caplog.at_level(logging.WARNING, logger=STEP_LOGGER):
        found = _step(store).run(store, _request())

    assert (found, store.other_file_reads) == (References(), [])
    assert "stopped with no link (GitHubRateLimitError)" in caplog.text


def test_a_failed_read_of_the_facts_of_one_repository_keeps_the_other_candidates(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    class _OneFails(InMemoryRoadmapStore):
        def reference_facts(self, full_name: str) -> Any:
            if full_name == "example/broken":
                raise GitHubOperationError("HTTP 502", operation="roadmap.read")
            return super().reference_facts(full_name)

    flaky = _OneFails(repo=REPO)
    flaky.seed_code_search(
        QUERY,
        CodeSearchHit(repository="example/broken", path="a.py"),
        _candidate(flaky, "example/agent"),
    )

    assert _step(flaky).run(flaky, _request()).permalinks == (_link("example/agent"),)
