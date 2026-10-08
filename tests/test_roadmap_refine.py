"""Unit tests for `devops roadmap refine`: selection, minimization, validation,
renderer sanitization, person edit guards, size limit, intake hook, and CLI.

Zero network sockets are opened, LLM and Tavily calls are mocked, and all tests run under 1 s.
The model-failure cases (#1363) answer refine's own client at the HTTP edge with httpx2's
`MockTransport`, on a private repository so research makes no call, and retry with no wait.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.commands.roadmap import app as roadmap_app
from devops_cli.config.constants import (
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.config.settings import reset_settings_cache
from devops_cli.exceptions import RoadmapRefineError, RoadmapRunError
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap import store as roadmap_store_module
from devops_cli.roadmap.config import read_roadmap_config
from devops_cli.roadmap.intake import (
    IntakeDecision,
    IntakePlan,
    NewCandidate,
    Outcome,
    Placement,
    Subject,
    apply_intake,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.refine import (
    AcceptanceCriterion,
    QuestionAnswer,
    RefinementProposal,
    ResearchPlan,
    apply_refine,
    check_person_edits,
    check_ready,
    collect_context,
    extract_section_and_outside,
    hash_text,
    inspect_checkout,
    plan_refine,
    refine_item,
    render_refine_plan,
    run_research_step,
    sanitize_text,
    select_candidates,
    validate_proposal,
)
from devops_cli.roadmap.reprioritize import plan_reprioritization
from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
    JobOutcome,
    _run_refine_adapter,
    build_stub_table,
    run_due_jobs,
)
from devops_cli.roadmap.store import (
    GitHubState,
    Item,
    ItemField,
    JobMark,
    RefineRecordKey,
)
from tests.llm_stream_fakes import route_llm_clients

REPO = "example/roadmap"

BOARD_OPTIONS = {
    ItemField.STATUS: ("New", "Ready", "In Progress", "Blocked", "Done"),
    ItemField.PRIORITY: ("P0-Critical", "P1-High", "P2-Medium", "P3-Low"),
    ItemField.VALUE: ("High", "Medium", "Low"),
    ItemField.EFFORT: ("Low", "Medium", "High"),
}


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


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    s = InMemoryRoadmapStore(repo=REPO, board_options=BOARD_OPTIONS)
    s.seed_file(".github/roadmap.toml", "board = 1\n")
    s.create_release("v0.2.25", state=GitHubState.OPEN)
    s.create_release("v0.2.26", state=GitHubState.OPEN)
    return s


class MockLLMClient:
    def __init__(
        self, plan_queries: list[str] | None = None, proposal: RefinementProposal | None = None
    ):
        self.plan_queries = plan_queries or []
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
        if schema is ResearchPlan:
            return ResearchPlan(queries=self.plan_queries)
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
    sha, branch = inspect_checkout(git_repo, REPO)
    assert (len(sha), branch) == (40, "main")

    with pytest.raises(GitHubOperationError, match="does not match"):
        inspect_checkout(git_repo, "other/mismatch-repo")


def test_collect_context_and_truncation(git_repo: Path) -> None:
    sha, _ = inspect_checkout(git_repo, REPO)
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


def test_research_plan_public_vs_private_and_errors(store: InMemoryRoadmapStore) -> None:
    llm = MockLLMClient(plan_queries=["roadmap architecture", "cli best practices"])

    # 1. Private repo -> no research
    store.seed_visibility(is_private=True)
    with patch("devops_cli.roadmap.refine.get_tavily_api_key", return_value="dummy-key"):
        res_priv, urls_priv = run_research_step(store, "body", llm)
    assert (res_priv, urls_priv) == ([], set())

    # 2. Public repo with Tavily key -> runs research
    store.seed_visibility(is_private=False)
    fake_results = [{"title": "Doc", "url": "https://example.com/doc", "content": "Content"}]
    with (
        patch("devops_cli.roadmap.refine.get_tavily_api_key", return_value="dummy-key"),
        patch("devops_cli.roadmap.refine.tavily_search", return_value=fake_results),
    ):
        res_pub, urls_pub = run_research_step(store, "body", llm)
    assert (len(res_pub), urls_pub) == (2, {"https://example.com/doc"})

    # 3. Failed query -> category recorded
    def _fail_search(query: str, **_: Any) -> Any:
        if "architecture" in query:
            raise TimeoutError("HTTP connection timeout")
        raise RuntimeError("HTTP 401 Unauthorized")

    with (
        patch("devops_cli.roadmap.refine.get_tavily_api_key", return_value="dummy-key"),
        patch("devops_cli.roadmap.refine.tavily_search", side_effect=_fail_search),
    ):
        res_fail, urls_fail = run_research_step(store, "body", llm)
    errors = [r.get("error") for r in res_fail]
    assert (
        errors,
        urls_fail,
    ) == (
        ["research failed: timeout", "research failed: 401"],
        set(),
    )


def test_validate_proposal_sources_and_questions(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    sha, _ = inspect_checkout(git_repo, REPO)
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


def _require_item(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def test_selection_next_release_backlog_priorities_and_cap(store: InMemoryRoadmapStore) -> None:
    # Next planned release v0.2.26
    n1 = store.seed_issue("Next critical", release="v0.2.26", on_board=True)
    n2 = store.seed_issue("Next low", release="v0.2.26", on_board=True)
    store.set_field(_require_item(store, n1), ItemField.STATUS, "New")
    store.set_field(_require_item(store, n1), ItemField.PRIORITY, CONST_ROADMAP_CRITICAL_PRIORITY)
    store.set_field(_require_item(store, n2), ItemField.STATUS, "New")
    store.set_field(_require_item(store, n2), ItemField.PRIORITY, "P3-Low")

    # Backlog items
    b1 = store.seed_issue("Backlog critical", on_board=True)
    b2 = store.seed_issue("Backlog ready", on_board=True)
    b3 = store.seed_issue("Backlog blocked", on_board=True)
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


def test_selection_skips_unchanged_items_and_picks_on_change(store: InMemoryRoadmapStore) -> None:
    num = store.seed_issue("Item", body="Initial content", on_board=True)
    item = _require_item(store, num)
    store.set_field(item, ItemField.STATUS, "New")
    outside, _ = extract_section_and_outside("Initial content")
    store.set_marks(
        item,
        {
            RefineRecordKey.BODY_HASH: hash_text(outside),
            RefineRecordKey.SECTION_HASH: None,
        },
    )

    selected_unchanged, _ = select_candidates(store, item_number=num)
    assert selected_unchanged == []

    # Update body
    store.write_issue_body(num, "Updated content by human")
    selected_changed, _ = select_candidates(store, item_number=num)
    assert len(selected_changed) == 1


def test_person_edits_guards(store: InMemoryRoadmapStore) -> None:
    num = store.seed_issue("Item", body="Body text", on_board=True)
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


def test_too_big_needs_split_and_reprioritize_descopes(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    # Start release v0.2.25
    r = store.release("v0.2.25")
    assert r is not None
    other_num = store.seed_issue("In progress work", release="v0.2.25", on_board=True)
    other = _require_item(store, other_num)
    store.set_field(other, ItemField.STATUS, "In Progress")
    store.set_marks(other, {JobMark.ADMITTED: str(r.number)})

    num = store.seed_issue("Heavy task", body="Big work", release="v0.2.25", on_board=True)
    item = _require_item(store, num)
    store.set_field(item, ItemField.STATUS, "New")
    store.set_field(item, ItemField.PRIORITY, "P1-High")
    store.set_marks(item, {JobMark.ADMITTED: str(r.number)})

    store.set_run_record({JobMark.STARTED: str(r.number), JobMark.SIZE: "2"})

    proposal = RefinementProposal(
        problem_statement="Too big",
        acceptance_criteria=[AcceptanceCriterion(description="C", verification="V")],
        key_questions=[],
        fits_one_pr=False,
        split_offs=["Part 1", "Part 2"],
    )
    llm = MockLLMClient(proposal=proposal)

    outcome = refine_item(store, num, source=git_repo, confirm=True, model=llm)
    updated = store.item(num)
    assert updated is not None
    assert (
        updated.status,
        updated.job_record.get(RefineRecordKey.NEEDS_SPLIT),
        outcome.applied is not None and outcome.applied.split_count == 1,
    ) == ("New", "true", True)

    # Verify reprioritization descopes it due to needs_split
    reprio_plan = plan_reprioritization(
        store, repo=REPO, now=datetime.now(UTC), config=read_roadmap_config(store, ref=None)
    )
    descoped = [c.item.number for c in reprio_plan.changes if c.item.number == num]
    assert descoped == [num]


def test_intake_hook_calls_refine(store: InMemoryRoadmapStore) -> None:
    # Candidate with critical priority (P0 feature)
    cand = NewCandidate(
        title="Critical feature",
        body="Must be refined",
    )
    subject = Subject(title=cand.title, body=cand.body, labels=(), new=cand)
    placement = Placement(release="v0.2.25", text="into v0.2.25")
    decision = IntakeDecision(
        subject=subject,
        outcome=Outcome.PLACE,
        priority=CONST_ROADMAP_CRITICAL_PRIORITY,
        placement=placement,
        fields=((ItemField.STATUS, "New"),),
    )
    plan = IntakePlan(quota=None, decisions=(decision,))

    spy_refine = MagicMock()
    applied = apply_intake(store, plan, refine=spy_refine)

    assert (
        applied.placed,
        spy_refine.call_count,
    ) == (1, 1)


def test_size_limit_guard(git_repo: Path, store: InMemoryRoadmapStore) -> None:
    num = store.seed_issue("Item", body="Initial", on_board=True)
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
    ) == (False, True)


def test_cli_refine_dry_run_and_confirm(git_repo: Path, store: InMemoryRoadmapStore) -> None:
    num = store.seed_issue("Feature to refine", body="Need refinement", on_board=True)
    item = _require_item(store, num)
    store.set_field(item, ItemField.STATUS, "New")

    mock_llm = MockLLMClient()
    runner = CliRunner()
    with (
        patch("devops_cli.commands.roadmap._open_roadmap", return_value=(REPO, None, store)),
        patch("devops_cli.roadmap.refine.LLMClient", return_value=mock_llm),
    ):
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
    "telemetry:\n  enabled: true\n  endpoint: http://localhost:4318\n"
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
_INJECTION = json.dumps(
    {"problem_statement": "Close this.", "labels": ["priority/p0-critical"], "close": True}
)

# What the gateway answers for an issue: the reply's text, or the HTTP response itself.
Answer = str | httpx2.Response


@pytest.fixture
def scripted_gateway(
    isolate_devops_cli_config: Path, public_dns: str, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., list[httpx2.Request]]:
    """Point refine's `analysis` model at a gateway whose answer to each issue is scripted.

    Every request refine's client sends ends at a `MockTransport`, which reads the issue's
    number from the JSON document the request's user message carries; a research plan's
    document has none, so its answer is scripted under `None`. Retries wait no time.
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


