"""The reference step inside the alternatives check (#4672): its queries come from the item body
and from the one model reply of the check, a skip-class item sends the rule queries only, mode
`plan` changes no issue, mode `on` writes the links in the block, the comment and the job record,
and a step that finds nothing or fails leaves the verdict of the check.

The roadmap is the in-memory store, which also answers the code search, the reference facts and
the file of a candidate. pydantic-ai's `FunctionModel` answers each model request from a script.
Firecrawl, deps.dev and a documentation page answer at the HTTP edge through `web`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai.messages import ToolReturnPart

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
)
from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_URL
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.alternatives import AlternativesReply, Verdict, plan_alternatives
from devops_cli.roadmap.body_hash import extract_section_and_outside
from devops_cli.roadmap.references.providers import SearchKind
from devops_cli.roadmap.references.step import References, ReferenceStep, open_reference_step
from devops_cli.roadmap.stores.store import (
    AlternativesRecordKey,
    CodeSearchHit,
    ItemField,
    ReferenceFacts,
)
from devops_cli.telemetry.instruments import BRAIN_REFERENCES_TOTAL
from tests.support.fakes.reference_provider import FakeReferenceProvider
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_alternatives import apply_alternatives
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from tests.support.fakes.http import WebFake
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
HEAD = "a" * 40
REASON = "No open tool covers the need."
SEARCH_URL = "https://example.com/agents"
IMPORT = "from pydantic_ai import Agent"
BODY = f"The job needs an agent.\n\n```python\n{IMPORT}\n```\n\nUse `pydantic-ai`."
FILE = "\n".join(["# An agent", "", IMPORT, *(f"line {n}" for n in range(4, 31))])
SEARCH = call("search_web", query="agent framework")
NONE = AlternativesReply(reason=REASON, verdict=Verdict.NONE)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO, is_private=False)


@pytest.fixture(autouse=True)
def firecrawl(config: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, web: WebFake) -> None:
    """A chain of Firecrawl alone, which answers each web search with one result."""
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config(search={"providers": ["firecrawl"]}, firecrawl={"api_key": "fc-test"})
    _serve(web, SEARCH_URL)


def _serve(web: WebFake, *urls: str) -> None:
    results = [{"title": f"Result {url}", "url": url, "description": "A page."} for url in urls]
    body = json.dumps({"success": True, "data": {"web": results}}).encode()
    web.content(DEFAULT_FIRECRAWL_SEARCH_URL, body)


def _mode(config: Callable[..., Any], mode: str) -> None:
    config(
        search={"providers": ["firecrawl"]},
        firecrawl={"api_key": "fc-test"},
        roadmap={"alternatives": {"references": mode}},
    )


def _item(store: InMemoryRoadmapStore, title: str = "Run an agent", body: str = BODY) -> int:
    fields = {ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"}
    return store.seed_issue(title, body=body, fields=fields)


def _candidate(store: InMemoryRoadmapStore, name: str, **facts: Any) -> CodeSearchHit:
    """Make the repository `name`, whose head holds `src/agent.py`, and give its code hit."""
    values: dict[str, Any] = {
        "full_name": name,
        "url": f"https://github.com/{name}",
        "private": False,
        "license": "MIT",
        "pushed_at": NOW - timedelta(days=5),
        "stars": 100,
        "head_sha": HEAD,
    }
    store.seed_reference_facts(ReferenceFacts(**{**values, **facts}))
    store.seed_other_file(name, "src/agent.py", FILE, ref=HEAD)
    return CodeSearchHit(repository=name, path="src/agent.py")


def _permalink(name: str) -> str:
    return f"https://github.com/{name}/blob/{HEAD}/src/agent.py#L3-L22"


def _plan(store: InMemoryRoadmapStore, script: Script, **options: Any) -> Any:
    return plan_alternatives(store, repo=REPO, investigator=script.model(), now=NOW, **options)


def _plan_one(store: InMemoryRoadmapStore, number: int) -> Any:
    """The check of the one item `number`, whatever its last check."""
    return _plan(store, Script(SEARCH, NONE), item_number=number)


def _block(store: InMemoryRoadmapStore, number: int) -> list[str]:
    _, block = extract_section_and_outside(
        store.read_issue_body(number),
        CONST_ROADMAP_ALTERNATIVES_START_MARKER,
        CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    )
    return (block or "").strip().splitlines()


def _record(store: InMemoryRoadmapStore, number: int) -> dict[Any, str | None]:
    item = store.item(number)
    assert item is not None
    return item.job_record


def _searched(messages: list[Any]) -> bool:
    """Whether the run of an item made its web search."""
    return any(
        isinstance(part, ToolReturnPart) and part.tool_name == "search_web"
        for message in messages
        for part in getattr(message, "parts", ())
    )


def _linked(otlp: FakeCollector) -> list[tuple[dict[str, Any], float]]:
    points = otlp.points(BRAIN_REFERENCES_TOTAL.name)
    return [point for point in points if point[0]["result"] == "linked"]


# ── Queries ───────────────────────────────────────────────────────────────────


def test_the_step_sends_the_rule_queries_and_the_queries_of_the_one_reply_of_the_check(
    store: InMemoryRoadmapStore,
) -> None:
    _item(store)
    queries = ["agent tool call", "typed agent", "agent retry", "agent stream"]
    script = Script(SEARCH, NONE.model_copy(update={"reference_queries": queries}))

    plan = _plan(store, script)

    (check,) = plan.checks
    assert (check.verdict, store.code_searches, len(script.seen)) == (
        Verdict.NONE,
        [IMPORT, "agent tool call", "pydantic-ai"],
        2,
    )


def test_a_docs_item_sends_the_rule_queries_makes_no_model_call_and_stays_not_applicable(
    store: InMemoryRoadmapStore, config: Callable[..., Any], web: WebFake
) -> None:
    _mode(config, "on")
    number = _item(store, "docs(roadmap): a change")
    store.seed_code_search(IMPORT, _candidate(store, "example/agent"))
    script = Script(SEARCH, NONE.model_copy(update={"reference_queries": ["never sent"]}))

    plan = _plan(store, script)
    apply_alternatives(store, plan)

    (check,) = plan.checks
    assert (
        check.verdict,
        store.code_searches,
        script.seen,
        store.comments_on(number),
        _block(store, number),
    ) == (
        Verdict.NOT_APPLICABLE,
        [IMPORT, "pydantic-ai"],
        [],
        [],
        [
            f"Alternatives check of {NOW.date()}: not-applicable.",
            "Class: docs, no model call.",
            "Tool: none found.",
            "",
            "Reference implementations:",
            f"- {_permalink('example/agent')}",
        ],
    )


# ── Modes ─────────────────────────────────────────────────────────────────────


def test_mode_on_writes_3_permalinks_in_the_block_the_comment_and_the_record(
    store: InMemoryRoadmapStore, config: Callable[..., Any], otlp: FakeCollector
) -> None:
    _mode(config, "on")
    number = _item(store)
    hits = [_candidate(store, f"example/agent{n}", stars=100 - n) for n in range(4)]
    store.seed_code_search(IMPORT, *hits)
    links = [_permalink(f"example/agent{n}") for n in range(3)]

    plan = _plan(store, Script(SEARCH, NONE))
    apply_alternatives(store, plan)

    (comment,) = store.comments_on(number)
    listed = ["Reference implementations:", *(f"- {link}" for link in links)]
    lines = comment.body.splitlines()
    start = lines.index("Reference implementations:")
    assert (
        _block(store, number)[-4:],
        lines[start : start + 4],
        _record(store, number).get(AlternativesRecordKey.REFS),
        _linked(otlp),
    ) == (
        listed,
        listed,
        " ".join(links),
        [({"provider": "github-code", "result": "linked"}, 3.0)],
    )


def test_two_linked_references_count_under_the_provider_and_the_result_linked(
    store: InMemoryRoadmapStore, config: Callable[..., Any], otlp: FakeCollector
) -> None:
    _mode(config, "on")
    _item(store)
    store.seed_code_search(
        IMPORT, _candidate(store, "example/agent"), _candidate(store, "example/other")
    )

    plan = _plan(store, Script(SEARCH, NONE))
    before_the_write = _linked(otlp)
    apply_alternatives(store, plan)

    assert (before_the_write, _linked(otlp)) == (
        [],
        [({"provider": "github-code", "result": "linked"}, 2.0)],
    )


def test_mode_plan_changes_no_issue_text_and_no_job_record(
    store: InMemoryRoadmapStore, caplog: pytest.LogCaptureFixture
) -> None:
    number = _item(store)
    store.seed_code_search(IMPORT, _candidate(store, "example/agent"))

    with caplog.at_level(logging.INFO):
        plan = _plan(store, Script(SEARCH, NONE))
        apply_alternatives(store, plan)

    (check,) = plan.checks
    (comment,) = store.comments_on(number)
    assert (
        check.references,
        check.references_found,
        _block(store, number),
        _permalink("example/agent") in comment.body,
        AlternativesRecordKey.REFS in _record(store, number),
    ) == (
        References(complete=False),
        1,
        [f"Alternatives check of {NOW.date()}: none.", "Tool: none found.", f"Reason: {REASON}"],
        False,
        False,
    )
    assert f"verified {_permalink('example/agent')} (github-code, mode plan" in caplog.text
    assert "references=1" in caplog.text


def test_mode_off_sends_no_code_search(
    store: InMemoryRoadmapStore, config: Callable[..., Any]
) -> None:
    _mode(config, "off")
    _item(store)

    plan = _plan(store, Script(SEARCH, NONE))

    assert (len(plan.checks), store.code_searches) == (1, [])


def test_a_source_of_the_check_on_the_allowlist_is_written_as_official_documentation(
    store: InMemoryRoadmapStore, config: Callable[..., Any], web: WebFake
) -> None:
    _mode(config, "on")
    number = _item(store)
    official = "https://docs.python.org/3/library/ast.html"
    _serve(web, official, SEARCH_URL)
    web.page(official, "<html>ast</html>")
    reply = NONE.model_copy(update={"sources": [official, SEARCH_URL]})

    apply_alternatives(store, _plan(store, Script(SEARCH, reply)))

    assert (
        _block(store, number)[-2:],
        _record(store, number).get(AlternativesRecordKey.REFS),
    ) == (["Official documentation:", f"- {official}"], official)


# ── Rechecks ──────────────────────────────────────────────────────────────────


def test_a_recheck_with_other_links_posts_no_comment_and_one_with_no_link_clears_the_record(
    store: InMemoryRoadmapStore, config: Callable[..., Any]
) -> None:
    _mode(config, "on")
    number = _item(store)
    store.seed_code_search(IMPORT, _candidate(store, "example/agent"))
    apply_alternatives(store, _plan(store, Script(SEARCH, NONE)))
    store.seed_code_search(IMPORT, _candidate(store, "example/other"))

    apply_alternatives(store, _plan_one(store, number))
    after_other_links = (
        len(store.comments_on(number)),
        _record(store, number).get(AlternativesRecordKey.REFS),
        _block(store, number)[-1],
    )
    store.seed_code_search(IMPORT)
    apply_alternatives(store, _plan_one(store, number))

    assert (
        after_other_links,
        _record(store, number).get(AlternativesRecordKey.REFS),
        "Reference implementations:" in _block(store, number),
    ) == ((1, _permalink("example/other"), f"- {_permalink('example/other')}"), None, False)


def test_a_failed_step_in_mode_on_keeps_the_links_of_the_earlier_check(
    store: InMemoryRoadmapStore, config: Callable[..., Any], otlp: FakeCollector
) -> None:
    """A step that failed found no link, which is not "the item has no link": the block and the
    record keep the links of the earlier check."""
    _mode(config, "on")
    number = _item(store)
    store.seed_code_search(IMPORT, _candidate(store, "example/agent"))
    apply_alternatives(store, _plan(store, Script(SEARCH, NONE)))
    store.fail_read("search_code", GitHubOperationError("HTTP 502", operation="roadmap.read"))

    plan = _plan_one(store, number)
    written = apply_alternatives(store, plan)

    (check,) = plan.checks
    link = _permalink("example/agent")
    assert (
        written,
        check.references_found,
        _block(store, number)[-2:],
        _record(store, number).get(AlternativesRecordKey.REFS),
        _linked(otlp),
    ) == (
        1,
        0,
        ["Reference implementations:", f"- {link}"],
        link,
        [({"provider": "github-code", "result": "linked"}, 1.0)],
    )


@pytest.mark.parametrize("mode", ["plan", "off"])
def test_a_recheck_in_mode_plan_or_off_leaves_the_links_of_the_block_and_of_the_record(
    store: InMemoryRoadmapStore, config: Callable[..., Any], web: WebFake, mode: str
) -> None:
    _mode(config, "on")
    number = _item(store)
    official = "https://docs.python.org/3/library/ast.html"
    _serve(web, official)
    web.page(official, "<html>ast</html>")
    reply = NONE.model_copy(update={"sources": [official]})
    store.seed_code_search(IMPORT, _candidate(store, "example/agent"))
    apply_alternatives(store, _plan(store, Script(SEARCH, reply)))
    before = (_block(store, number)[-5:], _record(store, number).get(AlternativesRecordKey.REFS))
    _mode(config, mode)
    store.seed_code_search(IMPORT, _candidate(store, "example/other"))

    apply_alternatives(store, _plan(store, Script(SEARCH, reply), item_number=number))

    after = (_block(store, number)[-5:], _record(store, number).get(AlternativesRecordKey.REFS))
    assert (before, after) == (
        (
            [
                "Reference implementations:",
                f"- {_permalink('example/agent')}",
                "",
                "Official documentation:",
                f"- {official}",
            ],
            f"{_permalink('example/agent')} {official}",
        ),
        before,
    )


# ── It fails soft ─────────────────────────────────────────────────────────────


def test_a_url_that_the_url_parser_refuses_leaves_the_verdict_of_a_skip_class_and_of_an_item(
    store: InMemoryRoadmapStore,
) -> None:
    body = (
        f"{BODY}\n\nProbe https://[cluster-ip]:6443/healthz, `http://[{{host}}]:{{port}}`, "
        "https://[::1 and https://example.com\uff1a8080."
    )
    skipped = _item(store, "docs(roadmap): a change", body)
    checked = _item(store, "Run an agent", body)

    plan = _plan(store, Script(lambda messages: NONE if _searched(messages) else SEARCH))
    written = apply_alternatives(store, plan)

    assert (
        written,
        plan.failures,
        _record(store, skipped).get(AlternativesRecordKey.VERDICT),
        _record(store, checked).get(AlternativesRecordKey.VERDICT),
    ) == (2, [], "not-applicable", "none")


def test_an_optional_provider_that_is_down_at_the_start_does_not_stop_the_check(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(store)
    down = FakeReferenceProvider("mcp-code", SearchKind.CODE, down=True)

    with open_reference_step(store, mode="plan", private=False, optional=[down]) as step:
        providers = [provider.name for provider in step.providers]
        plan = _plan(store, Script(SEARCH, NONE), reference_step=step)
        written = apply_alternatives(store, plan)

    assert (
        providers,
        written,
        plan.failures,
        _record(store, number).get(AlternativesRecordKey.VERDICT),
        down.queries,
    ) == (["github-code", "github-repository"], 1, [], "none", [])


def test_a_provider_that_holds_a_request_past_the_bound_leaves_the_verdict_of_the_check(
    store: InMemoryRoadmapStore,
) -> None:
    """The provider holds each search until the test ends, so the step of the item cannot end
    before its bound."""
    number = _item(store)
    held = FakeReferenceProvider("mcp-code", SearchKind.CODE)
    held.hold()

    try:
        plan = _plan(
            store, Script(SEARCH, NONE), reference_step=ReferenceStep("on", (held,), seconds=0.05)
        )
        written = apply_alternatives(store, plan)
    finally:
        held.release()

    (check,) = plan.checks
    assert (
        check.references,
        written,
        plan.failures,
        _record(store, number).get(AlternativesRecordKey.VERDICT),
    ) == (References(complete=False), 1, [], "none")
