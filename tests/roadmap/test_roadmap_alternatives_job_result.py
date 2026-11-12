"""The alternatives check logs one result line for each item that its writer settles (#4845).

The roadmap is the in-memory store. A check and a refusal come from `validate_reply`, so no test
reaches a model, a search or the web.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from devops_cli.roadmap import alternatives
from devops_cli.roadmap.alternatives import (
    AlternativesReply,
    AlternativesTools,
    AlternativesWriter,
    CheckFailure,
    Verdict,
)
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.stores.store import Item, ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_job_result import result_fields

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


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
    store: InMemoryRoadmapStore, reply: AlternativesReply, caplog: pytest.LogCaptureFixture
) -> list[dict[str, str]]:
    """The result lines of the item whose model searched once and gave `reply`."""
    item = _item(store)
    tools = AlternativesTools(store=store)
    tools.searches.append(alternatives.Search("scanner", 1))
    outcome = alternatives.validate_reply(item, reply, tools, NOW, ())
    with caplog.at_level(logging.INFO):
        AlternativesWriter(store, REPO).settle(outcome)
    return result_fields(caplog)


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
            "searches": "1",
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
        ("refused", "false", "RefusedReply")
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