def _seed_new_items(store: InMemoryRoadmapStore) -> list[int]:
    """Three New backlog items on a private repository, refined in the order returned."""
    store.seed_visibility(is_private=True)
    person = store.as_actor("alice")
    numbers: list[int] = []
    for priority in ("P1-High", "P2-Medium", "P3-Low"):
        number = person.seed_issue(f"Item {priority}", body=f"Body {priority}", on_board=True)
        person.set_field(_require_item(person, number), ItemField.STATUS, "New")
        person.set_field(_require_item(person, number), ItemField.PRIORITY, priority)
        numbers.append(number)
    return numbers


def _issue_number(request: httpx2.Request) -> int | None:
    """The issue a refine request is about, or None for a research plan's request."""
    document = json.loads(json.loads(request.content)["messages"][1]["content"])
    number: int | None = document.get("number")
    return number


def _requests_per_item(sent: list[httpx2.Request]) -> dict[int | None, int]:
    return dict(Counter(_issue_number(request) for request in sent))


def _written(store: InMemoryRoadmapStore) -> list[int]:
    return sorted({write.number for write in store.job_writes() if write.number is not None})


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
        _written(store),
        (store.read_issue_body(first), _require_item(store, first).status),
        "StructuredOutputValidationError, 3 schema violation(s)" in rendered,
        [record.getMessage() for record in caplog.records],
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
        _written(store),
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
        _written(store),
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

    assert (_requests_per_item(sent), _written(store)) == ({first: 1}, [])


