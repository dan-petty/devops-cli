"""Tests for `devops roadmap alternatives` (#2650): which items the check takes, the tools of its
agent run, what the job validates in the reply, and what a run writes to the issue.

The roadmap is the in-memory store. pydantic-ai's `FunctionModel` answers each model request from a
script, so no test reaches a model. Firecrawl and PyPI are answered at the HTTP edge by `stub_web`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, RetryPromptPart, ToolReturnPart, UserPromptPart
from typer.testing import CliRunner

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.commands.roadmap import app as roadmap_app
from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS,
    CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
)
from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_URL, DEFAULT_PYPI_PACKAGE_URL
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.exceptions.roadmap import RoadmapAlternativesError
from devops_cli.roadmap.alternatives import (
    AlternativesReply,
    AlternativesTools,
    Verdict,
    apply_alternatives,
    body_hash_of,
    plan_alternatives,
    raise_for_failed_checks,
    render_alternatives_plan,
    select_items,
)
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import MODEL_LANE_ROWS, run_due_jobs
from devops_cli.roadmap.store import (
    AlternativesRecordKey,
    CloseReason,
    ItemField,
    RepositoryFacts,
    RoadmapStore,
)
from devops_cli.telemetry.instruments import FIRECRAWL_SEARCHES_TOTAL, ROADMAP_ALTERNATIVES_TOTAL
from tests.roadmap_github_fake import GitHubFake
from tests.support.fakes.github import RunnerSession
from tests.support.fakes.otlp import FakeCollector
from tests.support.scripted_model import Script, call
from tests.web_fakes import StubWeb

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
TOOL_URL = "https://github.com/example/scanner"
SEARCH_URL = "https://example.com/scanner"
PLACED = {ItemField.PRIORITY: "P2-Medium"}


def _days_ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    """A public roadmap, and the repository `example/scanner`, which GitHub knows."""
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
def web_key(config: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, stub_web: StubWeb) -> None:
    """A Firecrawl key in the settings, and a Firecrawl that answers each search with one result."""
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config(firecrawl={"api_key": "fc-test"})
    _firecrawl(stub_web, SEARCH_URL)


def _firecrawl(stub_web: StubWeb, *urls: str) -> None:
    """Make Firecrawl answer every search with one result for each URL."""
    results = [{"title": f"Result {url}", "url": url, "description": "A scanner."} for url in urls]
    body = json.dumps({"success": True, "data": {"web": results}}).encode()
    stub_web.content(DEFAULT_FIRECRAWL_SEARCH_URL, body)


def _item(
    store: InMemoryRoadmapStore,
    title: str = "Scan a directory",
    *,
    body: str = "The job needs a scanner for a directory.",
    status: str = "New",
    association: str = "COLLABORATOR",
) -> int:
    return store.seed_issue(
        title,
        body=body,
        fields={**PLACED, ItemField.STATUS: status},
        author_association=association,
    )


def _mark_checked(
    store: InMemoryRoadmapStore, number: int, *, days: int, body: str | None = None
) -> None:
    """Record a check of item `number` made `days` days before `NOW`, of `body` or its own."""
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            AlternativesRecordKey.CHECKED_AT: _days_ago(days).isoformat(),
            AlternativesRecordKey.BODY_HASH: body_hash_of(item.body if body is None else body),
            AlternativesRecordKey.VERDICT: "none",
        },
    )


def _mark_failed(
    store: InMemoryRoadmapStore, number: int, *, days: int, error: str = "AIClientError"
) -> None:
    """Record a failed check of item `number` made `days` days before `NOW`."""
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            AlternativesRecordKey.FAILED_AT: _days_ago(days).isoformat(),
            AlternativesRecordKey.FAILED_ERROR: error,
        },
    )


def _recorded(store: RoadmapStore, number: int, key: AlternativesRecordKey) -> str | None:
    item = store.item(number)
    assert item is not None
    return item.job_record.get(key)


def _failure_record(store: RoadmapStore, number: int) -> tuple[str | None, str | None]:
    """The time and the class of the error of the last failed check of item `number`."""
    return (
        _recorded(store, number, AlternativesRecordKey.FAILED_AT),
        _recorded(store, number, AlternativesRecordKey.FAILED_ERROR),
    )


def _covers(**changes: Any) -> AlternativesReply:
    reply = AlternativesReply(
        verdict=Verdict.COVERS,
        tool_url=TOOL_URL,
        covers=["Scans a directory."],
        lacks=["No SARIF output."],
        sources=[TOOL_URL, SEARCH_URL],
    )
    return reply.model_copy(update=changes)


_SEARCH = call("search_web", query="scanner")


def _after_search(reply: AlternativesReply) -> list[Any]:
    """The steps of an item whose model searches once and answers with `reply`."""
    return [_SEARCH, reply]


def _searched(messages: list[ModelMessage]) -> bool:
    return any(
        isinstance(part, ToolReturnPart) and part.tool_name == "search_web"
        for message in messages
        for part in getattr(message, "parts", ())
    )


def _searching(reply: AlternativesReply) -> Script:
    """A model that, for each item, searches once and then answers with `reply`."""
    return Script(lambda messages: reply if _searched(messages) else _SEARCH)


def _search_then_read_then(reply: AlternativesReply) -> Script:
    """A model that searches, reads the repository, and answers with `reply`."""
    return Script(
        call("search_web", query="scanner for a directory"),
        call("github_repository", name="example/scanner"),
        reply,
    )


def _plan(store: RoadmapStore, script: Script | None, **options: Any) -> Any:
    options.setdefault("now", NOW)
    return plan_alternatives(
        store, repo=REPO, investigator=script.model() if script else None, **options
    )


def _prompt_of(messages: list[ModelMessage]) -> dict[str, Any]:
    """The request document of a model request."""
    text = next(
        part.content
        for message in messages
        for part in getattr(message, "parts", ())
        if isinstance(part, UserPromptPart)
    )
    document: dict[str, Any] = json.loads(str(text))
    return document


def _by_item(replies: dict[int, Any]) -> Script:
    """A model that answers each request of an item from that item's steps, in order, and the
    last step after that. A step is a model response, a reply or an error."""
    used: dict[int, int] = {}

    def answer(messages: list[ModelMessage]) -> Any:
        number = _prompt_of(messages)["number"]
        steps = replies[number] if isinstance(replies[number], list) else [replies[number]]
        index = used.get(number, 0)
        used[number] = index + 1
        return steps[min(index, len(steps) - 1)]

    return Script(answer)


# ── Selection ─────────────────────────────────────────────────────────────────


def test_unchecked_items_come_before_stale_items_and_the_limit_caps_the_run(
    store: InMemoryRoadmapStore,
) -> None:
    stale = _item(store, "Stale")
    fresh = _item(store, "Fresh")
    first = _item(store, "First unchecked")
    second = _item(store, "Second unchecked")
    _mark_checked(store, stale, days=40)
    _mark_checked(store, fresh, days=2)

    selection = select_items(
        store, item_number=None, limit=3, recheck_days=30, retry_days=3, now=NOW
    )

    assert (
        [item.number for item in selection.selected],
        [item.number for item in selection.current],
    ) == ([first, second, stale], [fresh])


def test_stale_items_are_taken_oldest_check_first(store: InMemoryRoadmapStore) -> None:
    newer = _item(store, "Newer check")
    older = _item(store, "Older check")
    _mark_checked(store, newer, days=35)
    _mark_checked(store, older, days=90)

    selection = select_items(
        store, item_number=None, limit=5, recheck_days=30, retry_days=3, now=NOW
    )

    assert [item.number for item in selection.selected] == [older, newer]


def test_an_item_whose_text_changed_is_checked_again_and_the_jobs_own_text_changes_nothing(
    store: InMemoryRoadmapStore,
) -> None:
    edited = _item(store, "Edited", body="The new text.")
    own = _item(store, "Own block", body="The same text.")
    _mark_checked(store, edited, days=2, body="The old text.")
    _mark_checked(store, own, days=2, body="The same text.")
    marked = f"{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\nVerdict: none.\n{CONST_ROADMAP_ALTERNATIVES_END_MARKER}"
    store.write_issue_body(own, f"The same text.\n\n{marked}")

    selection = select_items(
        store, item_number=None, limit=5, recheck_days=30, retry_days=3, now=NOW
    )

    assert (
        [item.number for item in selection.selected],
        [item.number for item in selection.current],
    ) == ([edited], [own])


def test_started_blocked_closed_and_untrusted_items_are_left_out(
    store: InMemoryRoadmapStore,
) -> None:
    for status in ("In Progress", "Blocked", "Done"):
        _item(store, status, status=status)
    _item(store, "Outside author", association="NONE")
    store.close(_item(store, "Closed"), CloseReason.COMPLETED)
    ready = _item(store, "Ready", status="Ready")

    selection = select_items(
        store, item_number=None, limit=9, recheck_days=30, retry_days=3, now=NOW
    )

    assert [item.number for item in selection.selected] == [ready]


def test_an_item_that_is_named_is_checked_whoever_opened_it(store: InMemoryRoadmapStore) -> None:
    untrusted = _item(store, "Outside author", association="NONE", status="Blocked")
    other = _item(store, "Other")
    _mark_checked(store, untrusted, days=2)

    selection = select_items(
        store, item_number=untrusted, limit=1, recheck_days=30, retry_days=3, now=NOW
    )
    missing = select_items(store, item_number=99, limit=1, recheck_days=30, retry_days=3, now=NOW)

    assert (
        [item.number for item in selection.selected],
        other in [item.number for item in selection.selected],
        missing.selected,
    ) == ([untrusted], False, [])


def test_a_closed_item_that_is_named_is_not_checked(store: InMemoryRoadmapStore) -> None:
    number = _item(store)
    store.close(number, CloseReason.NOT_PLANNED)

    assert (
        select_items(
            store, item_number=number, limit=1, recheck_days=30, retry_days=3, now=NOW
        ).selected
        == []
    )


def test_the_recheck_window_is_a_setting(
    store: InMemoryRoadmapStore, web_key: None, config: Callable[..., Any], stub_web: StubWeb
) -> None:
    number = _item(store)
    _mark_checked(store, number, days=10)
    script = _searching(AlternativesReply(verdict=Verdict.NONE))

    default_window = _plan(store, script)
    config(roadmap={"alternatives": {"recheck_days": 7}})
    short_window = _plan(store, script)

    assert (
        [c.item.number for c in default_window.checks],
        [c.item.number for c in short_window.checks],
    ) == ([], [number])


def test_retry_delay_an_item_whose_check_failed_lately_is_left_out_until_the_delay_ends(
    store: InMemoryRoadmapStore, caplog: pytest.LogCaptureFixture
) -> None:
    first = _item(store, "First unchecked")
    lately = _item(store, "Failed lately")
    long_ago = _item(store, "Failed long ago")
    garbled = _item(store, "Garbled failure time")
    _mark_failed(store, lately, days=1)
    _mark_failed(store, long_ago, days=4)
    item = store.item(garbled)
    assert item is not None
    store.set_marks(item, {AlternativesRecordKey.FAILED_AT: "yesterday"})

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.alternatives"):
        selection = select_items(
            store, item_number=None, limit=9, recheck_days=30, retry_days=3, now=NOW
        )
    named = select_items(store, item_number=lately, limit=1, recheck_days=30, retry_days=3, now=NOW)
    longer = select_items(store, item_number=None, limit=9, recheck_days=30, retry_days=7, now=NOW)

    assert (
        [i.number for i in selection.selected],
        [i.number for i in selection.current],
        [i.number for i in named.selected],
        [i.number for i in longer.selected],
        any(f"#{garbled} is not a time" in r.getMessage() for r in caplog.records),
    ) == ([first, long_ago, garbled], [], [lately], [first, garbled], True)


def test_retry_delay_the_setting_defaults_to_three_and_is_at_least_one(
    config: Callable[..., Any],
) -> None:
    from pydantic import ValidationError

    from devops_cli.config.settings import AlternativesConfig, load_settings

    config()
    with pytest.raises(ValidationError) as raised:
        AlternativesConfig(retry_days=0)
    assert [error["loc"] for error in raised.value.errors()] == [("retry_days",)]
    assert (AlternativesConfig().retry_days, load_settings().roadmap.alternatives.retry_days) == (
        3,
        3,
    )


# ── The tools of the run ──────────────────────────────────────────────────────


def test_the_search_stops_at_its_limit_and_remembers_what_it_ran(
    store: InMemoryRoadmapStore, stub_web: StubWeb
) -> None:
    _firecrawl(stub_web, SEARCH_URL)
    tools = AlternativesTools(store=store, firecrawl_key="fc-test")

    answers = [
        tools.search_web(f"query {n}") for n in range(CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES + 1)
    ]

    assert (
        answers[0],
        answers[-1],
        tools.queries,
        tools.allowed_urls,
        len(stub_web.sent),
        [tool.name for tool in tools.tools()],
    ) == (
        f"Result {SEARCH_URL}\n{SEARCH_URL}\nA scanner.",
        "The search limit for this item is reached.",
        ["query 0", "query 1", "query 2"],
        {SEARCH_URL},
        CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES,
        ["search_web", "github_repository", "pypi_package"],
    )


def test_a_repository_read_answers_with_its_facts_and_remembers_them(
    store: InMemoryRoadmapStore,
) -> None:
    tools = AlternativesTools(store=store, firecrawl_key="fc-test")

    answer = tools.github_repository("example/scanner")

    facts = tools.facts[TOOL_URL]
    assert (answer, (facts.license, facts.last_activity, facts.archived), tools.allowed_urls) == (
        "\n".join(
            [
                TOOL_URL,
                "License: MIT",
                f"Last push: {_days_ago(5).date()}",
                "Archived: no",
                "Stars: 120",
                f"Latest release: v1.2.0 ({_days_ago(9).date()})",
            ]
        ),
        ("MIT", _days_ago(5), False),
        {TOOL_URL},
    )


def test_a_repository_with_no_release_or_license_says_so(store: InMemoryRoadmapStore) -> None:
    store.seed_repository(
        RepositoryFacts(full_name="example/bare", url="https://github.com/example/bare")
    )
    tools = AlternativesTools(store=store, firecrawl_key="fc-test")

    answer = tools.github_repository("example/bare")

    assert answer.splitlines()[1:] == [
        "License: not stated",
        "Last push: never",
        "Archived: no",
        "Stars: 0",
        "Latest release: none",
    ]


@pytest.mark.parametrize(
    "name", ["scanner", "example/", "/scanner", "a/b/c", "../user", "a/..", "a b/c"]
)
def test_a_name_that_is_no_repository_name_is_answered_as_text_and_read_nowhere(
    store: InMemoryRoadmapStore, name: str
) -> None:
    tools = AlternativesTools(store=store, firecrawl_key="fc-test")

    answer = tools.github_repository(name)

    assert (answer, tools.fact_reads, tools.facts) == ("Give the repository as owner/name.", 0, {})


def test_a_repository_that_does_not_exist_is_answered_as_text(store: InMemoryRoadmapStore) -> None:
    tools = AlternativesTools(store=store, firecrawl_key="fc-test")

    assert tools.github_repository("example/none") == "GitHub has no repository example/none."


def test_a_failed_repository_read_is_answered_as_text_and_logged(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(full_name: str) -> RepositoryFacts:
        raise GitHubOperationError("GitHub answered 502.", operation="roadmap.read")

    monkeypatch.setattr(store, "repository_facts", broken)
    tools = AlternativesTools(store=store, firecrawl_key="fc-test")

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.alternatives"):
        answer = tools.github_repository("example/scanner")

    assert (answer, [r.getMessage() for r in caplog.records]) == (
        "The read failed: GitHubOperationError.",
        ["A repository read of the alternatives check failed: GitHubOperationError."],
    )


def test_a_spent_github_quota_stops_the_run(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def spent(full_name: str) -> RepositoryFacts:
        raise GitHubRateLimitError("No requests are left.", operation="roadmap.read")

    monkeypatch.setattr(store, "repository_facts", spent)
    tools = AlternativesTools(store=store, firecrawl_key="fc-test")

    with pytest.raises(GitHubRateLimitError) as raised:
        tools.github_repository("example/scanner")
    assert raised.value.error_code == "GITHUB_RATE_LIMIT_UNKNOWN"


def test_the_two_fact_tools_share_one_read_limit(
    store: InMemoryRoadmapStore, stub_web: StubWeb
) -> None:
    tools = AlternativesTools(store=store, firecrawl_key="fc-test")

    answers = [tools.github_repository("example/scanner") for _ in range(7)]
    after = tools.pypi_package("scanner")

    assert (
        answers[0] == answers[5],
        answers[6],
        after,
        tools.fact_reads,
        stub_web.sent,
    ) == (
        True,
        "The fact read limit for this item is reached.",
        "The fact read limit for this item is reached.",
        CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS,
        [],
    )


def _pypi(
    stub_web: StubWeb,
    name: str,
    *,
    uploads: list[str],
    license_expression: str | None,
    license_text: str | None = None,
    classifiers: list[str] | None = None,
) -> None:
    payload = {
        "info": {
            "name": name,
            "version": "2.0.0",
            "license": license_text,
            "license_expression": license_expression,
            "classifiers": classifiers or [],
            "package_url": f"https://pypi.org/project/{name}/",
        },
        "urls": [{"upload_time_iso_8601": stamp} for stamp in uploads],
    }
    stub_web.content(DEFAULT_PYPI_PACKAGE_URL.format(name=name), json.dumps(payload).encode())


def test_a_pypi_read_answers_with_the_latest_upload_and_remembers_it(
    store: InMemoryRoadmapStore, stub_web: StubWeb
) -> None:
    _pypi(
        stub_web,
        "scanner",
        uploads=["2026-10-20T01:00:00.123456Z", "2026-10-20T01:00:30.000000Z"],
        license_expression="Apache-2.0",
    )
    tools = AlternativesTools(store=store, firecrawl_key="fc-test")

    answer = tools.pypi_package("scanner")

    facts = tools.facts["https://pypi.org/project/scanner"]
    assert (answer, facts.license, facts.last_activity, facts.archived) == (
        "\n".join(
            [
                "https://pypi.org/project/scanner/",
                "License: Apache-2.0",
                "Latest version: 2.0.0",
                "Latest upload: 2026-10-20",
            ]
        ),
        "Apache-2.0",
        datetime(2026, 10, 20, 1, 0, 30, tzinfo=UTC),
        False,
    )


@pytest.mark.parametrize(
    ("fields", "license_name"),
    [
        pytest.param(
            {"license_expression": "MIT", "license_text": "Apache-2.0"}, "MIT", id="expression"
        ),
        pytest.param(
            {"license_expression": None, "license_text": "Apache-2.0"}, "Apache-2.0", id="text"
        ),
        pytest.param(
            {
                "license_expression": None,
                "license_text": "A long licence text.\n" * 20,
                "classifiers": ["Topic :: Utilities", "License :: OSI Approved :: MIT License"],
            },
            "MIT License",
            id="classifier-when-the-text-is-a-whole-licence",
        ),
        pytest.param(
            {"license_expression": None, "license_text": "", "classifiers": []},
            "not stated",
            id="not-stated",
        ),
    ],
)
def test_a_pypi_read_gives_the_license_a_package_states_in_any_of_its_fields(
    store: InMemoryRoadmapStore, stub_web: StubWeb, fields: dict[str, Any], license_name: str
) -> None:
    _pypi(stub_web, "scanner", uploads=[NOW.isoformat()], **fields)
    tools = AlternativesTools(store=store, firecrawl_key="fc-test")

    answer = tools.pypi_package("scanner")

    assert f"License: {license_name}" in answer.splitlines()
    assert tools.facts["https://pypi.org/project/scanner"].license == (
        None if license_name == "not stated" else license_name
    )


def test_a_pypi_package_that_does_not_exist_or_fails_to_read_is_answered_as_text(
    store: InMemoryRoadmapStore, stub_web: StubWeb, caplog: pytest.LogCaptureFixture
) -> None:
    stub_web.respond("GET", DEFAULT_PYPI_PACKAGE_URL.format(name="broken"), 503)
    tools = AlternativesTools(store=store, firecrawl_key="fc-test")

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.alternatives"):
        answers = [tools.pypi_package(name) for name in ("none-such", "broken", "../x", "a b")]

    assert (answers, [r.getMessage() for r in caplog.records]) == (
        [
            "PyPI has no package none-such.",
            "The read failed: HTTPStatusError.",
            "Give the package name as PyPI spells it.",
            "Give the package name as PyPI spells it.",
        ],
        ["A PyPI read of the alternatives check failed: HTTPStatusError."],
    )


# ── The request and the reply ─────────────────────────────────────────────────


def test_the_request_holds_the_item_the_replies_and_the_budget(
    store: InMemoryRoadmapStore, web_key: None
) -> None:
    body = "The job needs a scanner."
    block = (
        f"{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\nOld verdict.\n"
        f"{CONST_ROADMAP_ALTERNATIVES_END_MARKER}"
    )
    number = _item(store, body=f"{body}\n\n{block}")
    store.comment(number, "An older comment.")
    store.comment(number, f"{CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER}\nThe last check.")
    store.comment(number, "Keep this item: the scanner lacks a feature.")
    store.comment(number, "A second reply.")
    script = _searching(AlternativesReply(verdict=Verdict.NONE))

    _plan(store, script)

    assert _prompt_of(script.seen[0]) == {
        "number": number,
        "title": "Scan a directory",
        "body": body,
        "replies": ["Keep this item: the scanner lacks a feature.", "A second reply."],
        "search_budget": {"searches": 3, "results_per_search": 5, "fact_reads": 6},
    }


def test_the_request_holds_every_comment_when_the_job_left_none(
    store: InMemoryRoadmapStore, web_key: None
) -> None:
    number = _item(store)
    store.comment(number, "A person's note.")
    script = _searching(AlternativesReply(verdict=Verdict.NONE))

    _plan(store, script)

    assert _prompt_of(script.seen[0])["replies"] == ["A person's note."]


# ── Writes ────────────────────────────────────────────────────────────────────


def test_a_covering_tool_makes_one_comment_one_block_and_the_record(
    store: InMemoryRoadmapStore, web_key: None, stub_web: StubWeb
) -> None:
    _firecrawl(stub_web, SEARCH_URL)
    number = _item(store, body="The job needs a scanner.")
    before = store.item(number)
    assert before is not None
    script = _search_then_read_then(_covers())

    plan = _plan(store, script)
    written = apply_alternatives(store, plan)

    after = store.item(number)
    assert after is not None
    comments = [c.body for c in store.comments_on(number)]
    assert (
        written,
        after.labels == before.labels,
        after.state.value,
        comments,
        store.read_issue_body(number),
        {k.value: v for k, v in after.job_record.items() if k.value.startswith("alternatives.")},
    ) == (
        1,
        True,
        "open",
        [
            "\n".join(
                [
                    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
                    "## Alternatives check: covers",
                    "",
                    f"Tool: example/scanner ({TOOL_URL})",
                    "- License: MIT",
                    f"- Last activity: {_days_ago(5).date()}",
                    "- Maintained: yes",
                    "",
                    "Covers:",
                    "- Scans a directory.",
                    "",
                    "Lacks:",
                    "- No SARIF output.",
                    "",
                    "Searches run:",
                    "- scanner for a directory",
                    "",
                    "Sources:",
                    f"- {TOOL_URL}",
                    f"- {SEARCH_URL}",
                    "",
                    f"Checked on {NOW.date()}. A person decides what this means for the item. "
                    "The check changes no label and closes no issue.",
                ]
            )
        ],
        "\n".join(
            [
                "The job needs a scanner.",
                "",
                CONST_ROADMAP_ALTERNATIVES_START_MARKER,
                f"Alternatives check of {NOW.date()}: covers.",
                f"Tool: example/scanner ({TOOL_URL}), MIT, last activity "
                f"{_days_ago(5).date()}, maintained.",
                CONST_ROADMAP_ALTERNATIVES_END_MARKER,
            ]
        ),
        {
            "alternatives.body_hash": body_hash_of("The job needs a scanner."),
            "alternatives.checked_at": NOW.isoformat(),
            "alternatives.failed_at": None,
            "alternatives.failed_error": None,
            "alternatives.tool": TOOL_URL,
            "alternatives.verdict": "covers",
        },
    )


def test_a_second_run_inside_the_window_on_an_unchanged_body_does_nothing(
    store: InMemoryRoadmapStore, web_key: None, stub_web: StubWeb
) -> None:
    _firecrawl(stub_web, SEARCH_URL)
    number = _item(store)
    apply_alternatives(store, _plan(store, _search_then_read_then(_covers())))
    writes = len(store.job_writes())
    second = Script(_covers())

    plan = _plan(store, second, now=NOW + timedelta(days=10))

    assert (
        second.seen,
        plan.checks,
        [item.number for item in plan.current],
        apply_alternatives(store, plan),
        len(store.job_writes()) == writes,
        len(store.comments_on(number)),
    ) == ([], [], [number], 0, True, 1)


def test_a_check_after_the_window_replaces_the_block_and_adds_a_comment(
    store: InMemoryRoadmapStore, web_key: None, stub_web: StubWeb
) -> None:
    _firecrawl(stub_web, SEARCH_URL)
    number = _item(store)
    apply_alternatives(store, _plan(store, _search_then_read_then(_covers())))

    later = NOW + timedelta(days=31)
    again = _searching(AlternativesReply(verdict=Verdict.NONE))
    apply_alternatives(store, _plan(store, again, now=later))

    body = store.read_issue_body(number)
    assert (
        body.count(CONST_ROADMAP_ALTERNATIVES_START_MARKER),
        body.count(CONST_ROADMAP_ALTERNATIVES_END_MARKER),
        f"Alternatives check of {later.date()}: none." in body,
        "covers" in body,
        len(store.comments_on(number)),
    ) == (1, 1, True, False, 2)


def test_a_person_changing_the_body_after_the_plan_stops_its_write(
    store: InMemoryRoadmapStore, web_key: None, caplog: pytest.LogCaptureFixture
) -> None:
    number = _item(store)
    plan = _plan(store, _searching(AlternativesReply(verdict=Verdict.NONE)))
    store.as_actor("alice").write_issue_body(number, "A new text.")

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.alternatives"):
        written = apply_alternatives(store, plan)

    assert (written, store.read_issue_body(number), store.comments_on(number)) == (
        0,
        "A new text.",
        [],
    )
    assert any(f"#{number}" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            f"Intro\n{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\nPERSON TEXT\n", id="start-only"
        ),
        pytest.param(
            f"Intro\nPERSON TEXT\n{CONST_ROADMAP_ALTERNATIVES_END_MARKER}\n", id="end-only"
        ),
        pytest.param(
            f"{CONST_ROADMAP_ALTERNATIVES_END_MARKER}\nPERSON TEXT\n"
            f"{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\n",
            id="end-before-start",
        ),
    ],
)
def test_a_body_with_an_unpaired_marker_is_skipped_and_a_persons_text_is_kept(
    store: InMemoryRoadmapStore, web_key: None, body: str
) -> None:
    number = _item(store, "Unpaired", body=body)

    plan = _plan(store, _searching(AlternativesReply(verdict=Verdict.NONE)))
    written = apply_alternatives(store, plan)

    assert (
        plan.checks,
        [(f.item.number, f.reason) for f in plan.failures],
        written,
        store.read_issue_body(number),
    ) == (
        [],
        [(number, "the body holds a marker of the check with no partner")],
        0,
        body,
    )


def test_a_none_verdict_names_no_tool(store: InMemoryRoadmapStore, web_key: None) -> None:
    number = _item(store)
    reply = AlternativesReply(verdict=Verdict.NONE)

    apply_alternatives(store, _plan(store, _searching(reply)))

    item = store.item(number)
    assert item is not None
    (comment,) = store.comments_on(number)
    assert (
        item.job_record.get(AlternativesRecordKey.VERDICT),
        item.job_record.get(AlternativesRecordKey.TOOL),
        "Tool: none found" in comment.body,
    ) == ("none", None, True)


def test_a_not_applicable_verdict_after_a_search_or_a_fact_read_is_refused(
    store: InMemoryRoadmapStore, web_key: None, stub_web: StubWeb
) -> None:
    _firecrawl(stub_web, SEARCH_URL)
    searched = _item(store, "Searched")
    read = _item(store, "Read")
    answer = AlternativesReply(verdict=Verdict.NOT_APPLICABLE)
    script = _by_item(
        {
            searched: [call("search_web", query="scanner for a directory"), answer],
            read: [call("github_repository", name="example/scanner"), answer],
        }
    )

    plan = _plan(store, script)

    reason = "the reply gives the verdict not-applicable, which the job sets for a skip class only"
    assert (plan.checks, [(f.item.number, f.reason) for f in plan.failures]) == (
        [],
        [(searched, reason), (read, reason)],
    )


def test_a_covering_tool_is_written_through_the_github_store_over_its_process_edge(
    web_key: None, stub_web: StubWeb
) -> None:
    """The whole flow on the GitHub store: the repository and its release are read with two `gh`
    requests, and the run writes one comment, the marker block and the record in one body write."""
    github = GitHubFake(REPO)
    github.seed_repository(
        {
            "full_name": "example/scanner",
            "html_url": TOOL_URL,
            "license": {"spdx_id": "MIT"},
            "archived": False,
            "pushed_at": _days_ago(5).isoformat(),
            "stargazers_count": 120,
        },
        {"tag_name": "v1.2.0", "published_at": _days_ago(9).isoformat()},
    )
    github.seed_issue(
        7,
        "Scan a directory",
        labels=("priority/p2-medium", "status/new"),
        body="The job needs a scanner.",
    )
    _firecrawl(stub_web, SEARCH_URL)
    roadmap = GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github))

    plan = _plan(roadmap, _search_then_read_then(_covers()))
    written = apply_alternatives(roadmap, plan)
    unchanged = _plan(roadmap, _searching(AlternativesReply(verdict=Verdict.NONE)), now=NOW)

    body = github.body(7)
    (comment,) = github.comments[7]
    assert (
        written,
        [call[-1] for call in github.calls if "repos/example/scanner" in call[-1]],
        CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER in comment,
        body.count(CONST_ROADMAP_ALTERNATIVES_START_MARKER),
        TOOL_URL in body and "MIT" in body,
        '"alternatives.verdict": "covers"' in body,
        unchanged.checks,
        github.project_calls(),
    ) == (
        1,
        ["repos/example/scanner", "repos/example/scanner/releases/latest"],
        True,
        1,
        True,
        True,
        [],
        [],
    )


# ── Skip classes and the search before a verdict ──────────────────────────────


@pytest.mark.parametrize("kind", ["test", "docs", "refactor", "chore", "ci", "perf"])
def test_skip_class_an_item_of_the_type_is_not_applicable_with_no_model_call(
    store: InMemoryRoadmapStore, web_key: None, stub_web: StubWeb, otlp: FakeCollector, kind: str
) -> None:
    number = _item(store, f"{kind}(roadmap): a change")
    script = _searching(AlternativesReply(verdict=Verdict.NONE))
    searches_before = len(stub_web.sent)

    plan = _plan(store, script)
    written = apply_alternatives(store, plan)

    (check,) = plan.checks
    (comment,) = store.comments_on(number)
    assert (
        (check.verdict, check.skip_class, check.queries, check.tool),
        script.seen,
        len(stub_web.sent) == searches_before,
        written,
        f"Class: {kind}. The check makes no search" in comment.body,
        f"Class: {kind}, no search." in store.read_issue_body(number),
        _recorded(store, number, AlternativesRecordKey.VERDICT),
        otlp.points(ROADMAP_ALTERNATIVES_TOTAL.name),
    ) == (
        (Verdict.NOT_APPLICABLE, kind, (), None),
        [],
        True,
        1,
        True,
        True,
        "not-applicable",
        [({"verdict": "not-applicable"}, 1.0)],
    )


def test_skip_class_a_fix_with_a_stack_trace_is_not_applicable_with_no_model_call(
    store: InMemoryRoadmapStore, web_key: None
) -> None:
    body = 'It crashes.\n\nTraceback (most recent call last):\n  File "x.py", line 1\nValueError'
    number = _item(store, "fix(roadmap): a crash", body=body)
    script = _searching(AlternativesReply(verdict=Verdict.NONE))

    plan = _plan(store, script)
    apply_alternatives(store, plan)

    (comment,) = store.comments_on(number)
    assert (
        [(c.verdict, c.skip_class) for c in plan.checks],
        script.seen,
        "Class: fix-with-stack-trace." in comment.body,
    ) == ([(Verdict.NOT_APPLICABLE, "fix-with-stack-trace")], [], True)


@pytest.mark.parametrize(
    ("title", "body"),
    [
        pytest.param("feat(roadmap): x", "A need.", id="feat"),
        pytest.param("build(roadmap): x", "A need.", id="build"),
        pytest.param("style(roadmap): x", "A need.", id="style"),
        pytest.param("fix(roadmap): a crash", "It crashes with no trace.", id="fix-with-no-trace"),
        pytest.param("Scan a directory", "A need.", id="no-type"),
    ],
)
def test_skip_class_an_item_of_another_type_goes_to_the_model(
    store: InMemoryRoadmapStore, web_key: None, title: str, body: str
) -> None:
    from devops_cli.roadmap.alternatives import skip_class_of

    number = _item(store, title, body=body)
    script = _searching(AlternativesReply(verdict=Verdict.NONE))

    plan = _plan(store, script)

    item = store.item(number)
    assert item is not None
    assert (
        skip_class_of(item),
        len(script.seen),
        [(c.verdict, c.skip_class) for c in plan.checks],
    ) == (None, 2, [(Verdict.NONE, None)])


def test_skip_class_an_item_with_an_unpaired_marker_is_a_failure_and_nothing_is_written(
    store: InMemoryRoadmapStore, web_key: None
) -> None:
    body = f"Intro\n{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\nPERSON TEXT\n"
    number = _item(store, "docs(roadmap): a page", body=body)
    script = _searching(AlternativesReply(verdict=Verdict.NONE))

    plan = _plan(store, script)
    written = apply_alternatives(store, plan)

    assert (
        plan.checks,
        [(f.item.number, f.reason) for f in plan.failures],
        written,
        store.read_issue_body(number),
        store.comments_on(number),
        script.seen,
    ) == (
        [],
        [(number, "the body holds a marker of the check with no partner")],
        0,
        body,
        [],
        [],
    )


def _retry_prompts(script: Script) -> list[str]:
    """The text of each retry prompt that the model received in its last request."""
    return [
        str(part.content)
        for message in script.seen[-1]
        for part in getattr(message, "parts", ())
        if isinstance(part, RetryPromptPart)
    ]


def test_search_first_a_reply_with_no_search_gets_one_more_turn_and_the_search_counts(
    store: InMemoryRoadmapStore, web_key: None, otlp: FakeCollector
) -> None:
    number = _item(store, "feat(roadmap): point argo cd at gitea")
    answer = AlternativesReply(verdict=Verdict.NONE)
    script = Script(answer, _SEARCH, answer)

    plan = _plan(store, script)

    (check,) = plan.checks
    assert (
        len(script.seen),
        check.item.number,
        check.queries,
        any("Call search_web at least once" in text for text in _retry_prompts(script)),
        len(otlp.points(FIRECRAWL_SEARCHES_TOTAL.name)) > 0,
    ) == (3, number, ("scanner",), True, True)


def test_search_first_two_replies_with_no_search_end_as_a_failed_check(
    store: InMemoryRoadmapStore, web_key: None, stub_web: StubWeb
) -> None:
    number = _item(store, "feat(roadmap): point argo cd at gitea")
    searches_before = len(stub_web.sent)
    script = Script(AlternativesReply(verdict=Verdict.NONE))

    plan = _plan(store, script)
    apply_alternatives(store, plan)

    assert (
        len(script.seen),
        plan.checks,
        [(f.item.number, f.reason, f.error_class) for f in plan.failures],
        len(stub_web.sent) == searches_before,
        store.comments_on(number),
    ) == (
        2,
        [],
        [(number, "the reply gives a verdict with no search", "RefusedReply")],
        True,
        [],
    )


def test_search_first_a_not_applicable_reply_from_the_model_is_refused(
    store: InMemoryRoadmapStore, web_key: None
) -> None:
    number = _item(store, "feat(roadmap): point argo cd at gitea")
    answer = AlternativesReply(verdict=Verdict.NOT_APPLICABLE)
    script = Script(answer, _SEARCH, answer)

    plan = _plan(store, script)

    assert (
        len(script.seen),
        plan.checks,
        [(f.item.number, f.reason) for f in plan.failures],
    ) == (
        3,
        [],
        [
            (
                number,
                "the reply gives the verdict not-applicable, which the job sets for a skip "
                "class only",
            )
        ],
    )


# ── What the job sets itself ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("facts", "maintained"),
    [
        pytest.param({"archived": True, "pushed_at": _days_ago(2)}, False, id="archived"),
        pytest.param({"pushed_at": _days_ago(2 * 365)}, False, id="quiet-for-two-years"),
        pytest.param({"pushed_at": _days_ago(364)}, True, id="pushed-within-a-year"),
        pytest.param({"pushed_at": None}, False, id="never-pushed"),
    ],
)
def test_the_job_sets_maintained_from_the_facts_a_tool_read(
    store: InMemoryRoadmapStore, web_key: None, facts: dict[str, Any], maintained: bool
) -> None:
    store.seed_repository(
        RepositoryFacts(full_name="example/scanner", url=TOOL_URL, license="MIT", **facts)
    )
    _item(store)

    plan = _plan(
        store,
        Script(_SEARCH, call("github_repository", name="example/scanner"), _covers(sources=[])),
    )

    tool = plan.checks[0].tool
    assert (tool.maintained, tool.license) == (maintained, "MIT")


def test_a_pypi_package_is_maintained_when_its_latest_upload_is_recent(
    store: InMemoryRoadmapStore, web_key: None, stub_web: StubWeb
) -> None:
    _pypi(stub_web, "scanner", uploads=[_days_ago(100).isoformat()], license_expression="MIT")
    _item(store)
    url = "https://pypi.org/project/scanner"
    reply = _covers(tool_url=f"{url}/", sources=[])

    plan = _plan(store, Script(_SEARCH, call("pypi_package", name="scanner"), reply))

    tool = plan.checks[0].tool
    assert (tool.maintained, tool.url) == (True, url)


# ── Refused replies and failed calls ──────────────────────────────────────────


_READ_THE_TOOL = call("github_repository", name="example/scanner")


@pytest.mark.parametrize(
    ("steps", "reason"),
    [
        pytest.param(
            [_SEARCH, _READ_THE_TOOL, _covers(sources=["https://example.com/invented"])],
            "the reply cites a URL that no tool returned: https://example.com/invented",
            id="made-up-source",
        ),
        pytest.param(
            [_SEARCH, _covers(tool_url="https://github.com/example/invented")],
            "the reply names a tool whose facts no tool read: https://github.com/example/invented",
            id="tool-with-no-facts",
        ),
        pytest.param(
            [_SEARCH, _covers(tool_url=None)],
            "the reply gives the verdict covers with no tool",
            id="verdict-with-no-tool",
        ),
    ],
)
def test_a_refused_reply_skips_its_item_and_the_others_are_written(
    store: InMemoryRoadmapStore,
    web_key: None,
    steps: list[Any],
    reason: str,
) -> None:
    refused = _item(store, "Refused")
    kept = _item(store, "Kept")
    script = _by_item(
        {refused: steps, kept: _after_search(AlternativesReply(verdict=Verdict.NONE))}
    )

    plan = _plan(store, script)
    written = apply_alternatives(store, plan)
    raise_for_failed_checks(plan)

    assert (
        [c.item.number for c in plan.checks],
        [(f.item.number, f.reason) for f in plan.failures],
        written,
        store.comments_on(refused),
        _failure_record(store, refused),
    ) == ([kept], [(refused, reason)], 1, [], (NOW.isoformat(), "RefusedReply"))


def test_a_failed_model_call_skips_its_item_and_names_the_error_class(
    store: InMemoryRoadmapStore, web_key: None
) -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    failing = _item(store, "Failing")
    kept = _item(store, "Kept")
    script = _by_item(
        {
            failing: ModelHTTPError(500, "m"),
            kept: _after_search(AlternativesReply(verdict=Verdict.NONE)),
        }
    )

    plan = _plan(store, script)
    raise_for_failed_checks(plan)

    assert (
        [c.item.number for c in plan.checks],
        [(f.item.number, f.reason, f.error_class) for f in plan.failures],
    ) == ([kept], [(failing, "the model call failed (AIClientError)", "AIClientError")])


def test_a_run_that_spends_its_budget_skips_its_item(
    store: InMemoryRoadmapStore, web_key: None, stub_web: StubWeb
) -> None:
    _firecrawl(stub_web, SEARCH_URL)
    number = _item(store)
    plan = _plan(store, Script(call("search_web", query="q")))

    ((failure),) = plan.failures
    assert (
        failure.item.number,
        failure.error_class,
        failure.reason.startswith("the model's run stopped (UsageLimitExceeded: "),
        len(failure.reason) > len("the model's run stopped (UsageLimitExceeded: )"),
    ) == (number, "UsageLimitExceeded", True, True)


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        pytest.param(
            "The next request would exceed the limit.",
            "the model's run stopped (UsageLimitExceeded: The next request would exceed the limit.)",
            id="with-message",
        ),
        pytest.param("", "the model's run stopped (UsageLimitExceeded)", id="no-message"),
    ],
)
def test_failure_record_the_reason_of_a_stopped_run_holds_its_message(
    store: InMemoryRoadmapStore,
    web_key: None,
    monkeypatch: pytest.MonkeyPatch,
    message: str,
    reason: str,
) -> None:
    from devops_cli.roadmap.refine_investigation import InvestigationStopped

    number = _item(store)
    monkeypatch.setattr(
        "devops_cli.roadmap.alternatives.investigate",
        lambda *_args, **_kwargs: InvestigationStopped("UsageLimitExceeded", message),
    )

    plan = _plan(store, _searching(AlternativesReply(verdict=Verdict.NONE)))
    apply_alternatives(store, plan)

    assert (
        [(f.item.number, f.reason) for f in plan.failures],
        _failure_record(store, number),
    ) == ([(number, reason)], (NOW.isoformat(), "UsageLimitExceeded"))


def test_rejected_credentials_stop_the_run_at_the_first_item(
    store: InMemoryRoadmapStore, web_key: None
) -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    first = _item(store, "First")
    _item(store, "Second")
    script = _by_item({first: ModelHTTPError(401, "m")})

    with pytest.raises(AICredentialsError) as raised:
        _plan(store, script)
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"

    assert len(script.seen) == 1
    assert store.job_writes() == []


def test_the_models_text_makes_no_live_link_mention_or_marker(
    store: InMemoryRoadmapStore, web_key: None
) -> None:
    number = _item(store)
    hostile = _covers(
        tool_url=TOOL_URL,
        covers=[
            f"Ping @someone {CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER} ![x](https://example.com/p.png)"
        ],
        lacks=[f"{CONST_ROADMAP_ALTERNATIVES_END_MARKER} see https://example.com/evil"],
        sources=[TOOL_URL],
    )
    script = Script(_SEARCH, call("github_repository", name="example/scanner"), hostile)

    apply_alternatives(store, _plan(store, script))

    (comment,) = store.comments_on(number)
    body = store.read_issue_body(number)
    assert (
        comment.body.count(CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER),
        "`@someone`" in comment.body,
        "<b>" in comment.body,
        "![" in comment.body,
        "`https://example.com/evil`" in comment.body,
        body.count(CONST_ROADMAP_ALTERNATIVES_END_MARKER),
        "@someone" in body,
    ) == (1, True, False, False, True, 1, False)


# ── Off ───────────────────────────────────────────────────────────────────────


def test_a_private_repository_turns_the_check_off(
    store: InMemoryRoadmapStore, web_key: None, stub_web: StubWeb
) -> None:
    _item(store)
    store.seed_visibility(is_private=True)
    script = _searching(AlternativesReply(verdict=Verdict.NONE))

    plan = _plan(store, script)

    assert (
        plan.off_reason,
        plan.checks,
        script.seen,
        stub_web.sent,
        apply_alternatives(store, plan),
        store.job_writes(),
        "The check is off: the repository is private." in render_alternatives_plan(plan),
    ) == ("the repository is private", [], [], [], 0, [], True)


def test_a_missing_firecrawl_key_turns_the_check_off(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any]
) -> None:
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config(firecrawl={"api_key": None})
    _item(store)
    script = _searching(AlternativesReply(verdict=Verdict.NONE))

    plan = _plan(store, script)

    assert (plan.off_reason, plan.checks, script.seen, plan.has_writes) == (
        "no Firecrawl key is set",
        [],
        [],
        False,
    )


# ── The report and the command ────────────────────────────────────────────────


def test_the_report_names_each_check_each_current_item_and_each_failure(
    store: InMemoryRoadmapStore, web_key: None
) -> None:
    checked = _item(store, "Checked now")
    current = _item(store, "Checked lately")
    failed = _item(store, "Failing")
    _mark_checked(store, current, days=2)
    script = _by_item(
        {
            checked: _after_search(AlternativesReply(verdict=Verdict.NONE)),
            failed: [_SEARCH, _READ_THE_TOOL, _covers(sources=["https://example.com/invented"])],
        }
    )

    report = render_alternatives_plan(_plan(store, script))

    assert report.splitlines() == [
        f"# Alternatives check for {REPO}",
        "## Checked",
        f"- #{checked} Checked now: none",
        "## Checked lately",
        f"- #{current} Checked lately: checked on {_days_ago(2).date()}, the text is unchanged",
        "## Skipped",
        f"- #{failed} Failing: skipped, the reply cites a URL that no tool returned: "
        "https://example.com/invented",
    ]


def test_the_command_previews_a_check_and_writes_it_with_confirm(
    roadmap_store: InMemoryRoadmapStore, web_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = _item(roadmap_store)
    script = _searching(AlternativesReply(verdict=Verdict.NONE))
    monkeypatch.setattr(
        "devops_cli.roadmap.alternatives.get_task_model", lambda _task: script.model()
    )

    preview = CliRunner().invoke(roadmap_app, ["alternatives", "--repo", REPO])
    written_by_preview = roadmap_store.comments_on(number)
    confirmed = CliRunner().invoke(roadmap_app, ["alternatives", "--repo", REPO, "--confirm"])

    assert (
        preview.exit_code,
        f"- #{number} Scan a directory: none" in preview.output,
        written_by_preview,
        confirmed.exit_code,
        len(roadmap_store.comments_on(number)),
    ) == (0, True, [], 0, 1)


def test_total_failure_the_command_exits_1_when_its_only_item_fails(
    roadmap_store: InMemoryRoadmapStore, web_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = _item(roadmap_store)
    script = Script(_SEARCH, _READ_THE_TOOL, _covers(sources=["https://example.com/invented"]))
    monkeypatch.setattr(
        "devops_cli.roadmap.alternatives.get_task_model", lambda _task: script.model()
    )

    result = CliRunner().invoke(roadmap_app, ["alternatives", "--repo", REPO, "--confirm"])

    assert (
        result.exit_code,
        f"#{number}" in result.output,
        _failure_record(roadmap_store, number),
    ) == (
        1,
        True,
        (_recorded(roadmap_store, number, AlternativesRecordKey.FAILED_AT), "RefusedReply"),
    )


def test_total_failure_the_command_exits_0_when_one_item_fails_and_one_is_checked(
    roadmap_store: InMemoryRoadmapStore, web_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    failing = _item(roadmap_store, "Failing")
    kept = _item(roadmap_store, "Kept")
    script = _by_item(
        {
            failing: [_SEARCH, _READ_THE_TOOL, _covers(sources=["https://example.com/invented"])],
            kept: _after_search(AlternativesReply(verdict=Verdict.NONE)),
        }
    )
    monkeypatch.setattr(
        "devops_cli.roadmap.alternatives.get_task_model", lambda _task: script.model()
    )

    result = CliRunner().invoke(roadmap_app, ["alternatives", "--repo", REPO, "--confirm"])

    assert (
        result.exit_code,
        f"#{failing} Failing: skipped" in result.output,
        len(roadmap_store.comments_on(kept)),
        _failure_record(roadmap_store, failing)[1],
    ) == (0, True, 1, "RefusedReply")


@pytest.mark.parametrize(
    "modes", [["--dry-run", "--confirm"], ["--plan", "--confirm"], ["--plan", "--dry-run"]]
)
def test_more_than_one_mode_flag_is_refused(modes: list[str]) -> None:
    result = CliRunner().invoke(roadmap_app, ["alternatives", "--repo", REPO, *modes])

    assert (result.exit_code, "Pass one of" in result.output) == (1, True)


def test_the_command_checks_the_one_item_it_names(
    roadmap_store: InMemoryRoadmapStore, web_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    named = _item(roadmap_store, "Named")
    other = _item(roadmap_store, "Other")
    script = _searching(AlternativesReply(verdict=Verdict.NONE))
    monkeypatch.setattr(
        "devops_cli.roadmap.alternatives.get_task_model", lambda _task: script.model()
    )

    result = CliRunner().invoke(
        roadmap_app, ["alternatives", "--repo", REPO, "--item", str(named), "--confirm"]
    )

    assert (
        result.exit_code,
        len(roadmap_store.comments_on(named)),
        roadmap_store.comments_on(other),
    ) == (
        0,
        1,
        [],
    )


# ── The Service row ───────────────────────────────────────────────────────────


def _alternatives_row() -> Any:
    return next(row for row in MODEL_LANE_ROWS if row.name == "alternatives")


def _answer_with(monkeypatch: pytest.MonkeyPatch, script: Script) -> None:
    monkeypatch.setattr(
        "devops_cli.roadmap.alternatives.get_task_model", lambda _task: script.model()
    )


def test_the_row_checks_at_most_the_limit_of_the_setting_and_the_command_uses_it_too(
    store: InMemoryRoadmapStore,
    web_key: None,
    config: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    numbers = [_item(store, f"Item {n}") for n in range(4)]
    config(roadmap={"alternatives": {"limit": 2}})
    _answer_with(monkeypatch, _searching(AlternativesReply(verdict=Verdict.NONE)))

    planned = plan_alternatives(store, repo=REPO, now=NOW)
    explicit = plan_alternatives(store, repo=REPO, limit=3, now=NOW)
    _alternatives_row().runner(store=store, repo=REPO)

    assert (
        [c.item.number for c in planned.checks],
        [c.item.number for c in explicit.checks],
        [n for n in numbers if store.comments_on(n)],
    ) == (numbers[:2], numbers[:3], numbers[:2])


def test_the_limit_setting_defaults_to_five_and_is_at_least_one(
    config: Callable[..., Any],
) -> None:
    from pydantic import ValidationError

    from devops_cli.config.settings import AlternativesConfig, load_settings

    config()
    with pytest.raises(ValidationError) as raised:
        AlternativesConfig(limit=0)
    assert len(raised.value.errors()) > 0
    assert load_settings().roadmap.alternatives.limit == 5


def test_total_failure_a_failed_check_records_its_item_and_the_row_succeeds(
    store: InMemoryRoadmapStore, web_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    failing = _item(store, "Failing")
    kept = _item(store, "Kept")
    _answer_with(
        monkeypatch,
        _by_item(
            {
                failing: ModelHTTPError(500, "m"),
                kept: _after_search(AlternativesReply(verdict=Verdict.NONE)),
            }
        ),
    )

    _alternatives_row().runner(store=store, repo=REPO)

    assert (
        store.comments_on(failing),
        len(store.comments_on(kept)),
        _failure_record(store, failing)[1],
        _failure_record(store, kept),
    ) == ([], 1, "AIClientError", (None, None))


def test_total_failure_a_round_in_which_every_check_fails_fails_the_row_and_records_each(
    store: InMemoryRoadmapStore, web_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    first = _item(store, "First")
    second = _item(store, "Second")
    script = _by_item({first: ModelHTTPError(500, "m"), second: ModelHTTPError(503, "m")})
    _answer_with(monkeypatch, script)

    plan = _plan(store, script)
    with pytest.raises(RoadmapAlternativesError) as direct:
        raise_for_failed_checks(plan)
    with pytest.raises(RoadmapAlternativesError) as row:
        _alternatives_row().runner(store=store, repo=REPO)

    assert (
        direct.value.failed_items,
        row.value.failed_items,
        "the check failed for each of the 2 item(s) it tried" in str(row.value),
        _failure_record(store, first)[1],
        _failure_record(store, second)[1],
    ) == ((first, second), (first, second), True, "AIClientError", "AIClientError")


def test_total_failure_a_round_with_no_item_to_check_makes_no_model_call_and_succeeds(
    store: InMemoryRoadmapStore, web_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = _item(store, "Current")
    delayed = _item(store, "Delayed")
    _mark_checked(store, current, days=2)
    _mark_failed(store, delayed, days=1)
    script = _searching(AlternativesReply(verdict=Verdict.NONE))
    _answer_with(monkeypatch, script)

    plan = plan_alternatives(store, repo=REPO, now=NOW)
    raise_for_failed_checks(plan)

    assert (script.seen, plan.checks, plan.failures, plan.has_writes) == ([], [], [], False)


def test_a_round_off_for_want_of_a_key_runs_the_row_and_checks_nothing(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any]
) -> None:
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config()
    number = _item(store)

    outcome = _alternatives_row().runner(store=store, repo=REPO)

    assert (outcome.placed_critical_or_p0, store.comments_on(number)) == (False, [])


def test_the_row_runs_in_a_round_and_records_its_success_until_the_interval_passes(
    store: InMemoryRoadmapStore, web_key: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    number = _item(store)
    _answer_with(monkeypatch, _searching(AlternativesReply(verdict=Verdict.NONE)))
    table = (_alternatives_row(),)

    def round_at(now: datetime) -> tuple[str, ...]:
        return run_due_jobs(
            REPO, store, batch={("poll", "", ""): 1}, table=table, data_dir=tmp_path, now=now
        )

    first = round_at(NOW)
    soon = round_at(NOW + timedelta(minutes=718))
    later = round_at(NOW + timedelta(minutes=720))

    assert (first, soon, later, len(store.comments_on(number))) == (
        ("alternatives",),
        (),
        ("alternatives",),
        1,
    )


def test_the_commands_limit_option_has_no_default_of_its_own(
    roadmap_store: InMemoryRoadmapStore,
    web_key: None,
    config: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    numbers = [_item(roadmap_store, f"Item {n}") for n in range(3)]
    config(roadmap={"alternatives": {"limit": 1}})
    _answer_with(monkeypatch, _searching(AlternativesReply(verdict=Verdict.NONE)))

    result = CliRunner().invoke(roadmap_app, ["alternatives", "--repo", REPO, "--confirm"])

    assert (result.exit_code, [n for n in numbers if roadmap_store.comments_on(n)]) == (
        0,
        numbers[:1],
    )


def test_failure_record_one_of_five_checks_fails_and_the_round_records_it_and_succeeds(
    store: InMemoryRoadmapStore, web_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    numbers = [_item(store, f"Item {n}") for n in range(5)]
    failing = numbers[2]
    before = store.read_issue_body(failing)
    script = _by_item(
        {
            n: ModelHTTPError(500, "m")
            if n == failing
            else _after_search(AlternativesReply(verdict=Verdict.NONE))
            for n in numbers
        }
    )
    _answer_with(monkeypatch, script)
    monkeypatch.setattr(
        "devops_cli.roadmap.alternatives.datetime",
        type("_FixedClock", (datetime,), {"now": classmethod(lambda cls, tz=None: NOW)}),
    )

    _alternatives_row().runner(store=store, repo=REPO)

    assert (
        [n for n in numbers if store.comments_on(n)],
        _failure_record(store, failing),
        store.read_issue_body(failing),
        _recorded(store, failing, AlternativesRecordKey.CHECKED_AT),
    ) == ([n for n in numbers if n != failing], (NOW.isoformat(), "AIClientError"), before, None)


def test_failure_record_a_plan_that_is_not_applied_changes_no_job_record(
    store: InMemoryRoadmapStore, web_key: None
) -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    number = _item(store)

    plan = _plan(store, Script(ModelHTTPError(500, "m")))

    assert (plan.has_writes, store.job_writes(), _failure_record(store, number)) == (
        True,
        [],
        (None, None),
    )


def test_failure_record_a_failed_item_is_tried_again_after_the_delay_and_its_check_clears_it(
    store: InMemoryRoadmapStore, web_key: None
) -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    number = _item(store)
    apply_alternatives(store, _plan(store, Script(ModelHTTPError(500, "m"))))
    soon = _searching(AlternativesReply(verdict=Verdict.NONE))
    later = _searching(AlternativesReply(verdict=Verdict.NONE))

    early = _plan(store, soon, now=NOW + timedelta(days=1))
    apply_alternatives(store, early)
    recorded_early = _failure_record(store, number)
    written = apply_alternatives(store, _plan(store, later, now=NOW + timedelta(days=4)))

    assert (
        soon.seen,
        early.checks,
        early.failures,
        recorded_early,
        written,
        len(later.seen),
        _failure_record(store, number),
        _recorded(store, number, AlternativesRecordKey.VERDICT),
    ) == ([], [], [], (NOW.isoformat(), "AIClientError"), 1, 2, (None, None), "none")


# ── The metric ────────────────────────────────────────────────────────────────


def test_each_written_check_counts_once_by_its_verdict(
    store: InMemoryRoadmapStore, web_key: None, stub_web: StubWeb, otlp: FakeCollector
) -> None:
    _firecrawl(stub_web, SEARCH_URL)
    covering = _item(store, "Covering")
    nothing = _item(store, "Nothing")
    script = _by_item(
        {
            covering: [
                call("search_web", query="scanner"),
                call("github_repository", name="example/scanner"),
                _covers(),
            ],
            nothing: _after_search(AlternativesReply(verdict=Verdict.NONE)),
        }
    )

    plan = _plan(store, script)
    planned_points = otlp.points(ROADMAP_ALTERNATIVES_TOTAL.name)
    apply_alternatives(store, plan)

    assert (planned_points, sorted(otlp.points(ROADMAP_ALTERNATIVES_TOTAL.name), key=str)) == (
        [],
        [({"verdict": "covers"}, 1.0), ({"verdict": "none"}, 1.0)],
    )


def test_a_check_skipped_because_the_body_changed_and_a_failed_check_count_nothing(
    store: InMemoryRoadmapStore, web_key: None, otlp: FakeCollector
) -> None:
    from pydantic_ai.exceptions import ModelHTTPError

    edited = _item(store, "Edited")
    failing = _item(store, "Failing")
    script = _by_item(
        {
            edited: _after_search(AlternativesReply(verdict=Verdict.NONE)),
            failing: ModelHTTPError(500, "m"),
        }
    )

    plan = _plan(store, script)
    store.write_issue_body(edited, "A person rewrote the item.")
    written = apply_alternatives(store, plan)

    assert (written, otlp.points(ROADMAP_ALTERNATIVES_TOTAL.name)) == (0, [])
