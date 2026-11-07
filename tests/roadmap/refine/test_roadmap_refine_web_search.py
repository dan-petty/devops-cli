"""Whether a refine round has web search, and what a round without it says (#1335)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.roadmap.refine.refine import (
    WebSearch,
    plan_refine,
    render_refine_plan,
    web_search_of,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import READY, REPO, seed_with_body

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_the_web_search_state_of_a_round_whose_visibility_read_fails(
    store: InMemoryRoadmapStore, caplog: pytest.LogCaptureFixture
) -> None:
    """A spent quota stops the round, and any other failed read of the repository's visibility
    turns web search off with its reason and a warning (#1365, #2398)."""
    store.fail_read("repository_is_private", GitHubRateLimitError("GraphQL budget exhausted"))
    with pytest.raises(GitHubRateLimitError) as raised:
        web_search_of(store)
    assert raised.value.error_code == "GITHUB_RATE_LIMIT_UNKNOWN"

    store.fail_read(
        "repository_is_private", GitHubOperationError("transient read failure", operation="read")
    )
    with caplog.at_level(logging.WARNING):
        web = web_search_of(store)

    assert (
        web,
        any("Could not read repository visibility" in r.getMessage() for r in caplog.records),
    ) == (WebSearch(off_reason="the repository's visibility could not be read"), True)


def test_page_fetch_needs_web_search_and_a_crawl4ai_url(
    store: InMemoryRoadmapStore, config: Callable[..., Path]
) -> None:
    """The fetch of a page (#3890) is on for a public repository with a set `crawl4ai.url`. A
    private repository, or an empty setting, leaves it off."""
    url = "http://crawl4ai.devops.svc.cluster.local:11235"
    store.seed_visibility(is_private=False)
    config(crawl4ai={"url": None})
    unset = web_search_of(store)
    config(crawl4ai={"url": url})
    public = web_search_of(store)
    store.seed_visibility(is_private=True)
    private = web_search_of(store)

    assert (unset.fetch, public, private.fetch) == (
        False,
        WebSearch(on=True, fetch=True),
        False,
    )


def test_a_public_repository_has_web_search_with_the_keyless_provider(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Path]
) -> None:
    """DuckDuckGo needs no key, so the default providers turn web search on (#3925). A chain of
    Firecrawl alone with no key leaves it off."""
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    store.seed_visibility(is_private=False)
    config(firecrawl={"api_key": None})
    with_defaults = web_search_of(store)
    config(search={"providers": ["firecrawl"]})
    firecrawl_only = web_search_of(store)

    assert (with_defaults, firecrawl_only) == (
        WebSearch(on=True),
        WebSearch(off_reason="no search provider is configured"),
    )


@pytest.mark.parametrize(
    ("is_private", "reason"),
    [(False, "no search provider is configured"), (True, "the repository is private")],
    ids=["no-provider", "private"],
)
def test_a_round_with_no_web_search_says_why(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    is_private: bool,
    reason: str,
    monkeypatch: pytest.MonkeyPatch,
    config: Callable[..., Path],
) -> None:
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config(search={"providers": ["firecrawl"]}, firecrawl={"api_key": None})
    seed_with_body(store, "Body")
    store.seed_visibility(is_private=is_private)
    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo)

    assert (plan.web_search_off, render_refine_plan(plan).splitlines()[1]) == (
        reason,
        f"Web search is off: {reason}.",
    )