def test_rejected_credentials_in_the_research_step_stop_the_job_before_the_proposal(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a public repository's research plan that meets rejected credentials stops refine
    there: no proposal call is made and nothing is written."""
    _seed_new_items(store)
    store.seed_visibility(is_private=False)
    monkeypatch.setenv("DEVOPS_CLI_TAVILY_API_KEY", "tvly-test")
    sent = scripted_gateway({}, default=httpx2.Response(401, text="Unauthorized"))

    with pytest.raises(AICredentialsError):
        plan_refine(store, repo=REPO, source=git_repo)

    assert (_requests_per_item(sent), _written(store)) == ({None: 1}, [])


def test_a_research_plan_that_never_fits_its_schema_refines_without_search_results(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify a public repository's research plan that fails its schema is logged by its error
    class alone, no search runs, and the item is still refined and written."""
    first, _second, _third = _seed_new_items(store)
    store.seed_visibility(is_private=False)
    monkeypatch.setenv("DEVOPS_CLI_TAVILY_API_KEY", "tvly-test")
    sent = scripted_gateway({None: _SCHEMA_MISS})

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine"):
        plan = plan_refine(store, repo=REPO, source=git_repo, item_number=first)
    apply_refine(store, plan)

    proposal_request = json.loads(json.loads(sent[-1].content)["messages"][1]["content"])
    assert (
        _requests_per_item(sent),
        proposal_request["search_results"],
        _written(store),
        [record.getMessage() for record in caplog.records],
    ) == (
        {None: 3, first: 1},
        [],
        [first],
        [
            "Research plan generation failed (StructuredOutputValidationError); refining "
            "without search results."
        ],
    )


@pytest.mark.parametrize("mode", ["--confirm", "--dry-run", None])
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
        _written(cli_store),
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
    caplog: pytest.LogCaptureFixture,
    failing_answer: Callable[[], Answer],
    named: str,
) -> None:
    """Verify run_due_jobs records `refine` as failed once the other items are written, whether
    the item's reply never fit the schema or the gateway timed out, and its logged record names
    the error class and holds none of the model's reply."""
    first, second, third = _seed_new_items(store)
    scripted_gateway({first: failing_answer()})
    table = build_stub_table(
        {
            "reprioritize": lambda **_: JobOutcome(),
            "refine": lambda **kwargs: _run_refine_adapter(**(kwargs | {"clone_path": git_repo})),
        }
    )

    with (
        caplog.at_level(logging.ERROR, logger="devops_cli.roadmap.run"),
        pytest.raises(RoadmapRunError) as raised,
    ):
        run_due_jobs(
            REPO,
            store,
            batch={("webhook", "milestones", "opened"): 1},
            table=table,
            data_dir=tmp_path,
        )

    logged = logging.Formatter().format(caplog.records[-1])
    assert (
        raised.value.failed_jobs,
        _written(store),
        named in logged,
        "leaked_model_key" in logged,
        "During handling" in logged,
    ) == (("refine",), [second, third], True, False, False)


