"""A link in the text of a fetched page is not a source of an alternatives reply (#6394).

The Service log of 2026-11-21 holds 14 WARNING lines of `url` refusals (#6346). In 10 of them the
reply cites a link from the text of the page that `fetch_page` read, such as the link of a README
to the documentation of its tool. In 3 the reply cites a URL that the item body names and that no
tool read. These tests replay such a run offline: Firecrawl and the Crawl4AI service answer at the
HTTP edge by `web`, and a scripted model answers each request. The fetch answer tells the model
that a link in the text is not a source, and the check still refuses a reply that cites one.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_URL
from devops_cli.roadmap.alternatives import (
    AlternativesPlan,
    AlternativesReply,
    Verdict,
    plan_alternatives,
)
from devops_cli.roadmap.stores.store import ItemField
from tests.support.fakes.http import WebFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.scripted_model import Script, call

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
CRAWL4AI_SERVICE = "http://crawl4ai.devops.svc.cluster.local:11235"
REPOSITORY_PAGE = "https://github.com/example/scanner"
NOTES_PAGE = "https://scanner.example.com/notes"
DOCS_LINK = "https://scanner.example.com/docs/setup/"
BODY = f"The job needs to read every file of a directory.\n\nSource: {NOTES_PAGE}"
PAGE_TEXT = f"# scanner\n\nScans a directory. Read the [setup guide]({DOCS_LINK})."
SEARCH = call("search_web", query="scanner for a directory")


@pytest.fixture
def services(
    config: Callable[..., Any],
    keyring_store: Any,
    monkeypatch: pytest.MonkeyPatch,
    web: WebFake,
) -> WebFake:
    """Firecrawl, which answers each search with the repository page, and the Crawl4AI service,
    which gives the text of each page it is asked for: a README with a link to its docs."""
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config(
        search={"providers": ["firecrawl"]},
        firecrawl={"api_key": "fc-test"},
        crawl4ai={"url": CRAWL4AI_SERVICE},
    )
    keyring_store.set_password("devops-cli", "crawl4ai_api_token", "c4a-token")
    results = [{"title": "scanner", "url": REPOSITORY_PAGE, "description": "A scanner."}]
    web.content(
        DEFAULT_FIRECRAWL_SEARCH_URL,
        json.dumps({"success": True, "data": {"web": results}}).encode(),
    )
    web.respond("POST", f"{CRAWL4AI_SERVICE}/md", 200, {"success": True, "markdown": PAGE_TEXT})
    return web


def _round(*steps: Any) -> tuple[AlternativesPlan, Script]:
    """The plan of one item whose scripted model takes `steps`, and the script."""
    store = InMemoryRoadmapStore(repo=REPO, is_private=False)
    store.seed_issue(
        "Scan a directory",
        body=BODY,
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"},
        author_association="COLLABORATOR",
    )
    script = Script(*steps)
    plan = plan_alternatives(store, repo=REPO, investigator=script.model(), now=NOW)
    return plan, script


def _citing(*sources: str) -> AlternativesReply:
    return AlternativesReply(
        reason="No tool reads every file.", verdict=Verdict.NONE, sources=list(sources)
    )


def _url_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING and "(url)" in record.getMessage()
    ]


def test_a_reply_that_cites_a_link_in_the_text_of_a_fetched_page_is_refused_for_url(
    services: WebFake, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        plan, script = _round(
            SEARCH,
            call("fetch_page", url=REPOSITORY_PAGE),
            _citing(REPOSITORY_PAGE, DOCS_LINK),
        )

    fetched = script.tool_returns()[1]
    assert (
        DOCS_LINK in fetched,
        "A link in the text is not a source." in fetched,
        plan.checks,
        [failure.reason_code for failure in plan.failures],
        _url_warnings(caplog),
    ) == (
        True,
        True,
        [],
        ["url"],
        [
            f"The alternatives check of #1 refused its reply (url): the reply cites {DOCS_LINK}, "
            "and no tool of the run returned it."
        ],
    )


def test_a_reply_that_cites_the_page_that_fetch_page_read_is_written(
    services: WebFake, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        plan, _ = _round(
            SEARCH,
            call("fetch_page", url=NOTES_PAGE),
            _citing(REPOSITORY_PAGE, f"{NOTES_PAGE}/"),
        )

    assert (len(plan.checks), plan.failures, _url_warnings(caplog)) == (1, [], [])


def test_a_url_that_the_item_names_is_not_a_source_until_fetch_page_reads_it(
    services: WebFake,
) -> None:
    plan, _ = _round(SEARCH, _citing(REPOSITORY_PAGE, NOTES_PAGE))

    assert (plan.checks, [failure.reason_code for failure in plan.failures]) == ([], ["url"])
