"""Only a search that a provider answered counts in the alternatives check (#4044).

A search outage must not give a "no tool" verdict. `cited_web_search` returns the text of the
answer and whether a provider answered. The alternatives tools record a `Search` only for an
answered search, and a reply that follows no answered search ends as a failed check, so the retry
delay applies.

The roadmap is the in-memory store, pydantic-ai's `FunctionModel` answers each model request from a
script, and Firecrawl is answered at the HTTP edge.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2
import pytest

from devops_cli.config.constants import CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES
from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_URL
from devops_cli.roadmap.alternatives import (
    AlternativesReply,
    AlternativesTools,
    Verdict,
    plan_alternatives,
)
from devops_cli.roadmap.refine.refine_investigation import InvestigationTools, cited_web_search
from devops_cli.roadmap.stores.store import AlternativesRecordKey, ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_alternatives import apply_alternatives
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
REASON = "No open tool covers the need."
SEARCH_URL = "https://example.com/scanner"
BODY = "The job needs to read every file of a directory."
SEARCH = call("search_web", query="scanner")
NONE = AlternativesReply(reason=REASON, verdict=Verdict.NONE)
NUMBER = 1
FAILED_TEXT = "The search failed: no provider answered."


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    """A public roadmap with one open item that has no check."""
    roadmap = InMemoryRoadmapStore(repo=REPO, is_private=False)
    number = roadmap.seed_issue(
        "Scan a directory",
        body=BODY,
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"},
    )
    assert number == NUMBER
    return roadmap


@pytest.fixture(autouse=True)
def firecrawl_only(
    config: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, web: WebFake
) -> None:
    """A chain of Firecrawl alone, with a key. `web` serves nothing at its URL, so each search
    fails until a test serves an answer."""
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config(search={"providers": ["firecrawl"]}, firecrawl={"api_key": "fc-test"})


def _serve(web: WebFake, *urls: str) -> None:
    """Make Firecrawl answer every search with one result for each of `urls`; no URL is an
    empty answer."""
    results = [{"title": f"Result {url}", "url": url, "description": "A scanner."} for url in urls]
    body = json.dumps({"success": True, "data": {"web": results}}).encode()
    web.content(DEFAULT_FIRECRAWL_SEARCH_URL, body)


def _fail_first_search(web: WebFake) -> None:
    """Answer the first request to Firecrawl with a server error, and each later one from the
    routes."""
    sent: list[httpx2.Request] = []

    def server(request: httpx2.Request) -> httpx2.Response | None:
        if str(request.url) != DEFAULT_FIRECRAWL_SEARCH_URL:
            return None
        sent.append(request)
        return httpx2.Response(500) if len(sent) == 1 else None

    web.serve(server)


def _record(store: InMemoryRoadmapStore, number: int) -> dict[Any, str]:
    item = store.item(number)
    assert item is not None
    return item.job_record


def _plan(store: InMemoryRoadmapStore, script: Script) -> Any:
    return plan_alternatives(store, repo=REPO, investigator=script.model(), now=NOW)


def test_shared_text_an_answer_an_empty_answer_and_a_failed_search_keep_their_text(
    web: WebFake, tmp_path: Path
) -> None:
    _serve(web, SEARCH_URL)
    answered = cited_web_search("scanner", set(), results=5)
    _serve(web)
    empty = cited_web_search("scanner", set(), results=5)
    web.routes.clear()
    failed = cited_web_search("scanner", set(), results=5)
    tools = InvestigationTools(source=tmp_path, sha="0" * 40, web=True)

    assert (
        [(result.text, result.answered) for result in (answered, empty, failed)],
        tools.search_web("scanner"),
    ) == (
        [
            (f"Result {SEARCH_URL}\n{SEARCH_URL}\nA scanner.", True),
            ("No result.", True),
            (FAILED_TEXT, False),
        ],
        FAILED_TEXT,
    )


def test_shared_text_a_refused_query_ran_no_search_and_is_not_an_answer(
    web: WebFake,
) -> None:
    result = cited_web_search("why does 192.168.49.2 refuse", set(), results=5)

    assert (result.text, result.answered, web.sent) == (
        "The search was refused: the query holds a private address.",
        False,
        [],
    )


def test_empty_answer_a_search_that_answered_with_no_result_counts_as_a_search(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    _serve(web)
    found: set[str] = set()
    tools = AlternativesTools(store=store)

    result = cited_web_search("scanner", found, results=5)
    text = tools.search_web("scanner")

    assert (result.text, result.answered, found, text, tools.queries) == (
        "No result.",
        True,
        set(),
        "No result.",
        ["scanner"],
    )


def test_empty_answer_a_verdict_follows_an_empty_search_and_is_checked(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    _serve(web)

    plan = _plan(store, Script(SEARCH, NONE))

    (check,) = plan.checks
    assert (
        [(search.query, search.results) for search in check.searches],
        check.verdict,
        plan.failures,
    ) == ([("scanner", 0)], Verdict.NONE, [])


def test_all_searches_failed_the_check_fails_and_the_body_is_not_written(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    number = NUMBER
    script = Script(SEARCH, NONE, NONE)

    plan = _plan(store, script)
    written = apply_alternatives(store, plan)

    assert (
        len(web.sent),
        plan.checks,
        [(failure.item.number, failure.reason, failure.error_class) for failure in plan.failures],
        written,
        store.read_issue_body(number),
        store.comments_on(number),
        _record(store, number).get(AlternativesRecordKey.FAILED_ERROR),
        AlternativesRecordKey.VERDICT in _record(store, number),
    ) == (
        1,
        [],
        [(number, "the reply gives a verdict with no answered search", "RefusedReply")],
        0,
        BODY,
        [],
        "RefusedReply",
        False,
    )


def test_all_searches_failed_the_model_gets_one_more_turn_and_a_later_answer_counts(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    _serve(web, SEARCH_URL)
    _fail_first_search(web)

    plan = _plan(store, Script(SEARCH, SEARCH, NONE))

    (check,) = plan.checks
    assert (
        [(search.query, search.results) for search in check.searches],
        check.verdict,
        plan.failures,
    ) == ([("scanner", 1)], Verdict.NONE, [])


def test_all_searches_failed_each_attempt_counts_toward_the_search_limit(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    tools = AlternativesTools(store=store)

    answers = [
        tools.search_web(f"query {n}") for n in range(CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES + 1)
    ]

    assert (answers[0], answers[-1], tools.searches, tools.allowed_urls, len(web.sent)) == (
        FAILED_TEXT,
        "The search limit for this item is reached.",
        [],
        set(),
        CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES,
    )