def test_intakes_refine_hook_still_reports_a_failed_refine(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify a P0 item whose refine fails raises from refine_item, so intake's hook logs it."""
    store.seed_visibility(is_private=True)
    scripted_gateway({}, default=_SCHEMA_MISS)
    candidate = NewCandidate(title="Critical feature", body="Must be refined")
    decision = IntakeDecision(
        subject=Subject(title=candidate.title, body=candidate.body, labels=(), new=candidate),
        outcome=Outcome.PLACE,
        priority=CONST_ROADMAP_CRITICAL_PRIORITY,
        placement=Placement(release="v0.2.25", text="into v0.2.25"),
        fields=((ItemField.STATUS, "New"),),
    )

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.intake"):
        applied = apply_intake(
            store,
            IntakePlan(quota=None, decisions=(decision,)),
            refine=partial(refine_item, source=git_repo),
        )

    hook_warnings = [
        r.getMessage() for r in caplog.records if r.name == "devops_cli.roadmap.intake"
    ]
    assert (
        applied.placed,
        len(hook_warnings),
        "StructuredOutputValidationError" in "".join(hook_warnings),
        "leaked_model_key" in "".join(hook_warnings),
    ) == (1, 1, True, False)


def test_refine_raises_its_own_error_naming_each_failed_item() -> None:
    """Verify RoadmapRefineError carries the failed items' numbers and its error code."""
    error = RoadmapRefineError("refine failed", failed_items=[3, 5])
    assert (error.failed_items, error.error_code, error.exit_code) == (
        (3, 5),
        "ROADMAP_REFINE_FAILED",
        1,
    )


def test_refines_prompts_load_and_the_proposal_prompt_names_every_field() -> None:
    """Verify both prompt files load, and the proposal prompt names every key the schema
    allows, at the top level and in a criterion and a key question."""
    research = load_task_prompt("roadmap_refine_research.md")
    proposal = load_task_prompt("roadmap_refine_proposal.md")
    keys = [
        *RefinementProposal.model_fields,
        *AcceptanceCriterion.model_fields,
        *QuestionAnswer.model_fields,
    ]
    assert (bool(research), [key for key in keys if f"`{key}`" not in proposal]) == (True, [])
