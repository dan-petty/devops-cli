"""The alternatives check logs one result line for each item that its writer settles (#4845).

The roadmap is the in-memory store. A check and a refusal come from `validate_reply`, and a stopped
run from a scripted model, so no test reaches a model. Firecrawl answers a search at the HTTP edge.
A refused check logs the searches that a provider answered, and each URL that no tool returned
(#6346).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest
from pydantic_ai.exceptions import UsageLimitExceeded

from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_URL
from devops_cli.roadmap import alternatives
from devops_cli.roadmap.alternatives import (
    AlternativesReply,
    AlternativesTools,
    AlternativesWriter,
    CheckFailure,
    Verdict,
    plan_alternatives,
)
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.stores.store import Item, ItemField
from tests.support.fakes.http import WebFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_job_result import result_fields
from tests.support.scripted_model import Script, call

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
SEARCH_URL = "https://example.com/scanner"
MADE_UP_URL = "https://example.com/tool"
OTHER_MADE_UP_URL = "https://example.com/other"


def _item(store: InMemoryRoadmapStore) -> Item:
    number = store.seed_issue(
        "Scan a directory",
        body="The job needs to read every file of a directory.",
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"},
        author_association="COLLABORATOR",
    )
    item = store.item(number)
    assert item is not None
    return item


def _settled(
    store: InMemoryRoadmapStore,
    reply: AlternativesReply,
    caplog: pytest.LogCaptureFixture,
    searches: int = 1,
) -> list[dict[str, str]]:
    """The result lines of the item whose model made `searches` answered searches and gave
    `reply`."""
    item = _item(store)
    tools = AlternativesTools(store=store)
    tools.searches.extend(alternatives.Search(f"scanner {n}", 1) for n in range(searches))
    outcome = alternatives.validate_reply(item, reply, tools, NOW, ())
    with caplog.at_level(logging.INFO):
        AlternativesWriter(store, REPO).settle(outcome)
    return result_fields(caplog)


@pytest.fixture
def firecrawl(config: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, web: WebFake) -> None:
    """A chain of Firecrawl alone, with a key, that answers each search with `SEARCH_URL`."""
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config(search={"providers": ["firecrawl"]}, firecrawl={"api_key": "fc-test"})
    results = [{"title": "Scanner", "url": SEARCH_URL, "description": "A scanner."}]
    body = json.dumps({"success": True, "data": {"web": results}}).encode()
    web.content(DEFAULT_FIRECRAWL_SEARCH_URL, body)


def _url_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The text of each WARNING record that names the reason code `url`."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING and "(url)" in record.getMessage()
    ]


def test_a_written_check_logs_its_verdict_and_its_searches(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryRoadmapStore(repo=REPO)

    lines = _settled(store, AlternativesReply(reason="Nothing fits.", verdict=Verdict.NONE), caplog)

    assert lines == [
        {
            "job": "alternatives",
            "repo": REPO,
            "item": "#1",
            "result": "none",
            "success": "true",
            "class": "none",
            "infra": "false",
            "first_pass": "true",
            "searches": "1",
            "returns": "0",
            "reason": "none",
        }
    ]


def test_a_reply_that_the_job_refused_logs_a_refusal_with_its_code(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    reply = AlternativesReply(reason="Not a code item.", verdict=Verdict.NOT_APPLICABLE)

    lines = _settled(store, reply, caplog)

    assert [(line["result"], line["success"], line["reason"]) for line in lines] == [
        ("refused", "false", "skip_only")
    ]


def test_a_failed_model_call_logs_a_failure_with_its_class(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    failure = CheckFailure(
        _item(store), "the model call failed", "AIClientError", NOW, FailureClass.PROVIDER
    )

    with caplog.at_level(logging.INFO):
        AlternativesWriter(store, REPO).settle(failure)

    assert [
        (line["result"], line["class"], line["infra"], line["searches"], line["reason"])
        for line in result_fields(caplog)
    ] == [("failed", "provider", "true", "0", "AIClientError")]


def test_a_reply_refused_for_its_url_logs_the_searches_that_a_provider_answered(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    reply = AlternativesReply(reason="Nothing fits.", verdict=Verdict.NONE, sources=[MADE_UP_URL])

    lines = _settled(store, reply, caplog, searches=2)

    assert [(line["result"], line["reason"], line["searches"]) for line in lines] == [
        ("refused", "url", "2")
    ]


def test_the_failure_of_a_refused_reply_keeps_its_answered_searches() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    tools = AlternativesTools(store=store)
    tools.searches.extend([alternatives.Search("scanner", 1), alternatives.Search("walker", 0)])
    reply = AlternativesReply(reason="Nothing fits.", verdict=Verdict.NONE, sources=[MADE_UP_URL])

    outcome = alternatives.validate_reply(_item(store), reply, tools, NOW, ())

    assert isinstance(outcome, CheckFailure)
    assert (outcome.reason_code, outcome.searches) == ("url", 2)


def test_only_a_search_that_a_provider_answered_counts_on_the_line_of_a_refusal(
    firecrawl: None, web: WebFake, caplog: pytest.LogCaptureFixture
) -> None:
    sent: list[httpx2.Request] = []

    def fail_first(request: httpx2.Request) -> httpx2.Response | None:
        sent.append(request)
        return httpx2.Response(500) if len(sent) == 1 else None

    web.serve(fail_first)
    store = InMemoryRoadmapStore(repo=REPO)
    tools = AlternativesTools(store=store)
    tools.search_web("scanner")
    tools.search_web("directory walker")
    reply = AlternativesReply(reason="Nothing fits.", verdict=Verdict.NONE, sources=[MADE_UP_URL])

    outcome = alternatives.validate_reply(_item(store), reply, tools, NOW, ())
    with caplog.at_level(logging.INFO):
        AlternativesWriter(store, REPO).settle(outcome)

    assert (tools.search_calls, [line["searches"] for line in result_fields(caplog)]) == (2, ["1"])


def test_a_reply_refused_for_its_url_logs_each_url_that_no_tool_returned(
    firecrawl: None, caplog: pytest.LogCaptureFixture
) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    tools = AlternativesTools(store=store)
    tools.search_web("scanner")
    reply = AlternativesReply(
        reason="Nothing fits.",
        verdict=Verdict.NONE,
        sources=[SEARCH_URL, MADE_UP_URL, OTHER_MADE_UP_URL],
    )

    with caplog.at_level(logging.WARNING):
        alternatives.validate_reply(_item(store), reply, tools, NOW, ())

    warnings = _url_warnings(caplog)
    assert len(warnings) == 2
    assert all("#1" in text for text in warnings)
    assert [MADE_UP_URL in warnings[0], OTHER_MADE_UP_URL in warnings[1]] == [True, True]
    assert not any(SEARCH_URL in text for text in warnings)


def test_a_reply_refused_for_a_tool_with_no_facts_logs_no_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    tools = AlternativesTools(store=store)
    tools.searches.append(alternatives.Search("scanner", 1))
    reply = AlternativesReply(
        reason="It scans.", verdict=Verdict.COVERS, tool_url="https://github.com/example/scanner"
    )

    with caplog.at_level(logging.WARNING):
        outcome = alternatives.validate_reply(_item(store), reply, tools, NOW, ())

    assert isinstance(outcome, CheckFailure)
    assert (outcome.reason_code, _url_warnings(caplog)) == ("no_facts", [])


def test_a_run_that_stopped_after_a_search_logs_that_search(
    firecrawl: None, caplog: pytest.LogCaptureFixture
) -> None:
    store = InMemoryRoadmapStore(repo=REPO, is_private=False)
    _item(store)
    script = Script(call("search_web", query="scanner"), UsageLimitExceeded("Too many tool calls"))

    with caplog.at_level(logging.INFO):
        plan_alternatives(
            store,
            repo=REPO,
            investigator=script.model(),
            writer=AlternativesWriter(store, REPO),
            now=NOW,
        )

    assert [
        (line["result"], line["reason"], line["searches"]) for line in result_fields(caplog)
    ] == [("refused", "timeout", "1")]
