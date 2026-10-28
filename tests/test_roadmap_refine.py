"""Unit tests for `devops roadmap refine`: selection, minimization, validation,
renderer sanitization, person edit guards, size limit, intake hook, and CLI.

Zero network sockets are opened, LLM and Firecrawl calls are mocked, and all tests run under 1 s.
The model-failure cases (#1363) answer refine's own client at the HTTP edge with httpx2's
`MockTransport`, on a private repository so no web search runs, and retry with no wait.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
import traceback
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion

    from tests.support.fakes.model import ModelFake

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.client.models import (
    AIClientError,
    AICredentialsError,
    ReplyRejectedError,
    StructuredOutputValidationError,
)
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.commands.roadmap import app as roadmap_app
from devops_cli.config import constants
from devops_cli.config.constants import (
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_MAX_BODY_CHARS,
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.config.settings import reset_settings_cache
from devops_cli.exceptions import RoadmapRefineError, RoadmapRunError
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.roadmap import store as roadmap_store_module
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore, JobWrite
from devops_cli.roadmap.refine import (
    AcceptanceCriterion,
    DesignOption,
    QuestionAnswer,
    RefinementProposal,
    RefinePlan,
    WebSearch,
    apply_refine,
    body_questions,
    check_person_edits,
    check_ready,
    collect_context,
    extract_section_and_outside,
    hash_text,
    inspect_checkout,
    needs_investigation,
    plan_refine,
    render_proposal_section,
    render_refine_plan,
    sanitize_text,
    select_candidates,
    validate_proposal,
    web_search_of,
)
from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
    _run_refine_adapter,
    build_stub_table,
    run_due_jobs,
)
from devops_cli.roadmap.store import (
    CloseReason,
    GitHubState,
    Item,
    ItemField,
    RefineRecordKey,
)
from tests.llm_stream_fakes import route_llm_clients

pytestmark = pytest.mark.usefixtures("mock_keyring")

REPO = "example/roadmap"
# The open milestones, planning buckets in due-date order: the first, then the second.
FIRST, SECOND, THIRD = "2026-10-29", "2026-11-05", "2026-11-12"

# The Priority that makes an issue an Item, as a person sets it.
PLACED = {ItemField.PRIORITY: "P2-Medium"}


def _git_run(cwd: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_run(repo, "init", "-q", "-b", "main")
    _git_run(repo, "config", "user.email", "ci@example.com")
    _git_run(repo, "config", "user.name", "CI")
    _git_run(repo, "config", "commit.gpgsign", "false")
    _git_run(repo, "remote", "add", "origin", f"https://example.com/{REPO}.git")

    (repo / "CONTEXT.md").write_text("# Project Context\nArchitecture notes.\n", encoding="utf-8")
    (repo / "docs" / "adr").mkdir(parents=True)
    (repo / "docs" / "adr" / "0001-test.md").write_text(
        "# ADR 1\nDecision record.\n", encoding="utf-8"
    )
    (repo / "src").mkdir()
    (repo / "src" / "sample.py").write_text(
        "def hello_world():\n    return 'hello'\n", encoding="utf-8"
    )

    _git_run(repo, "add", "-A")
    _git_run(repo, "commit", "-q", "-m", "init")
    return repo


class BodyReadCountingStore(InMemoryRoadmapStore):
    """The in-memory roadmap, keeping the number of each issue whose body it is asked to read."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.body_reads: list[int] = []

    def read_issue_body(self, number: int) -> str:
        self.body_reads.append(number)
        return super().read_issue_body(number)


@pytest.fixture
def store() -> BodyReadCountingStore:
    s = BodyReadCountingStore(repo=REPO)
    s.seed_milestone(FIRST, due_on=date(2026, 10, 29), state=GitHubState.OPEN)
    s.seed_milestone(SECOND, due_on=date(2026, 11, 5), state=GitHubState.OPEN)
    return s


class MockLLMClient:
    def __init__(
        self,
        proposal: RefinementProposal | None = None,
        fail_with: AIClientError | None = None,
    ):
        self.fail_with = fail_with
        self.proposal = proposal or RefinementProposal(
            problem_statement="Test problem",
            acceptance_criteria=[AcceptanceCriterion(description="C1", verification="V1")],
            key_questions=[],
            fits_one_pr=True,
            split_offs=[],
            suspected_block=None,
            dependencies=[],
        )
        self.calls: list[tuple[str, str, Any]] = []

    def chat_structured(self, system: str, prompt: str, schema: type[Any]) -> Any:
        self.calls.append((system, prompt, schema))
        if self.fail_with is not None:
            raise self.fail_with
        return self.proposal


def test_extract_section_and_outside_and_hashes() -> None:
    body_plain = "Heading\n\nSome body text without section."
    out1, sec1 = extract_section_and_outside(body_plain)
    assert (out1, sec1) == (body_plain, None)

    section_content = "\n## Proposed design\nProposal text.\n"
    body_with_sec = f"Intro\n{CONST_ROADMAP_REFINE_START_MARKER}{section_content}{CONST_ROADMAP_REFINE_END_MARKER}\nOutro"
    out2, sec2 = extract_section_and_outside(body_with_sec)
    assert (
        out2,
        sec2,
        hash_text("   hello   ") == hash_text("hello"),
    ) == (
        "Intro\n\nOutro",
        section_content,
        True,
    )


def test_inspect_checkout_origin_match_and_mismatch(git_repo: Path) -> None:
    sha = inspect_checkout(git_repo, REPO)
    assert len(sha) == 40

    with pytest.raises(GitHubOperationError, match="does not match"):
        inspect_checkout(git_repo, "other/mismatch-repo")


def test_collect_context_and_truncation(git_repo: Path) -> None:
    sha = inspect_checkout(git_repo, REPO)
    body = "Review src/sample.py:1-2 and `hello_world` identifier."
    ctx = collect_context(git_repo, sha, body, max_tokens=1000)
    assert (
        "Project Context" in ctx,
        "ADR 1" in ctx,
        "def hello_world" in ctx,
        "hello_world" in ctx,
    ) == (True, True, True, True)

    short_ctx = collect_context(git_repo, sha, body, max_tokens=10)
    assert "[truncated due to context budget]" in short_ctx


def test_collect_context_handles_spaces_and_non_ascii_adrs(git_repo: Path) -> None:
    """collect_context reads ADR files whose names have spaces or non-ASCII characters without C-quoting failure."""
    adr_file = git_repo / "docs" / "adr" / "0002-café decision with space.md"
    adr_file.write_text("# ADR 2\nSpecial ADR content.\n", encoding="utf-8")
    _git_run(git_repo, "add", "-A")
    _git_run(git_repo, "commit", "-q", "-m", "add special adr")
    new_sha = inspect_checkout(git_repo, REPO)

    ctx = collect_context(git_repo, new_sha, "body", max_tokens=1000)
    assert "Special ADR content." in ctx
    assert "0002-café decision with space.md" in ctx


def test_the_web_search_state_of_a_round_whose_visibility_read_fails(
    store: InMemoryRoadmapStore, caplog: pytest.LogCaptureFixture
) -> None:
    """A spent quota stops the round, and any other failed read of the repository's visibility
    turns web search off with its reason and a warning (#1365, #2398)."""
    with (
        patch.object(
            store,
            "repository_is_private",
            side_effect=GitHubRateLimitError("GraphQL budget exhausted"),
        ),
        pytest.raises(GitHubRateLimitError),
    ):
        web_search_of(store)

    with (
        patch.object(
            store,
            "repository_is_private",
            side_effect=GitHubOperationError("transient read failure", operation="read"),
        ),
        caplog.at_level(logging.WARNING),
    ):
        web = web_search_of(store)

    assert (
        web,
        any("Could not read repository visibility" in r.getMessage() for r in caplog.records),
    ) == (WebSearch(off_reason="the repository's visibility could not be read"), True)


