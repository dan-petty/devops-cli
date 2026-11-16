"""Tests for the decision point `alternatives.reply_fixable` (#4864, ADR 0020).

Verifies that fixable refused replies return once to the model in mode `on`, repeated reasons
do not return, shadow mode records the decision band without retrying, and non-fixable reasons
keep the 3-day wait.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic_ai.exceptions import UsageLimitExceeded

from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_URL
from devops_cli.roadmap.alternatives import (
    AlternativesReply,
    AlternativesWriter,
    Verdict,
    plan_alternatives,
)
from devops_cli.roadmap.alternatives_reply_fixable import (
    load_fixable_codes,
    reply_fixable_rule,
)
from devops_cli.roadmap.decision_step import Band
from devops_cli.roadmap.stores.store import (
    AlternativesRecordKey,
    ItemField,
    RepositoryFacts,
)
from tests.support.fakes.http import WebFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_job_result import result_fields
from tests.support.scripted_model import Script, call

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
TOOL_URL = "https://github.com/example/scanner"
SEARCH_URL = "https://example.com/scanner"
REASON = "The tool scans files."


def _days_ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    roadmap = InMemoryRoadmapStore(repo=REPO, is_private=False)
    roadmap.seed_repository(
        RepositoryFacts(
            full_name="example/scanner",
            url=TOOL_URL,
            license="MIT",
            pushed_at=_days_ago(5),
            stars=120,
            latest_release="v1.2.0",
            released_at=_days_ago(9),
        )
    )
    return roadmap


@pytest.fixture
def web_key(config: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, web: WebFake) -> None:
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config(search={"providers": ["firecrawl"]}, firecrawl={"api_key": "fc-test"})
    _firecrawl(web, SEARCH_URL)


def _firecrawl(web: WebFake, *urls: str) -> None:
    results = [{"title": f"Result {url}", "url": url, "description": "A scanner."} for url in urls]
    body = json.dumps({"success": True, "data": {"web": results}}).encode()
    web.content(DEFAULT_FIRECRAWL_SEARCH_URL, body)


def _item(store: InMemoryRoadmapStore, title: str = "Scan a directory") -> int:
    return store.seed_issue(
        title,
        body="The job needs to read every file of a directory.",
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"},
        author_association="COLLABORATOR",
    )


# ── Rule tests ─────────────────────────────────────────────────────────────────


def test_fixable_codes_table_holds_expected_reason_codes() -> None:
    codes = load_fixable_codes()
    assert codes == frozenset(
        {
            "skip_only",
            "job_verdict",
            "no_search",
            "no_tool",
            "no_facts",
            "url",
            "schema_broken",
        }
    )


def test_rule_returns_review_for_fixable_code_with_no_earlier_refusal() -> None:
    assert reply_fixable_rule({"code": "no_tool", "earlier_code": None}) == Band.REVIEW
    assert reply_fixable_rule({"code": "no_search", "earlier_code": None}) == Band.REVIEW
    assert reply_fixable_rule({"code": "schema_broken", "earlier_code": None}) == Band.REVIEW


def test_rule_returns_review_when_reason_differs_from_earlier_code() -> None:
    assert reply_fixable_rule({"code": "no_tool", "earlier_code": "no_search"}) == Band.REVIEW


def test_rule_returns_continue_when_reason_repeats_earlier_code() -> None:
    assert reply_fixable_rule({"code": "no_tool", "earlier_code": "no_tool"}) == Band.CONTINUE
    assert reply_fixable_rule({"code": "skip_only", "earlier_code": "skip_only"}) == Band.CONTINUE


def test_rule_returns_continue_for_non_fixable_or_missing_code() -> None:
    assert reply_fixable_rule({"code": "timeout", "earlier_code": None}) == Band.CONTINUE
    assert reply_fixable_rule({"code": "output_limit", "earlier_code": None}) == Band.CONTINUE
    assert reply_fixable_rule({"code": "marker", "earlier_code": None}) == Band.CONTINUE
    assert reply_fixable_rule({"code": "", "earlier_code": None}) == Band.CONTINUE
    assert reply_fixable_rule({}) == Band.CONTINUE


# ── Integration tests with plan_alternatives ───────────────────────────────────


def test_mode_on_returns_fixable_refusal_once_and_writes_valid_reply(
    store: InMemoryRoadmapStore,
    web_key: None,
    config: Callable[..., Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    config(roadmap={"decisions": {"alternatives.reply_fixable": "on"}})
    number = _item(store)
    # Seed earlier failed reason that differs from no_tool
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {AlternativesRecordKey.FAILED_REASON: "no_search"})

    # 1. Search tool call
    # 2. Refused reply: covers with no tool_url -> code="no_tool"
    # 3. Retry turn: valid reply none
    refused_reply = AlternativesReply(reason=REASON, verdict=Verdict.COVERS, tool_url=None)
    valid_reply = AlternativesReply(reason=REASON, verdict=Verdict.NONE)
    script = Script(
        call("search_web", query="scanner"),
        refused_reply,
        valid_reply,
    )

    writer = AlternativesWriter(store, REPO)
    with caplog.at_level(logging.INFO):
        plan = plan_alternatives(
            store,
            repo=REPO,
            investigator=script.model(),
            writer=writer,
            now=NOW,
        )

    assert len(plan.checks) == 1
    assert len(plan.failures) == 0
    (check,) = plan.checks
    assert check.verdict == Verdict.NONE
    assert check.returns == 1

    # Check cleared failed_reason in job record
    updated_item = store.item(number)
    assert updated_item is not None
    assert updated_item.job_record.get(AlternativesRecordKey.FAILED_REASON) is None

    # Check result line
    lines = result_fields(caplog)
    alts_lines = [entry for entry in lines if entry.get("job") == "alternatives"]
    assert len(alts_lines) == 1
    assert (alts_lines[0]["result"], alts_lines[0]["returns"], alts_lines[0]["reason"]) == (
        "none",
        "1",
        "none",
    )


def test_mode_on_does_not_return_when_refusal_reason_repeats(
    store: InMemoryRoadmapStore,
    web_key: None,
    config: Callable[..., Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    config(roadmap={"decisions": {"alternatives.reply_fixable": "on"}})
    number = _item(store)
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {AlternativesRecordKey.FAILED_REASON: "no_tool"})

    # 1. Search tool call
    # 2. Refused reply with no_tool again
    # 3. Third step would only be called if retry occurred
    refused_reply = AlternativesReply(reason=REASON, verdict=Verdict.COVERS, tool_url=None)
    script = Script(
        call("search_web", query="scanner"),
        refused_reply,
        AlternativesReply(reason=REASON, verdict=Verdict.NONE),
    )

    writer = AlternativesWriter(store, REPO)
    with caplog.at_level(logging.INFO):
        plan = plan_alternatives(
            store,
            repo=REPO,
            investigator=script.model(),
            writer=writer,
            now=NOW,
        )

    assert len(plan.checks) == 0
    assert len(plan.failures) == 1
    (failure,) = plan.failures
    assert failure.reason_code == "no_tool"
    assert failure.band == Band.CONTINUE

    # Kept failed_reason in job record
    updated_item = store.item(number)
    assert updated_item is not None
    assert updated_item.job_record.get(AlternativesRecordKey.FAILED_REASON) == "no_tool"

    # Only 2 script calls made (no retry call made)
    assert len(script.seen) == 2

    # Check result line: band=continue
    lines = result_fields(caplog)
    alts_lines = [entry for entry in lines if entry.get("job") == "alternatives"]
    assert len(alts_lines) == 1
    assert (
        alts_lines[0]["result"],
        alts_lines[0]["reason"],
        alts_lines[0]["band"],
        alts_lines[0]["returns"],
    ) == ("refused", "no_tool", "continue", "0")


def test_mode_shadow_records_band_without_retry(
    store: InMemoryRoadmapStore,
    web_key: None,
    config: Callable[..., Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    config(roadmap={"decisions": {"alternatives.reply_fixable": "shadow"}})
    number = _item(store)

    refused_reply = AlternativesReply(reason=REASON, verdict=Verdict.COVERS, tool_url=None)
    script = Script(
        call("search_web", query="scanner"),
        refused_reply,
        AlternativesReply(reason=REASON, verdict=Verdict.NONE),
    )

    writer = AlternativesWriter(store, REPO)
    with caplog.at_level(logging.INFO):
        plan = plan_alternatives(
            store,
            repo=REPO,
            investigator=script.model(),
            writer=writer,
            now=NOW,
        )

    assert len(plan.checks) == 0
    assert len(plan.failures) == 1
    (failure,) = plan.failures
    assert failure.reason_code == "no_tool"
    assert failure.band == Band.REVIEW

    # In shadow mode, failed_reason is recorded
    updated_item = store.item(number)
    assert updated_item is not None
    assert updated_item.job_record.get(AlternativesRecordKey.FAILED_REASON) == "no_tool"

    # No retry turn executed
    assert len(script.seen) == 2

    # Result line holds reason and band=review
    lines = result_fields(caplog)
    alts_lines = [entry for entry in lines if entry.get("job") == "alternatives"]
    assert len(alts_lines) == 1
    assert (
        alts_lines[0]["result"],
        alts_lines[0]["reason"],
        alts_lines[0]["band"],
        alts_lines[0]["returns"],
    ) == ("refused", "no_tool", "review", "0")


def test_stopped_investigation_timeout_gives_band_continue(
    store: InMemoryRoadmapStore,
    web_key: None,
    config: Callable[..., Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    config(roadmap={"decisions": {"alternatives.reply_fixable": "on"}})
    number = _item(store)

    # Model stops with UsageLimitExceeded
    script = Script(UsageLimitExceeded("Too many tool calls"))

    writer = AlternativesWriter(store, REPO)
    with caplog.at_level(logging.INFO):
        plan = plan_alternatives(
            store,
            repo=REPO,
            investigator=script.model(),
            writer=writer,
            now=NOW,
        )

    assert len(plan.checks) == 0
    assert len(plan.failures) == 1
    (failure,) = plan.failures
    assert failure.reason_code == "timeout"
    assert failure.band == Band.CONTINUE

    # Recorded in job record
    updated_item = store.item(number)
    assert updated_item is not None
    assert updated_item.job_record.get(AlternativesRecordKey.FAILED_REASON) == "timeout"

    # Result line holds reason=timeout and band=continue
    lines = result_fields(caplog)
    alts_lines = [entry for entry in lines if entry.get("job") == "alternatives"]
    assert len(alts_lines) == 1
    assert (
        alts_lines[0]["result"],
        alts_lines[0]["reason"],
        alts_lines[0]["band"],
        alts_lines[0]["returns"],
    ) == ("refused", "timeout", "continue", "0")