def test_validate_proposal_sources_and_questions(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    sha = inspect_checkout(git_repo, REPO)
    body = (
        "## Description\nSome description.\n\n"
        "## Key questions\n- How to authenticate?\n- What database is used?\n\n"
        "## Owner decisions\n- Use SQLite for local storage\n"
    )
    raw = RefinementProposal(
        problem_statement="Problem statement",
        acceptance_criteria=[
            AcceptanceCriterion(description="Test pass", verification="uv run devops ci")
        ],
        key_questions=[
            # Fact with valid file source
            QuestionAnswer(
                question="How to authenticate?",
                answer="Token based",
                kind="fact",
                sources=["src/sample.py:1"],
                body_question=1,
            ),
            # Fact with invalid source
            QuestionAnswer(
                question="What is the port?",
                answer="Port 8080",
                kind="fact",
                sources=["src/nonexistent.py:99"],
            ),
            # Decision quoting owner decision
            QuestionAnswer(
                question="Which database?",
                answer="Use SQLite for local storage",
                kind="decision",
                sources=[],
            ),
            # Decision not quoting owner decision
            QuestionAnswer(
                question="Which framework?",
                answer="Use Typer",
                kind="decision",
                sources=[],
            ),
        ],
        fits_one_pr=True,
    )

    validated, open_qs = validate_proposal(
        raw, body, {"https://example.com/doc"}, git_repo, sha, store
    )
    answers = {qa.question: qa.answer for qa in validated.key_questions}

    assert (
        "(owner decision)" in answers["Which database?"],
        "(proposed)" in answers["Which framework?"],
        any("What database is used?" in q for q in open_qs),
        any("What is the port?" in q for q in open_qs),
    ) == (True, True, True, True)


@pytest.mark.parametrize(
    "answered",
    [[], [QuestionAnswer(question="Which store?", answer="The job record.", kind="decision")]],
    ids=["none", "answered"],
)
def test_the_key_questions_of_refines_own_section_are_never_asked_again(
    git_repo: Path, store: InMemoryRoadmapStore, answered: list[QuestionAnswer]
) -> None:
    """Refine reads the person's key questions from the body outside its own section, so the
    questions and the "None." its last section lists open no question when it refines the item
    again (#1758)."""
    sha = inspect_checkout(git_repo, REPO)
    proposal = RefinementProposal(
        problem_statement="The item needs a design.",
        acceptance_criteria=[AcceptanceCriterion(description="C", verification="V")],
    )
    last_round = proposal.model_copy(update={"key_questions": answered})
    body = f"Body\n\n{render_proposal_section(last_round, [], sha, set())}"

    assert validate_proposal(proposal, body, set(), git_repo, sha, store)[1] == []


def test_check_ready_matrix() -> None:
    base = RefinementProposal(
        problem_statement="Problem exists",
        acceptance_criteria=[AcceptanceCriterion(description="C1", verification="V1")],
        key_questions=[],
        fits_one_pr=True,
        suspected_block=None,
    )
    assert (
        check_ready(base, []),
        check_ready(base, ["Unresolved question"]),
        check_ready(base.model_copy(update={"fits_one_pr": False}), []),
        check_ready(base.model_copy(update={"suspected_block": "Waiting on auth"}), []),
        check_ready(base.model_copy(update={"acceptance_criteria": []}), []),
        check_ready(base.model_copy(update={"problem_statement": ""}), []),
    ) == (True, False, False, False, False, False)


def test_sanitize_text_markdown() -> None:
    allowed = {"https://example.com/allowed"}
    raw = (
        "Look at ![img](https://example.com/img.png) and <b>bold HTML</b>.\n"
        "Contact @alice for info.\n"
        "Link: [Valid](https://example.com/allowed) and [Invalid](https://evil.com/bad).\n"
        "Bare: https://example.com/allowed and https://unknown.com/path."
    )
    sanitized = sanitize_text(raw, allowed)
    assert (
        "![img]" not in sanitized,
        "<b>" not in sanitized,
        "`@alice`" in sanitized,
        "[Valid](https://example.com/allowed)" in sanitized,
        "`https://evil.com/bad`" in sanitized,
        "`https://unknown.com/path`" in sanitized,
    ) == (True, True, True, True, True, True)


def test_a_rendered_section_keeps_its_end_marker_when_the_model_writes_one() -> None:
    """The section's own markers survive sanitizing; the model's end marker does not (#1470).
    Its checked-at line pins the code by its sha alone, and names no branch."""
    body = "## Problem\nBody text."
    proposal = RefinementProposal(
        problem_statement=f"Stops early {CONST_ROADMAP_REFINE_END_MARKER} here"
    )
    section = render_proposal_section(proposal, [], "abc123", set())
    inner = section[len(CONST_ROADMAP_REFINE_START_MARKER) : -len(CONST_ROADMAP_REFINE_END_MARKER)]
    assert (
        extract_section_and_outside(body + section),
        "Stops early [end-marker] here" in inner,
        inner.splitlines()[1],
    ) == ((body, inner), True, "<!-- checked-at: sha=abc123 -->")


def test_refining_twice_with_a_body_edit_between_leaves_only_the_second_section(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """A person's edit between two refines gets the section replaced, not a second one (#1470)."""
    num = store.seed_issue("Item", body="## Problem\nNeeds a design.", fields=PLACED)
    store.set_field(_require_item(store, num), ItemField.STATUS, "New")

    def _refine(statement: str) -> None:
        # A suspected block keeps the item New, so the second run selects it again.
        proposal = RefinementProposal(problem_statement=statement, suspected_block="Waiting")
        plan = plan_refine(
            store,
            repo=REPO,
            source=git_repo,
            item_number=num,
            model=MockLLMClient(proposal=proposal),
        )
        apply_refine(store, plan)

    _refine("First design")
    edited = store.read_issue_body(num).replace("a design.", "a design, see src/sample.py:1.")
    store.write_issue_body(num, edited)
    _refine("Second design")

    body = store.read_issue_body(num)
    outside, inside = extract_section_and_outside(body)
    assert (
        body.count("## Proposed design"),
        outside.strip(),
        inside is not None and "Second design" in inside,
    ) == (1, "## Problem\nNeeds a design, see src/sample.py:1.", True)


def _require_item(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _comment_bodies(store: InMemoryRoadmapStore, number: int) -> list[str]:
    """The body of each comment on issue `number`, oldest first."""
    return [comment.body for comment in store.comments_on(number)]


def test_selection_second_milestone_backlog_priorities_and_cap(store: InMemoryRoadmapStore) -> None:
    # The second open milestone
    n1 = store.seed_issue("Next critical", milestone=SECOND, fields=PLACED)
    n2 = store.seed_issue("Next low", milestone=SECOND, fields=PLACED)
    store.set_field(_require_item(store, n1), ItemField.STATUS, "New")
    store.set_field(_require_item(store, n1), ItemField.PRIORITY, CONST_ROADMAP_CRITICAL_PRIORITY)
    store.set_field(_require_item(store, n2), ItemField.STATUS, "New")
    store.set_field(_require_item(store, n2), ItemField.PRIORITY, "P3-Low")

    # Backlog items
    b1 = store.seed_issue("Backlog critical", fields=PLACED)
    b2 = store.seed_issue("Backlog ready", fields=PLACED)
    b3 = store.seed_issue("Backlog blocked", fields=PLACED)
    store.set_field(_require_item(store, b1), ItemField.STATUS, "New")
    store.set_field(_require_item(store, b1), ItemField.PRIORITY, CONST_ROADMAP_CRITICAL_PRIORITY)
    store.set_field(_require_item(store, b2), ItemField.STATUS, CONST_ROADMAP_STATUS_READY)
    store.set_field(_require_item(store, b3), ItemField.STATUS, "Blocked")

    selected, _skipped = select_candidates(store, limit=3)
    sel_nums = [it.number for it in selected]
    assert (
        sel_nums,
        b2 not in sel_nums,
        b3 not in sel_nums,
    ) == ([n1, n2, b1], True, True)


def test_an_unchanged_item_that_waits_on_a_body_edit_is_selected_once_its_body_changes(
    store: InMemoryRoadmapStore,
) -> None:
    """An item refine could not write a design for waits on a body edit alone: selection leaves
    it out, with that next step, until a person edits the body (#1758)."""
    num = store.seed_issue("Item", body="Initial content", fields=PLACED)
    item = _require_item(store, num)
    store.set_field(item, ItemField.STATUS, "New")
    outside, _ = extract_section_and_outside("Initial content")
    store.set_marks(
        item,
        {
            RefineRecordKey.BODY_HASH: hash_text(outside),
            RefineRecordKey.SECTION_HASH: None,
            RefineRecordKey.NEXT_STEP: "edit",
        },
    )

    selected_unchanged, waiting = select_candidates(store)
    store.as_actor("alice").write_issue_body(num, "Updated content by human")
    selected_changed, _ = select_candidates(store)
    assert (
        selected_unchanged,
        [(w.item.number, w.step, w.details) for w in waiting],
        [it.number for it in selected_changed],
    ) == ([], [(num, "edit", ())], [num])


def _seed_item(
    store: InMemoryRoadmapStore,
    status: str,
    priority: str,
    *,
    milestone: str | None = None,
    labels: tuple[str, ...] = (),
    refined: bool = False,
) -> int:
    """An open item on the board with `status` and `priority`; `refined` gives it the record a
    refine round leaves."""
    number = store.seed_issue(
        f"{status} {priority}",
        body=f"Body {priority}",
        milestone=milestone,
        labels=labels,
        fields=PLACED,
    )
    store.set_field(_require_item(store, number), ItemField.STATUS, status)
    store.set_field(_require_item(store, number), ItemField.PRIORITY, priority)
    if refined:
        record = {RefineRecordKey.BODY_HASH: "body", RefineRecordKey.SECTION_HASH: "section"}
        store.set_marks(_require_item(store, number), record)
    return number


def test_a_later_milestone_is_refined_once_the_second_one_is_ready(
    store: InMemoryRoadmapStore,
) -> None:
    """With the second open milestone all Ready, refine takes the third one's New items,
    highest priority first, up to its limit (#1515)."""
    store.seed_milestone(THIRD, due_on=date(2026, 11, 12))
    _seed_item(store, CONST_ROADMAP_STATUS_READY, "P1-High", milestone=SECOND, refined=True)
    later = [
        _seed_item(store, "New", priority, milestone=THIRD)
        for priority in ("P1-High", "P2-Medium", "P1-High", "P1-High")
    ]
    selected, _skipped = select_candidates(store)
    assert [it.number for it in selected] == [later[0], later[2], later[3]]


def test_a_critical_fix_in_the_first_milestone_goes_before_any_later_item(
    store: InMemoryRoadmapStore,
) -> None:
    """A New critical fix in the first open milestone is taken before a later milestone's item,
    even one of the same priority (#1515)."""
    planned = _seed_item(store, "New", CONST_ROADMAP_CRITICAL_PRIORITY, milestone=SECOND)
    fix = _seed_item(
        store, "New", CONST_ROADMAP_CRITICAL_PRIORITY, milestone=FIRST, labels=("type/bug",)
    )
    selected, _skipped = select_candidates(store)
    assert [it.number for it in selected] == [fix, planned]


def test_ready_items_refine_never_saw_are_taken_in_each_milestone_and_backlog_p0_p1(
    store: InMemoryRoadmapStore,
) -> None:
    """A Ready item refine holds no record of is taken like a New one in each open milestone and
    among the backlog's P0/P1 items; one refine already saw and a lower-priority backlog one are
    not (#1515)."""
    ready = CONST_ROADMAP_STATUS_READY
    first = _seed_item(store, ready, CONST_ROADMAP_CRITICAL_PRIORITY, milestone=FIRST)
    _seed_item(store, ready, "P1-High", milestone=SECOND, refined=True)
    planned = _seed_item(store, ready, "P2-Medium", milestone=SECOND)
    backlog = _seed_item(store, ready, "P1-High")
    _seed_item(store, ready, "P3-Low")
    selected, _skipped = select_candidates(store, limit=10)
    assert [it.number for it in selected] == [first, planned, backlog]


def test_a_ready_item_refine_finds_not_ready_goes_back_to_new_and_then_waits_on_a_person(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """Refine sets a Ready item it never saw back to New when its proposal is not ready, saying so
    in the one comment that asks a person about the suspected block, and the next round leaves
    it waiting on that person (#1515, #1758)."""
    number = _seed_item(store, CONST_ROADMAP_STATUS_READY, "P1-High", milestone=SECOND)
    blocked = RefinementProposal(
        problem_statement="Needs the owner's decision.",
        acceptance_criteria=[AcceptanceCriterion(description="C", verification="V")],
        suspected_block="Waiting on the owner",
    )
    llm = MockLLMClient(proposal=blocked)
    apply_refine(store, plan_refine(store, repo=REPO, source=git_repo, model=llm))
    again = plan_refine(store, repo=REPO, source=git_repo, model=llm)
    sha = inspect_checkout(git_repo, REPO)[:12]
    assert (
        _require_item(store, number).status,
        _comment_bodies(store, number),
        again.refined_items,
        [(w.item.number, w.step) for w in again.waiting_items],
    ) == (
        "New",
        [
            f"{constants.CONST_ROADMAP_REFINE_COMMENT_MARKER}\nStatus set back to New at {sha}. "
            f"Refine cannot set this item to Ready at {sha} until a person answers the questions "
            "below. Reply in a comment or edit the body, and the next refine round looks at the "
            "item again.\n\n- Waiting on the owner"
        ],
        [],
        [(number, "person")],
    )


def test_an_item_refine_would_skip_for_a_person_edit_takes_no_place(
    store: InMemoryRoadmapStore,
) -> None:
    """A New backlog P1 whose section's hash differs from the record, as an item holding a section
    from before #1470 has once refine adds its own, waits on a body edit at selection, and the
    New item behind it gets the round's one place (#1515, #1758)."""
    stuck = _seed_item(store, "New", "P1-High")
    store.write_issue_body(
        stuck,
        f"Body\n\n{CONST_ROADMAP_REFINE_START_MARKER}\n## Proposed design\nOld.\n[end-marker]\n\n"
        f"{CONST_ROADMAP_REFINE_START_MARKER}\n## Proposed design\nNew.\n"
        f"{CONST_ROADMAP_REFINE_END_MARKER}",
    )
    store.set_marks(
        _require_item(store, stuck),
        {
            RefineRecordKey.BODY_HASH: "body",
            RefineRecordKey.SECTION_HASH: hash_text("## Proposed design\nNew."),
        },
    )
    fresh = _seed_item(store, "New", "P1-High")
    selected, waiting = select_candidates(store, limit=1)
    assert (
        [it.number for it in selected],
        [(w.item.number, w.step, w.details) for w in waiting],
    ) == (
        [fresh],
        [(stuck, "edit", ("the section's hash differs from the one refine last recorded",))],
    )


def test_person_edits_guards(store: InMemoryRoadmapStore) -> None:
    num = store.seed_issue("Item", body="Body text", fields=PLACED)
    item = _require_item(store, num)

    # 1. Section exists but no recorded hash
    body_with_untracked_section = (
        f"Body\n{CONST_ROADMAP_REFINE_START_MARKER}\nSection\n{CONST_ROADMAP_REFINE_END_MARKER}"
    )
    store.write_issue_body(num, body_with_untracked_section)
    err1 = check_person_edits(item, body_with_untracked_section)
    assert err1 == "the body holds a section refine has no record of"

    # 2. Section hash differs from recorded
    store.set_marks(item, {RefineRecordKey.SECTION_HASH: "different-hash"})
    item = _require_item(store, num)
    err2 = check_person_edits(item, body_with_untracked_section)
    assert err2 == "the section's hash differs from the one refine last recorded"


def test_too_big_needs_split(git_repo: Path, store: InMemoryRoadmapStore) -> None:
    """A proposal that does not fit one pull request leaves the item New and records it as
    needing a split; no job moves it out of its milestone."""
    num = store.seed_issue("Heavy task", body="Big work", milestone=FIRST, fields=PLACED)
    item = _require_item(store, num)
    store.set_field(item, ItemField.STATUS, "New")
    store.set_field(item, ItemField.PRIORITY, "P1-High")

    proposal = RefinementProposal(
        problem_statement="Too big",
        acceptance_criteria=[AcceptanceCriterion(description="C", verification="V")],
        key_questions=[],
        fits_one_pr=False,
        split_offs=["Part 1", "Part 2"],
    )
    llm = MockLLMClient(proposal=proposal)

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=num, model=llm)
    applied = apply_refine(store, plan)
    updated = store.item(num)
    assert updated is not None
    assert (
        updated.status,
        updated.milestone,
        updated.job_record.get(RefineRecordKey.NEEDS_SPLIT),
        applied.split_count == 1,
    ) == ("New", FIRST, "true", True)


def test_size_limit_guard(git_repo: Path, store: InMemoryRoadmapStore) -> None:
    num = store.seed_issue("Item", body="Initial", fields=PLACED)
    item = _require_item(store, num)
    store.set_field(item, ItemField.STATUS, "New")

    # Proposal with massive text pushing past 65,536 chars
    huge_text = "A" * 70000
    huge_proposal = RefinementProposal(
        problem_statement=huge_text,
        acceptance_criteria=[AcceptanceCriterion(description="C", verification="V")],
    )
    llm = MockLLMClient(proposal=huge_proposal)

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=num, model=llm)
    refined = plan.refined_items[0]
    assert (
        plan.has_writes,
        refined.skip_reason is not None and "exceed" in refined.skip_reason,
        refined.record_only,
    ) == (True, True, True)


def test_cli_refine_dry_run_and_confirm(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    num = store.seed_issue("Feature to refine", body="Need refinement", fields=PLACED)
    item = _require_item(store, num)
    store.set_field(item, ItemField.STATUS, "New")

    mock_llm = MockLLMClient()
    model_fake.answer(mock_llm.proposal)
    runner = CliRunner()
    with patch("devops_cli.commands.roadmap._open_store", return_value=(REPO, store)):
        # Dry run
        res_dry = runner.invoke(
            roadmap_app,
            ["refine", "--repo", REPO, "--source", str(git_repo), "--item", str(num), "--dry-run"],
        )
        assert (res_dry.exit_code, store.read_issue_body(num)) == (0, "Need refinement")

        # Confirm
        res_confirm = runner.invoke(
            roadmap_app,
            ["refine", "--repo", REPO, "--source", str(git_repo), "--item", str(num), "--confirm"],
        )
        updated = _require_item(store, num)
        assert (
            res_confirm.exit_code,
            CONST_ROADMAP_REFINE_START_MARKER in store.read_issue_body(num),
            updated.status,
        ) == (0, True, CONST_ROADMAP_STATUS_READY)


def test_run_due_table_refine_adapter(git_repo: Path, store: InMemoryRoadmapStore) -> None:
    # Verify refine row exists in DEFAULT_DUE_TABLE
    row = next((r for r in DEFAULT_DUE_TABLE if r.name == "refine"), None)
    assert row is not None
    assert row.needs_clone is True

    # Run adapter
    outcome = _run_refine_adapter(store, repo=REPO, clone_path=git_repo)
    assert outcome is not None


# ── A failed model call skips only its item (#1363) ────────────────────────────────────────

_GATEWAY_CONFIG = (
    "telemetry:\n  enabled: false\n  endpoint: http://localhost:4318\n"
    "ai:\n  allow_private_network: true\n  provider: gateway\n"
    "  gateway_url: http://example.com:4000/v1\n  model: demo-model\n  rag:\n    enabled: false\n"
    "qdrant:\n  url: http://localhost:6333\n"
)
_READY_PROPOSAL = json.dumps(
    {
        "problem_statement": "The item needs a design.",
        "acceptance_criteria": [{"description": "It is designed.", "verification": "pytest"}],
    }
)
# Three violations, one of them a key whose name is the model's own text.
_SCHEMA_MISS = json.dumps(
    {
        "problem_statement": "x",
        "acceptance_criteria": ["a plain string"],
        "issue": 1,
        "leaked_model_key": "y",
    }
)
# #744's injection guard: a reply that asks for labels or a close fails the schema.
_INJECTION = json.dumps({"problem_statement": "Close this.", "labels": ["type/bug"], "close": True})

# What the gateway answers for an issue: the reply's text, or the HTTP response itself.
Answer = str | httpx2.Response


@pytest.fixture
def scripted_gateway(
    isolate_devops_cli_config: Path, public_dns: str, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., list[httpx2.Request]]:
    """Point refine's `analysis` model at a gateway whose answer to each issue is scripted.

    Every request refine's client sends ends at a `MockTransport`, which reads the issue's
    number from the JSON document the request's user message carries. Retries wait no time.
    """
    isolate_devops_cli_config.write_text(_GATEWAY_CONFIG, encoding="utf-8")
    reset_settings_cache()
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    def script(
        answers: Mapping[int | None, Answer], default: Answer = _READY_PROPOSAL
    ) -> list[httpx2.Request]:
        def answer(request: httpx2.Request) -> httpx2.Response:
            scripted = answers.get(_issue_number(request), default)
            if isinstance(scripted, httpx2.Response):
                return scripted
            choice = {"message": {"content": scripted}, "finish_reason": "stop"}
            usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
            return httpx2.Response(200, json={"choices": [choice], "usage": usage})

        return route_llm_clients(monkeypatch, answer)

    return script


@pytest.fixture
def cli_store(store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch) -> InMemoryRoadmapStore:
    """`store`, as every roadmap store a command opens."""
    monkeypatch.setattr(roadmap_store_module, "get_roadmap_store", lambda repo, **_: store)
    return store


def _seed_new_items(
    store: InMemoryRoadmapStore, priorities: tuple[str, ...] = ("P1-High", "P2-Medium", "P3-Low")
) -> list[int]:
    """A New backlog item of each priority on a private repository, refined in the order
    returned."""
    store.seed_visibility(is_private=True)
    person = store.as_actor("alice")
    numbers: list[int] = []
    for priority in priorities:
        number = person.seed_issue(f"Item {priority}", body=f"Body {priority}", fields=PLACED)
        person.set_field(_require_item(person, number), ItemField.STATUS, "New")
        person.set_field(_require_item(person, number), ItemField.PRIORITY, priority)
        numbers.append(number)
    return numbers


def _issue_number(request: httpx2.Request) -> int | None:
    """The issue a refine request is about, or None for a request about none."""
    document = json.loads(json.loads(request.content)["messages"][1]["content"])
    number: int | None = document.get("number")
    return number


def _requests_per_item(sent: list[httpx2.Request]) -> dict[int | None, int]:
    return dict(Counter(_issue_number(request) for request in sent))


def _bodies_written(store: InMemoryRoadmapStore) -> list[int]:
    """The issues whose body a job wrote."""
    return sorted(
        {
            write.number
            for write in store.job_writes()
            if write.operation == "write_issue_body" and write.number is not None
        }
    )


def test_a_proposal_that_never_fits_the_schema_skips_only_its_item(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify candidate 1's StructuredOutputValidationError skips it alone: 2 and 3 are refined
    and written, and 1 is reported with the error class and violation count, no model text."""
    first, second, third = _seed_new_items(store)
    sent = scripted_gateway({first: _SCHEMA_MISS})

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine"):
        plan = plan_refine(store, repo=REPO, source=git_repo)
    apply_refine(store, plan)

    rendered = render_refine_plan(plan)
    assert (
        [(failed.item.number, failed.error, failed.violations) for failed in plan.failed_items],
        [refined.item.number for refined in plan.refined_items],
        _requests_per_item(sent),
        _bodies_written(store),
        (store.read_issue_body(first), _require_item(store, first).status),
        "StructuredOutputValidationError, 3 schema violation(s)" in rendered,
        [
            record.getMessage()
            for record in caplog.records
            if record.name == "devops_cli.roadmap.refine"
        ],
        "leaked_model_key" in rendered + caplog.text,
    ) == (
        [(first, "StructuredOutputValidationError", 3)],
        [second, third],
        {first: 3, second: 1, third: 1},
        [second, third],
        ("Body P1-High", "New"),
        True,
        [
            f"Refine skipped #{first}: its model call failed "
            "(StructuredOutputValidationError, 3 schema violation(s))."
        ],
        False,
    )


def test_a_reply_asking_for_labels_or_a_close_is_refused_and_writes_nothing(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """Verify #744's injection guard: a reply carrying `labels` and `close` fails the schema,
    its item is skipped with nothing written, and the other candidates still refine."""
    first, second, third = _seed_new_items(store)
    scripted_gateway({second: _INJECTION})

    plan = plan_refine(store, repo=REPO, source=git_repo)
    apply_refine(store, plan)

    assert (
        [(failed.item.number, failed.error, failed.violations) for failed in plan.failed_items],
        _bodies_written(store),
        (store.read_issue_body(second), _require_item(store, second).status),
    ) == (
        [(second, "StructuredOutputValidationError", 2)],
        [first, third],
        ("Body P2-Medium", "New"),
    )


def test_a_gateway_timeout_on_candidate_2_still_applies_candidate_1(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """Verify an AIClientError on candidate 2 skips it, and candidate 1's section and Ready
    Status are still applied."""
    first, second, third = _seed_new_items(store)
    sent = scripted_gateway({second: httpx2.Response(504, text="Gateway Timeout")})

    plan = plan_refine(store, repo=REPO, source=git_repo)
    apply_refine(store, plan)

    assert (
        [(failed.item.number, failed.error, failed.violations) for failed in plan.failed_items],
        _requests_per_item(sent),
        CONST_ROADMAP_REFINE_START_MARKER in store.read_issue_body(first),
        _require_item(store, first).status,
        _bodies_written(store),
    ) == (
        [(second, "AIClientError", 0)],
        {first: 1, second: 1, third: 1},
        True,
        CONST_ROADMAP_STATUS_READY,
        [first, third],
    )


def test_rejected_credentials_still_stop_the_job_at_the_first_item(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """Verify an AICredentialsError stops refine at its first item, before any other call."""
    first, _second, _third = _seed_new_items(store)
    sent = scripted_gateway({}, default=httpx2.Response(401, text="Unauthorized"))

    with pytest.raises(AICredentialsError):
        plan_refine(store, repo=REPO, source=git_repo)

    assert (_requests_per_item(sent), _bodies_written(store)) == ({first: 1}, [])


@pytest.mark.parametrize("mode", ["--confirm", None])
def test_the_cli_exits_1_after_reporting_a_failed_item(
    git_repo: Path,
    cli_store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    mode: str | None,
) -> None:
    """Verify `devops roadmap refine` prints its plan, writes the other items under --confirm,
    and exits 1 when an item's model call failed, in a preview too."""
    first, second, third = _seed_new_items(cli_store)
    scripted_gateway({first: _SCHEMA_MISS})

    args = ["refine", "--repo", REPO, "--source", str(git_repo), *([mode] if mode else [])]
    result = CliRunner().invoke(roadmap_app, args)

    assert (
        result.exit_code,
        f"#{first} Item P1-High: skipped" in result.output,
        "leaked_model_key" in result.output,
        _bodies_written(cli_store),
    ) == (1, True, False, [second, third] if mode == "--confirm" else [])


@pytest.mark.parametrize(
    ("failing_answer", "named"),
    [
        pytest.param(
            lambda: _SCHEMA_MISS,
            "StructuredOutputValidationError, 3 schema violation(s)",
            id="schema-miss",
        ),
        pytest.param(
            lambda: httpx2.Response(504, text="Gateway Timeout"),
            "AIClientError, 0 schema violation(s)",
            id="gateway-504",
        ),
    ],
)
def test_a_failed_item_fails_the_refine_job_of_a_run_without_its_model_text(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    tmp_path: Path,
    failing_answer: Callable[[], Answer],
    named: str,
) -> None:
    """Verify run_due_jobs records `refine` as failed once the other items are written, whether
    the item's reply never fit the schema or the gateway timed out, and the raised error
    names the error class and holds none of the model's reply."""
    first, second, third = _seed_new_items(store)
    scripted_gateway({first: failing_answer()})
    table = build_stub_table(
        {"refine": lambda **kwargs: _run_refine_adapter(**(kwargs | {"clone_path": git_repo}))}
    )

    with pytest.raises(RoadmapRunError) as raised:
        run_due_jobs(
            REPO,
            store,
            batch={("webhook", "milestones", "opened"): 1},
            table=table,
            data_dir=tmp_path,
        )

    formatted = "".join(traceback.format_exception(raised.value))
    assert (
        raised.value.failed_jobs,
        _bodies_written(store),
        named in formatted,
        "leaked_model_key" in formatted,
        "During handling" in formatted,
    ) == (("refine",), [second, third], True, False, False)


# ── The hourly round: no Ready count stops it, and no model call when nothing changed ──

# A proposal refine leaves New: it does not fit one pull request.
_SPLIT_PROPOSAL = json.dumps(
    {
        "problem_statement": "Two changes in one item.",
        "acceptance_criteria": [{"description": "Both land.", "verification": "pytest"}],
        "fits_one_pr": False,
        "split_offs": ["The first change.", "The second change."],
    }
)


def test_a_backlog_full_of_ready_items_stops_refine_from_no_new_item_up_to_the_limit(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """Twelve Ready items in the backlog do not stop a round. It asks the model about the New
    item of an open milestone first, then about the backlog's New items by priority, and stops
    at `--limit` alone. The board shows the Ready count to the person who plans (#2004)."""
    store.seed_visibility(is_private=True)
    for _ in range(12):
        _seed_item(store, CONST_ROADMAP_STATUS_READY, "P2-Medium", refined=True)
    planned = _seed_item(store, "New", "P3-Low", milestone=FIRST)
    backlog = [
        _seed_item(store, "New", priority)
        for priority in ("P3-Low", "P2-Medium", "P1-High", "P3-Low")
    ]
    model_fake.answer(_SPLIT_PROPOSAL)

    plan_refine(store, repo=REPO, source=git_repo, limit=4)

    assert [json.loads(call.prompt)["number"] for call in model_fake.calls] == [
        planned,
        backlog[2],
        backlog[1],
        backlog[0],
    ]


def test_a_round_after_refine_left_items_new_leaves_them_waiting_reading_no_body_or_model(
    git_repo: Path,
    store: BodyReadCountingStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """Items a real round refined and left New with a split proposed still wait on that split in
    the next round, which reads no issue body, selects nothing and sends the gateway no request,
    with a Ready item that has a recorded section among them (#1515, #1539, #1758)."""
    numbers = _seed_new_items(store)
    _seed_item(store, CONST_ROADMAP_STATUS_READY, "P2-Medium", milestone=SECOND, refined=True)
    sent = scripted_gateway({}, default=_SPLIT_PROPOSAL)
    apply_refine(store, plan_refine(store, repo=REPO, source=git_repo))
    first_round = len(sent)
    store.body_reads.clear()
    again = plan_refine(store, repo=REPO, source=git_repo)
    assert (
        first_round,
        len(sent),
        store.body_reads,
        again.refined_items,
        [(w.item.number, w.step) for w in again.waiting_items],
        [_require_item(store, number).status for number in numbers],
    ) == (3, 3, [], [], [(number, "split") for number in numbers], ["New"] * 3)


def test_editing_one_settled_items_body_selects_only_it_with_one_body_read_and_one_model_call(
    git_repo: Path,
    store: BodyReadCountingStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """A person's edit outside the refine section unsettles that item alone; the planning round
    that follows reads its body once, sends one request, and writes nothing (#1539)."""
    first, second, third = _seed_new_items(store)
    sent = scripted_gateway({}, default=_SPLIT_PROPOSAL)
    apply_refine(store, plan_refine(store, repo=REPO, source=git_repo))
    store.as_actor("alice").write_issue_body(
        second, store.read_issue_body(second) + "\n\nAnd one more requirement."
    )
    store.body_reads.clear()
    writes_before, requests_before = store.job_writes(), len(sent)

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [refined.item.number for refined in again.refined_items],
        [(w.item.number, w.step) for w in again.waiting_items],
        store.body_reads,
        len(sent) - requests_before,
        store.job_writes() == writes_before,
    ) == ([second], [(first, "split"), (third, "split")], [second], 1, True)


def _refine_round(store: InMemoryRoadmapStore, source: Path) -> RefinePlan:
    """One round of `devops roadmap refine --confirm`, planned and then applied."""
    plan = plan_refine(store, repo=REPO, source=source)
    apply_refine(store, plan)
    return plan


def _writes_to(store: InMemoryRoadmapStore, number: int) -> list[JobWrite]:
    """What jobs wrote to issue `number`, oldest first."""
    return [write for write in store.job_writes() if write.number == number]


def _refine_record(store: InMemoryRoadmapStore, number: int) -> tuple[str | None, ...]:
    """The body hash, the section hash and the failed body hash in issue `number`'s job record."""
    record = _require_item(store, number).job_record
    return tuple(
        record.get(key)
        for key in (
            RefineRecordKey.BODY_HASH,
            RefineRecordKey.SECTION_HASH,
            RefineRecordKey.FAILED_BODY_HASH,
        )
    )


_FIRST_BODY_HASH = hash_text("Body P1-High")
# A proposal whose section alone would take the body past the size the guard allows.
_TOO_BIG_PROPOSAL = json.dumps(
    {
        "problem_statement": "A" * CONST_ROADMAP_REFINE_MAX_BODY_CHARS,
        "acceptance_criteria": [{"description": "It is designed.", "verification": "pytest"}],
    }
)


def test_an_item_whose_refined_body_is_too_big_is_selected_once_and_its_body_never_written(
    git_repo: Path,
    store: BodyReadCountingStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """The size guard records the body it saw and writes none: the next round finds the item
    waiting on a body edit and sends no request, whatever a person comments, until a person
    edits it (#1526, #1539, #1758)."""
    first, *_ = _seed_new_items(store)
    sent = scripted_gateway({first: _TOO_BIG_PROPOSAL})

    first_round = _refine_round(store, git_repo)
    after_first = (len(sent), store.read_issue_body(first), _writes_to(store, first))
    store.as_actor("alice").comment(first, "Please try again.")
    second_round = plan_refine(store, repo=REPO, source=git_repo)
    after_second = (
        len(sent),
        second_round.refined_items,
        [(w.item.number, w.step) for w in second_round.waiting_items],
    )
    store.as_actor("alice").write_issue_body(first, "Body P1-High, edited")
    third_round = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        first_round.has_writes,
        after_first,
        after_second,
        [refined.item.number for refined in third_round.refined_items],
    ) == (
        True,
        (
            3,
            "Body P1-High",
            [
                JobWrite("set_mark", first, RefineRecordKey.BODY_HASH.value, _FIRST_BODY_HASH),
                JobWrite("set_mark", first, RefineRecordKey.SECTION_HASH.value, None),
                JobWrite("set_mark", first, RefineRecordKey.NEXT_STEP.value, "edit"),
            ],
        ),
        (3, [], [(first, "edit")]),
        [first],
    )


def test_two_replies_that_never_validate_on_the_same_body_settle_the_item(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """A reply that never fits the schema is the item's doing: the first failure records the
    body it saw and settles nothing, the second on the same body settles the item to wait on a
    body edit, and a person's edit unsettles it (#1526, #1539, #1758)."""
    first, *_ = _seed_new_items(store)
    sent = scripted_gateway({first: _SCHEMA_MISS})

    _refine_round(store, git_repo)
    after_first = (len(sent), _refine_record(store, first))
    _refine_round(store, git_repo)
    after_second = (len(sent), _refine_record(store, first))
    third_round = _refine_round(store, git_repo)
    after_third = (
        len(sent),
        third_round.failed_items,
        [(w.item.number, w.step) for w in third_round.waiting_items],
    )
    store.as_actor("alice").write_issue_body(first, "Body P1-High, edited")
    edited = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        after_first,
        after_second,
        after_third,
        [failure.item.number for failure in edited.failed_items],
    ) == (
        (5, (None, None, _FIRST_BODY_HASH)),
        (8, (_FIRST_BODY_HASH, None, None)),
        (8, [], [(first, "edit")]),
        [first],
    )


def test_a_failure_followed_by_a_success_refines_the_item_and_clears_the_failure(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """One reply that never fits the schema does not stop the item: the next round refines it,
    and its record no longer holds the failure (#1526, #1539)."""
    first, *_ = _seed_new_items(store)
    answers: dict[int | None, Answer] = {first: _SCHEMA_MISS}
    scripted_gateway(answers)

    _refine_round(store, git_repo)
    failed = _refine_record(store, first)
    del answers[first]
    _refine_round(store, git_repo)

    item = _require_item(store, first)
    body_hash, _, failed_body_hash = _refine_record(store, first)
    assert (
        failed,
        (body_hash, failed_body_hash),
        CONST_ROADMAP_REFINE_START_MARKER in store.read_issue_body(first),
        item.status,
    ) == (
        (None, None, _FIRST_BODY_HASH),
        (_FIRST_BODY_HASH, None),
        True,
        CONST_ROADMAP_STATUS_READY,
    )


def test_a_gateway_failure_records_nothing_and_the_next_round_selects_the_item_again(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """A timeout says nothing about the item, so however often it repeats, no record is written
    and the item stays due (#1539)."""
    first, second, third = _seed_new_items(store)
    sent = scripted_gateway({first: httpx2.Response(504, text="Gateway Timeout")})

    rounds = [_refine_round(store, git_repo), _refine_round(store, git_repo)]

    assert (
        [[failure.item.number for failure in plan.failed_items] for plan in rounds],
        _requests_per_item(sent),
        _writes_to(store, first),
        _refine_record(store, first),
    ) == ([[first], [first]], {first: 2, second: 1, third: 1}, [], (None, None, None))


# Replies that leave an item too big to refine, or failing on its own text.
_TROUBLE_REPLIES = pytest.mark.parametrize(
    "reply", [_TOO_BIG_PROPOSAL, _SCHEMA_MISS], ids=["too-big", "schema-miss"]
)


@pytest.mark.parametrize(
    ("reply", "marks", "exit_code"),
    [
        pytest.param(
            _TOO_BIG_PROPOSAL,
            [
                (RefineRecordKey.BODY_HASH.value, _FIRST_BODY_HASH),
                (RefineRecordKey.SECTION_HASH.value, None),
                ("refine.next_step", "edit"),
            ],
            0,
            id="too-big",
        ),
        pytest.param(
            _SCHEMA_MISS,
            [(RefineRecordKey.FAILED_BODY_HASH.value, _FIRST_BODY_HASH)],
            1,
            id="schema-miss",
        ),
    ],
)
def test_a_round_whose_only_item_is_too_big_or_fails_still_records_it_through_the_cli(
    git_repo: Path,
    cli_store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    reply: str,
    marks: list[tuple[str, str | None]],
    exit_code: int,
) -> None:
    """With nothing else to write, `devops roadmap refine --confirm` still applies the plan:
    the item's record is written and its body is not (#1539)."""
    (first,) = _seed_new_items(cli_store, ("P1-High",))
    scripted_gateway({first: reply})

    args = ["refine", "--repo", REPO, "--source", str(git_repo), "--confirm"]
    result = CliRunner().invoke(roadmap_app, args)

    assert (result.exit_code, _writes_to(cli_store, first)) == (
        exit_code,
        [JobWrite("set_mark", first, key, value) for key, value in marks],
    )


def test_the_runs_refine_job_records_an_item_too_big_to_refine(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """The refine job of `devops roadmap run` applies a plan whose only write is the record of
    an item too big to refine (#1539)."""
    (first,) = _seed_new_items(store, ("P1-High",))
    scripted_gateway({first: _TOO_BIG_PROPOSAL})

    _run_refine_adapter(store, repo=REPO, clone_path=git_repo)

    assert _writes_to(store, first) == [
        JobWrite("set_mark", first, RefineRecordKey.BODY_HASH.value, _FIRST_BODY_HASH),
        JobWrite("set_mark", first, RefineRecordKey.SECTION_HASH.value, None),
        JobWrite("set_mark", first, RefineRecordKey.NEXT_STEP.value, "edit"),
    ]


@_TROUBLE_REPLIES
def test_planning_a_round_writes_no_body_and_no_record_for_an_item_too_big_or_failing(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    reply: str,
) -> None:
    """`--plan` writes nothing, though the plan holds a record to write (#1539)."""
    (first,) = _seed_new_items(store, ("P1-High",))
    scripted_gateway({first: reply})

    plan = plan_refine(store, repo=REPO, source=git_repo)

    assert (plan.has_writes, _writes_to(store, first), store.read_issue_body(first)) == (
        True,
        [],
        "Body P1-High",
    )


@_TROUBLE_REPLIES
def test_a_body_edited_between_the_plan_and_the_apply_is_recorded_as_neither_too_big_nor_failed(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    caplog: pytest.LogCaptureFixture,
    reply: str,
) -> None:
    """The record is of the body the model saw: a body a person changed since is left unrecorded,
    with the warning every skipped write has (#1539)."""
    (first,) = _seed_new_items(store, ("P1-High",))
    scripted_gateway({first: reply})
    plan = plan_refine(store, repo=REPO, source=git_repo)
    store.as_actor("alice").write_issue_body(first, "Body P1-High, edited")
    caplog.clear()

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine"):
        apply_refine(store, plan)

    assert (_writes_to(store, first), caplog.messages) == (
        [],
        [f"Skipping #{first}: the body changed between the read and the write."],
    )


@pytest.mark.parametrize(
    ("error", "recorded"),
    [
        pytest.param(
            StructuredOutputValidationError("never valid", violations=2), True, id="schema"
        ),
        pytest.param(ReplyRejectedError("refused", reply="x"), True, id="rejected"),
        pytest.param(AIClientError("timed out"), False, id="transport"),
    ],
)
def test_only_a_failure_the_items_own_text_caused_is_recorded(
    git_repo: Path, store: InMemoryRoadmapStore, error: AIClientError, recorded: bool
) -> None:
    """A reply the model gave about the item that never validated or was refused is recorded; a
    failure that says nothing about the item, such as a timeout, is not (#1539)."""
    person = store.as_actor("alice")
    number = person.seed_issue("Item", body="Body", fields=PLACED)
    person.set_field(_require_item(store, number), ItemField.STATUS, "New")

    plan = plan_refine(
        store, repo=REPO, source=git_repo, item_number=number, model=MockLLMClient(fail_with=error)
    )
    apply_refine(store, plan)

    assert (plan.has_writes, _writes_to(store, number)) == (
        recorded,
        [JobWrite("set_mark", number, RefineRecordKey.FAILED_BODY_HASH.value, hash_text("Body"))]
        if recorded
        else [],
    )


def test_refine_raises_its_own_error_naming_each_failed_item() -> None:
    """Verify RoadmapRefineError carries the failed items' numbers and its error code."""
    error = RoadmapRefineError("refine failed", failed_items=[3, 5])
    assert (error.failed_items, error.error_code, error.exit_code) == (
        (3, 5),
        "ROADMAP_REFINE_FAILED",
        1,
    )


def test_refines_prompts_load_and_the_reply_prompt_names_every_field() -> None:
    """Verify the step prompts load, and the reply prompt that both steps send names every key
    the schema allows, at the top level and in a criterion, a key question and an option."""
    steps = [
        load_task_prompt(name)
        for name in ("roadmap_refine_proposal.md", "roadmap_refine_investigation.md")
    ]
    reply = load_task_prompt("roadmap_refine_reply.md")
    keys = [
        *RefinementProposal.model_fields,
        *AcceptanceCriterion.model_fields,
        *QuestionAnswer.model_fields,
        *DesignOption.model_fields,
    ]
    assert (all(steps), [key for key in keys if f"`{key}`" not in reply]) == (True, [])


# ── Each item refine cannot set Ready gets a next step (#1758) ────────────────────────────

_READY = RefinementProposal(
    problem_statement="The item needs a design.",
    acceptance_criteria=[AcceptanceCriterion(description="It is designed.", verification="pytest")],
)
_QUESTION = _READY.model_copy(
    update={
        "key_questions": [
            QuestionAnswer(question="Which store holds the record?", answer="?", kind="fact")
        ]
    }
)
_SPLIT = _READY.model_copy(
    update={"fits_one_pr": False, "split_offs": ["The first change.", "The second change."]}
)
_OPEN_QUESTION = "Which store holds the record? (missing verified source)"


def _blocked_by(blocker: int) -> RefinementProposal:
    """A proposal that waits on the open item `blocker`."""
    return _READY.model_copy(
        update={"suspected_block": f"Waits on #{blocker}.", "dependencies": [blocker]}
    )


def _is_about(number: int, prompt: str) -> bool:
    """Whether a proposal request is about issue `number`."""
    found: object = json.loads(prompt).get("number")
    return found == number


def _answer_each(model_fake: ModelFake, proposals: Mapping[int, RefinementProposal]) -> None:
    """Answer the proposal request about each issue with its proposal."""
    for number, proposal in proposals.items():
        model_fake.route(partial(_is_about, number), proposal)


def _replies_sent(model_fake: ModelFake) -> list[str]:
    """The replies the last proposal request carried."""
    replies: list[str] = json.loads(model_fake.calls[-1].prompt)["replies"]
    return replies


def _seed_waiting_items(store: InMemoryRoadmapStore, model_fake: ModelFake) -> tuple[int, ...]:
    """On a private repository, an item In Progress, then three New backlog P1s whose proposals
    ask a question, need a split and wait on the first item; returned in that order."""
    store.seed_visibility(is_private=True)
    blocker = _seed_item(store, "In Progress", "P1-High")
    asked, split, blocked = (_seed_item(store, "New", "P1-High") for _ in range(3))
    _answer_each(model_fake, {asked: _QUESTION, split: _SPLIT, blocked: _blocked_by(blocker)})
    return blocker, asked, split, blocked


def test_each_item_refine_leaves_new_waits_on_its_next_step_with_no_model_call(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """An item refine leaves New gets a next step, not a skip as unchanged: its open question
    goes to a person, its split goes to a person, or the open item it depends on blocks it. The
    next round leaves each one waiting on that step and calls no model (#1758)."""
    blocker, asked, split, blocked = _seed_waiting_items(store, model_fake)

    first = _refine_round(store, git_repo)
    calls = model_fake.call_count
    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(r.item.number, r.next_step, r.step_details) for r in first.refined_items],
        [(w.item.number, w.step, w.details) for w in again.waiting_items],
        again.refined_items,
        model_fake.call_count - calls,
    ) == (
        [
            (asked, "person", (_OPEN_QUESTION,)),
            (split, "split", ("The first change.", "The second change.")),
            (blocked, "blocked", (f"#{blocker}",)),
        ],
        [(asked, "person", ()), (split, "split", ()), (blocked, "blocked", (f"#{blocker}",))],
        [],
        0,
    )


def test_an_item_refine_cannot_ready_gets_one_comment_and_a_record_of_its_next_step(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """Refine posts one comment that carries its marker and gives the item's next step: the
    question, the proposed split for a person to make, or the open items it waits on. The job
    record keeps the step, the split and the blockers (#1758)."""
    blocker, asked, split, blocked = _seed_waiting_items(store, model_fake)

    _refine_round(store, git_repo)

    sha = inspect_checkout(git_repo, REPO)[:12]
    marker = constants.CONST_ROADMAP_REFINE_COMMENT_MARKER
    record_keys = ("refine.next_step", "refine.needs_split", "refine.blocked_by")
    assert (
        {number: _comment_bodies(store, number) for number in (asked, split, blocked)},
        {
            number: tuple(
                _require_item(store, number).job_record.get(RefineRecordKey(key))
                for key in record_keys
            )
            for number in (asked, split, blocked)
        },
    ) == (
        {
            asked: [
                f"{marker}\nRefine cannot set this item to Ready at {sha} until a person "
                "answers the questions below. Reply in a comment or edit the body, and the next "
                f"refine round looks at the item again.\n\n- {_OPEN_QUESTION}"
            ],
            split: [
                f"{marker}\nThe proposal at {sha} needs splitting into 2 items. A person splits "
                "the item into the items below, or replies in a comment or edits the body to "
                "keep one item, and the next refine round looks at the item again.\n\n"
                "1. The first change.\n2. The second change."
            ],
            blocked: [
                f"{marker}\nRefine cannot set this item to Ready at {sha} while the items below "
                "stay open. The next refine round looks at the item again when they close, or "
                "when a person replies in a comment or edits the body.\n\n"
                f"- #{blocker}"
            ],
        },
        {
            asked: ("person", "false", None),
            split: ("split", "true", None),
            blocked: ("blocked", "false", str(blocker)),
        },
    )


def test_the_next_step_comment_holds_the_models_text_sanitized_and_one_line_for_each_point(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The model's split reaches the comment as the section shows it: no HTML, every handle in
    a code span so no one is pinged, and each point on its own line (#1758)."""
    store.seed_visibility(is_private=True)
    number = _seed_item(store, "New", "P1-High")
    split_offs = ["Ask @owner <b>now</b>\n\n## Then this", "The second change."]
    model_fake.answer(_SPLIT.model_copy(update={"split_offs": split_offs}))

    _refine_round(store, git_repo)

    assert [comment.splitlines()[-2:] for comment in _comment_bodies(store, number)] == [
        ["1. Ask `@owner` now ## Then this", "2. The second change."]
    ]


def test_a_persons_reply_makes_an_item_that_waits_on_them_eligible_and_reaches_the_model(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A comment after refine's own makes the item eligible again, though its body is unchanged,
    and the model reads the reply; the first round, with no comment, sent none (#1758)."""
    store.seed_visibility(is_private=True)
    asked = _seed_item(store, "New", "P1-High")
    # The first round's proposal and its investigation (#2398) both leave the question open.
    model_fake.answer(_QUESTION, _QUESTION, _READY)
    _refine_round(store, git_repo)
    first_replies = _replies_sent(model_fake)

    store.as_actor("alice").comment(asked, "The job record holds it.")
    again = _refine_round(store, git_repo)

    assert (
        first_replies,
        [r.item.number for r in again.refined_items],
        _replies_sent(model_fake),
        _require_item(store, asked).status,
    ) == ([], [asked], ["The job record holds it."], CONST_ROADMAP_STATUS_READY)


def test_closing_the_item_that_blocks_an_item_makes_it_eligible_again(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A blocked item waits while its blocker is open, and the round after the blocker closes
    refines it again with no reply and no body edit (#1758)."""
    store.seed_visibility(is_private=True)
    blocker = _seed_item(store, "In Progress", "P1-High")
    blocked = _seed_item(store, "New", "P1-High")
    model_fake.answer(_blocked_by(blocker))
    _refine_round(store, git_repo)

    waiting = plan_refine(store, repo=REPO, source=git_repo)
    store.as_actor("alice").close_by_hand(blocker, CloseReason.COMPLETED)
    after_close = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(w.item.number, w.step) for w in waiting.waiting_items],
        [r.item.number for r in after_close.refined_items],
    ) == ([(blocked, "blocked")], [blocked])


def test_an_unchanged_item_whose_record_needs_a_split_but_holds_no_step_gets_its_split_handed_on(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """An unchanged item whose record holds `refine.needs_split` and no next step is refined
    again, not skipped, and its split goes to a person in a comment (#1758)."""
    store.seed_visibility(is_private=True)
    number = _seed_item(store, "New", "P1-High")
    section = "## Proposed design\nNeeds splitting into 2 items."
    start, end = CONST_ROADMAP_REFINE_START_MARKER, CONST_ROADMAP_REFINE_END_MARKER
    store.write_issue_body(number, f"Body P1-High\n\n{start}\n{section}\n{end}")
    store.set_marks(
        _require_item(store, number),
        {
            RefineRecordKey.BODY_HASH: hash_text("Body P1-High"),
            RefineRecordKey.SECTION_HASH: hash_text(section),
            RefineRecordKey.NEEDS_SPLIT: "true",
        },
    )
    model_fake.answer(_SPLIT)

    plan = _refine_round(store, git_repo)

    assert (
        [(r.item.number, r.next_step) for r in plan.refined_items],
        [comment.splitlines()[-2:] for comment in _comment_bodies(store, number)],
    ) == ([(number, "split")], [["1. The first change.", "2. The second change."]])


def test_an_item_a_person_sets_back_to_new_waits_for_their_reason_and_is_refined_after_it(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """An item refine set Ready and a person set back to New waits on that person; their
    comment, as `devops roadmap return` posts, makes refine look again with it (#1758)."""
    store.seed_visibility(is_private=True)
    number = _seed_item(store, "New", "P1-High")
    model_fake.answer(_READY, _QUESTION)
    _refine_round(store, git_repo)
    person = store.as_actor("alice")

    person.set_field(_require_item(person, number), ItemField.STATUS, "New")
    waiting = plan_refine(store, repo=REPO, source=git_repo)
    person.comment(number, "It needs a new store.")
    returned = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(w.item.number, w.step, w.details) for w in waiting.waiting_items],
        [r.item.number for r in returned.refined_items],
        _replies_sent(model_fake),
    ) == (
        [
            (
                number,
                "person",
                (
                    "A person set the item back to New after refine set it to Ready. A reply "
                    "that tells why makes refine look at it again.",
                ),
            )
        ],
        [number],
        ["It needs a new store."],
    )


@pytest.mark.parametrize(
    ("answers", "status"),
    # A round that leaves the question open asks twice: the proposal and its investigation.
    [
        ((_QUESTION, _QUESTION, _READY), CONST_ROADMAP_STATUS_READY),
        ((_READY, _QUESTION, _QUESTION), "New"),
    ],
    ids=["waiting-on-a-person", "ready"],
)
def test_an_item_named_with_item_is_refined_though_nothing_changed_since_its_last_round(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    answers: tuple[RefinementProposal, ...],
    status: str,
) -> None:
    """`--item` refines the open New or Ready item it names, since a person asked for it, though
    its body is unchanged and no reply came (#1758)."""
    store.seed_visibility(is_private=True)
    number = _seed_item(store, "New", "P1-High")
    model_fake.answer(*answers)
    plan1 = plan_refine(store, repo=REPO, source=git_repo, item_number=number)
    apply_refine(store, plan1)

    again = plan_refine(store, repo=REPO, source=git_repo, item_number=number)
    apply_refine(store, again)

    assert (
        [r.item.number for r in again.refined_items],
        model_fake.call_count,
        _require_item(store, number).status,
    ) == ([number], 3, status)


@pytest.mark.parametrize("status", ["In Progress", "Blocked"])
def test_an_item_named_with_item_that_refine_never_changes_has_nothing_to_do(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, status: str
) -> None:
    """`--item` on an item In Progress or Blocked reports it with nothing to do and why,
    and calls no model (#1758)."""
    number = _seed_item(store, status, "P1-High")

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=number)

    assert (
        [(w.item.number, w.step, w.details) for w in plan.waiting_items],
        model_fake.call_count,
    ) == (
        [(number, "none", (f"Status {status}: refine changes only open New and Ready items.",))],
        0,
    )


def test_an_item_named_with_item_that_is_closed_has_nothing_to_do(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """`--item` on a closed issue reports it with nothing to do and calls no model (#1758)."""
    number = _seed_item(store, "New", "P1-High")
    store.as_actor("alice").close_by_hand(number, CloseReason.COMPLETED)

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=number)

    assert (
        [(w.item.number, w.step, w.details) for w in plan.waiting_items],
        model_fake.call_count,
    ) == ([(number, "none", ("The issue is closed: refine changes only open items.",))], 0)


def test_the_report_groups_every_item_under_its_next_step(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, snapshot: SnapshotAssertion
) -> None:
    """The report lists each item under its next step, in the order refined to Ready, waiting on
    a person, split proposed and blocked, with its details: the round that refines three of them,
    then the round that refines the fourth and finds the three waiting (#1758)."""
    _seed_waiting_items(store, model_fake)
    _seed_item(store, "New", "P1-High")
    model_fake.answer(_READY)

    rounds = [_refine_round(store, git_repo), _refine_round(store, git_repo)]

    assert [render_refine_plan(plan) for plan in rounds] == snapshot


# ── A change to the code its block cites ends an item's wait (#2005) ──────────────────────

_CITED_PATH = "src/sample.py"


def _block_in_code(blocker: int | None) -> RefinementProposal:
    """A proposal whose block the code in `src/sample.py` causes: it waits on the open item
    `blocker`, or, with None, on a suspected block alone, which a person decides."""
    proposal = _READY.model_copy(
        update={
            "suspected_block": "`hello_world` in src/sample.py returns a fixed text.",
            "block_paths": [_CITED_PATH],
        }
    )
    return proposal if blocker is None else proposal.model_copy(update={"dependencies": [blocker]})


def _refine_comment_at(store: InMemoryRoadmapStore, number: int) -> datetime:
    """When refine last commented on issue `number`."""
    marker = constants.CONST_ROADMAP_REFINE_COMMENT_MARKER
    return [c.created_at for c in store.comments_on(number) if marker in c.body][-1]


def _seed_item_blocked_in_code(
    store: InMemoryRoadmapStore, model_fake: ModelFake, *, blocked: bool = True
) -> int:
    """On a private repository, a New backlog P1 whose proposal cites `src/sample.py` as the
    cause of its block: it waits on an item In Progress, or on a person when not `blocked`."""
    store.seed_visibility(is_private=True)
    blocker = _seed_item(store, "In Progress", "P1-High")
    number = _seed_item(store, "New", "P1-High")
    model_fake.answer(_block_in_code(blocker if blocked else None))
    return number


@pytest.mark.parametrize("blocked", [True, False], ids=["blocked", "suspected-block"])
def test_a_waiting_item_whose_cited_path_changes_on_main_after_refines_comment_is_refined_again(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, blocked: bool
) -> None:
    """Refine records the path that its proposal cites as the cause of the block. A commit on
    the default branch that changes that path after refine's last comment ends the wait: the
    next round refines the item again, with no reply and no body edit (#2005)."""
    number = _seed_item_blocked_in_code(store, model_fake, blocked=blocked)
    _refine_round(store, git_repo)
    calls = model_fake.call_count

    store.seed_commit(_CITED_PATH, at=_refine_comment_at(store, number) + timedelta(minutes=5))
    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        _require_item(store, number).job_record.get(RefineRecordKey.BLOCK_PATHS),
        [r.item.number for r in again.refined_items],
        again.waiting_items,
        model_fake.call_count - calls,
    ) == (_CITED_PATH, [number], [], 1)


def test_a_waiting_item_whose_cited_path_does_not_change_keeps_waiting_with_no_model_call(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A commit that changed the cited path before refine's last comment, and a later commit
    that changed another path, leave the item waiting on its blocker, and the round makes no
    model call (#2005)."""
    number = _seed_item_blocked_in_code(store, model_fake)
    _refine_round(store, git_repo)
    calls = model_fake.call_count

    commented = _refine_comment_at(store, number)
    store.seed_commit(_CITED_PATH, at=commented - timedelta(days=1))
    store.seed_commit("CONTEXT.md", at=commented + timedelta(minutes=5))
    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(w.item.number, w.step) for w in again.waiting_items],
        again.refined_items,
        model_fake.call_count - calls,
    ) == ([(number, "blocked")], [], 0)


def test_refine_records_each_cited_path_the_checkout_holds_once_and_names_them_in_its_comment(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """Refine keeps a cited path once and without its line, only when the checkout holds it at
    the refined commit, and never a path outside the repository. Its comment names the files
    whose change ends the wait (#2005)."""
    store.seed_visibility(is_private=True)
    number = _seed_item(store, "New", "P1-High")
    cited = ["src/sample.py:1", "src/missing.py", "../CONTEXT.md", "/etc/hosts"]
    cited += ["src/sample.py", "CONTEXT.md"]
    model_fake.answer(_block_in_code(None).model_copy(update={"block_paths": cited}))

    _refine_round(store, git_repo)

    (comment,) = store.comments_on(number)
    assert (
        _require_item(store, number).job_record.get(RefineRecordKey.BLOCK_PATHS),
        comment.body.splitlines()[-1],
    ) == (
        "src/sample.py,CONTEXT.md",
        "The next refine round also looks at the item again when a commit on the default "
        "branch changes one of these files: `src/sample.py`, `CONTEXT.md`.",
    )


@pytest.mark.parametrize("proposal", [_READY, _QUESTION], ids=["ready", "question"])
def test_a_proposal_that_names_no_block_records_no_cited_path(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    proposal: RefinementProposal,
) -> None:
    """A path is recorded only as the cause of a block: a proposal with no suspected block and
    no open dependency records none, and its comment names none (#2005)."""
    store.seed_visibility(is_private=True)
    number = _seed_item(store, "New", "P1-High")
    model_fake.answer(proposal.model_copy(update={"block_paths": [_CITED_PATH]}))

    _refine_round(store, git_repo)

    assert (
        _require_item(store, number).job_record.get(RefineRecordKey.BLOCK_PATHS),
        [_CITED_PATH in comment.body for comment in store.comments_on(number)],
    ) == (None, [False])


# ── Body questions, decisions and the web search state (#2398) ────────────────────────────


def _seed_with_body(store: InMemoryRoadmapStore, body: str) -> int:
    """A New P1 backlog item with `body`, on a private repository."""
    store.seed_visibility(is_private=True)
    return store.seed_issue(
        "Item", body=body, fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"}
    )


def _first_request(model_fake: ModelFake) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(model_fake.calls[0].prompt)
    return document


def _section_lines(store: InMemoryRoadmapStore, number: int) -> list[str]:
    _, section = extract_section_and_outside(store.read_issue_body(number))
    return (section or "").splitlines()


_ANSWERED_IN_BODY = (
    "Body\n\n## Key questions\n"
    "- *Which ADR number?* (proposed) The next free one.\n"
    "- *Which files?*\n"
    "  - Decided: each file goes to the package that owns it.\n"
    "- #1336 owns the directory.\n"
)


def test_a_bodys_answered_key_questions_and_its_statements_open_no_question(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A question answered after its question mark or by indented lines, and a bullet with no
    question mark, are not sent and open no question, so one request makes the item Ready."""
    _seed_with_body(store, _ANSWERED_IN_BODY)
    model_fake.answer(_READY)

    plan = _refine_round(store, git_repo)

    assert (
        _first_request(model_fake)["body_questions"],
        plan.refined_items[0].next_step,
        model_fake.call_count,
    ) == ([], "ready", 1)


@pytest.mark.parametrize(
    ("section", "questions"),
    [
        (
            "- How should refine handle a body\n  that wraps across lines?\n",
            ["How should refine handle a body that wraps across lines?"],
        ),
        (
            "- How should refine handle a body\nthat wraps across lines?\n",
            ["How should refine handle a body that wraps across lines?"],
        ),
        (
            "- Which store holds the record?\n\nContext: the Service writes it hourly.\n",
            ["Which store holds the record?"],
        ),
        (
            "### Storage\n- Which backend holds the record?\n### Auth\n- Who owns the key?\n",
            ["Which backend holds the record?", "Who owns the key?"],
        ),
        (
            "- Which command installs the hook?\n\n```sh\n# README today:\nmake hooks\n```\n\n- Does the hook run on push?\n",
            ["Which command installs the hook?", "Does the hook run on push?"],
        ),
        ("- Which format does the export use?\n\n  It is JSON today.\n", []),
        ("- Which store?\n## Next\n- Not this one?\n", ["Which store?"]),
    ],
    ids=[
        "wrapped-indented",
        "wrapped-lazy",
        "paragraph-after",
        "sub-headings",
        "code-fence",
        "indented-answer",
        "next-section",
    ],
)
def test_the_body_questions_follow_markdown(section: str, questions: list[str]) -> None:
    """A wrapped question stays one question, a paragraph or a code block after the list answers
    nothing, a lower heading stays inside the section and a heading of its level ends it, and a
    paragraph indented under the item answers it."""
    assert body_questions(f"Body\n\n## Key questions\n{section}") == questions


def test_a_mark_the_model_copies_is_replaced_by_the_one_the_answer_earns(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """An answer that holds an earlier round's mark gets one mark: "(best practice)" for a
    sourced decision, and "(proposed)" for an unsourced one, which the investigation then sees."""
    sha = inspect_checkout(git_repo, REPO)
    copied = [
        QuestionAnswer(
            question="Sourced?",
            answer="Use the library. (proposed)",
            kind="decision",
            sources=["src/sample.py"],
        ),
        QuestionAnswer(
            question="Unsourced?",
            answer="(proposed) Use Valkey. It is maintained.",
            kind="decision",
        ),
    ]
    proposal, open_qs = validate_proposal(
        _READY.model_copy(update={"key_questions": copied}), "Body", set(), git_repo, sha, store
    )

    assert (
        [qa.answer for qa in proposal.key_questions],
        needs_investigation(proposal, open_qs),
    ) == (["Use the library. (best practice)", "Use Valkey. It is maintained. (proposed)"], True)


def test_only_an_answer_that_quotes_an_owner_decision_is_the_owners(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    sha = inspect_checkout(git_repo, REPO)
    body = "Body\n\n## Owner decisions\n- Use Valkey, not Redis.\n"
    answers = [
        QuestionAnswer(question="Cache?", answer="Redis", kind="decision"),
        QuestionAnswer(question="Store?", answer="Use Valkey, not Redis.", kind="decision"),
    ]
    proposal, _ = validate_proposal(
        _READY.model_copy(update={"key_questions": answers}), body, set(), git_repo, sha, store
    )

    assert [qa.answer for qa in proposal.key_questions] == [
        "Redis (proposed)",
        "Use Valkey, not Redis. (owner decision)",
    ]


def test_the_investigation_hears_of_a_decision_whose_sources_failed(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A decision whose cited path the commit does not hold reaches the investigation as a
    decision with no verified source."""
    _seed_with_body(store, "Body")
    answer = QuestionAnswer(
        question="Which parser?",
        answer="Use the library.",
        kind="decision",
        sources=["docs/parsers.md"],
    )
    model_fake.answer(_READY.model_copy(update={"key_questions": [answer]}))

    _refine_round(store, git_repo)

    assert json.loads(model_fake.calls[1].prompt)["open_questions"] == [
        "Which parser? (decision with no verified source)"
    ]


def test_a_url_source_renders_as_a_link_before_the_closing_bracket() -> None:
    url = "https://example.com/doc"
    answer = QuestionAnswer(question="Which?", answer="This.", kind="decision", sources=[url])
    section = render_proposal_section(
        _READY.model_copy(update={"key_questions": [answer]}), [], "a" * 40, {url}
    )

    assert f"[sources: {url}]" in section


def test_a_body_question_that_no_answer_names_waits_on_a_person(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    _seed_with_body(store, "Body\n\n## Key questions\n- *Which store holds the record?*\n")
    model_fake.answer(_READY)

    plan = _refine_round(store, git_repo)

    refined = plan.refined_items[0]
    assert (
        _first_request(model_fake)["body_questions"],
        refined.next_step,
        refined.step_details,
    ) == (
        [{"number": 1, "question": "*Which store holds the record?*"}],
        "person",
        ("*Which store holds the record?*",),
    )


def test_an_answer_that_names_a_body_question_answers_it(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    _seed_with_body(store, "Body\n\n## Key questions\n- *Which store holds the record?*\n")
    answer = QuestionAnswer(
        question="Which store?",
        answer="The job record.",
        kind="decision",
        sources=["src/sample.py"],
        body_question=1,
    )
    model_fake.answer(_READY.model_copy(update={"key_questions": [answer]}))

    plan = _refine_round(store, git_repo)

    assert (plan.refined_items[0].next_step, model_fake.call_count) == ("ready", 1)


_LIBRARY = DesignOption(option="Use the library", chosen=True, reason="It is maintained.")
_PARSER = DesignOption(option="Write a parser", chosen=False, reason="It adds code to keep.")


def _decision(sources: list[str]) -> RefinementProposal:
    answer = QuestionAnswer(
        question="Which parser?",
        answer="Use the library.",
        kind="decision",
        sources=sources,
        options=[_LIBRARY, _PARSER],
    )
    return _READY.model_copy(update={"key_questions": [answer]})


def test_a_sourced_decision_shows_its_options_and_the_best_practice_and_can_be_ready(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    number = _seed_with_body(store, "Body")
    model_fake.answer(_decision(["src/sample.py"]))

    plan = _refine_round(store, git_repo)

    lines = _section_lines(store, number)
    start = lines.index("### Key questions") + 1
    assert (plan.refined_items[0].next_step, model_fake.call_count, lines[start : start + 3]) == (
        "ready",
        1,
        [
            "- **Which parser?**: Use the library. (best practice) [sources: src/sample.py]",
            "  - Chosen: Use the library. It is maintained.",
            "  - Rejected: Write a parser. It adds code to keep.",
        ],
    )


def test_an_unsourced_decision_is_investigated_and_stays_proposed(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A decision with no source starts the investigation; when it finds none, the decision
    stays "(proposed)" and does not stop Ready."""
    number = _seed_with_body(store, "Body")
    model_fake.answer(_decision([]))

    plan = _refine_round(store, git_repo)

    lines = _section_lines(store, number)
    start = lines.index("### Key questions") + 1
    assert (plan.refined_items[0].next_step, model_fake.call_count, lines[start]) == (
        "ready",
        2,
        "- **Which parser?**: Use the library. (proposed)",
    )


def test_a_question_for_a_person_waits_on_a_person_with_no_investigation(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    _seed_with_body(store, "Body")
    asked = QuestionAnswer(
        question="Which repository secret holds the key?",
        answer="Recommended: a new secret.",
        kind="person",
    )
    model_fake.answer(_READY.model_copy(update={"key_questions": [asked]}))

    plan = _refine_round(store, git_repo)

    refined = plan.refined_items[0]
    assert (refined.next_step, refined.step_details, model_fake.call_count) == (
        "person",
        ("Which repository secret holds the key? (a person decides)",),
        1,
    )


@pytest.mark.parametrize(
    ("is_private", "reason"),
    [(False, "no Firecrawl key is set"), (True, "the repository is private")],
    ids=["no-key", "private"],
)
def test_a_round_with_no_web_search_says_why(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    is_private: bool,
    reason: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    _seed_with_body(store, "Body")
    store.seed_visibility(is_private=is_private)
    model_fake.answer(_READY)

    plan = plan_refine(store, repo=REPO, source=git_repo)

    assert (plan.web_search_off, render_refine_plan(plan).splitlines()[1]) == (
        reason,
        f"Web search is off: {reason}.",
    )
