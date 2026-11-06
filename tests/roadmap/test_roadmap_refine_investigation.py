"""Tests for refine's investigation (#2398): the read-only tools on the pinned commit, the
pydantic-ai run that settles a proposal's open questions, its budget, its errors and its spend.

pydantic-ai's `FunctionModel` answers each model request from a script, so no test reaches a
model. Firecrawl is answered at the HTTP edge by `web`, and git runs on a temporary repository.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
import subprocess
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import Tool
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import UsageLimits

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.config.constants import (
    CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE,
    CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS,
    CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS,
    CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS,
    CONST_ROADMAP_REFINE_MAX_REPLIES,
    CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS,
    CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES,
    CONST_ROADMAP_RUN_ERROR_CHARS,
)
from devops_cli.roadmap import refine
from devops_cli.roadmap.agent_run import (
    RunLimit,
    RunTrace,
    ToolOutcome,
    empty_answer,
    error_answer,
    ok_answer,
)
from devops_cli.roadmap.refine import (
    AcceptanceCriterion,
    JobCheck,
    NextStep,
    QuestionAnswer,
    RefinementProposal,
    inspect_checkout,
    plan_refine,
    render_refine_plan,
)
from devops_cli.roadmap.refine_investigation import (
    InvestigationTools,
    cited_web_search,
    investigate,
)
from devops_cli.roadmap.store import ItemField
from tests.support.fakes.http import WebFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.scripted_model import Script, call

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"

# One acceptance criterion in the shape of an OpenSpec requirement, and the existing-tool answer
# that every proposal carries (#1849).
_CRITERION = AcceptanceCriterion(
    name="A design",
    requirement="The item SHALL have a design.",
    scenario="A person reads the item",
    when="a person reads the item",
    then="the design is in the item",
)
_CRITERION_JSON = _CRITERION.model_dump()
_TOOL = "No open tool covers the need."
_FIRECRAWL_URL = "https://api.firecrawl.dev/v2/search"
_OPEN_FACT = QuestionAnswer(question="Where is the sample function?", answer="?", kind="fact")
_FIRST = RefinementProposal(
    existing_tool=_TOOL,
    problem_statement="The item needs a design.",
    acceptance_criteria=[_CRITERION],
    key_questions=[_OPEN_FACT],
)
_SETTLED = _FIRST.model_copy(
    update={
        "key_questions": [
            _OPEN_FACT.model_copy(
                update={"answer": "In src/sample.py.", "sources": ["src/sample.py:1"]}
            )
        ]
    }
)


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A checkout of `REPO` whose one commit holds `src/sample.py`."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        _git(repo, "config", key, value)
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "remote", "add", "origin", f"https://example.com/{REPO}.git")
    (repo / "src" / "sample.py").write_text(
        "def hello_world():\n    return 'hello'\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    """A private roadmap with one New P1 backlog item, number 1."""
    s = InMemoryRoadmapStore(repo=REPO, is_private=True)
    s.seed_issue(
        "Item", body="Body", fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"}
    )
    return s


@pytest.fixture
def window(monkeypatch: pytest.MonkeyPatch) -> Callable[[int], None]:
    """Set the context window of the `analysis` task that a refine investigation reads."""

    def set_window(tokens: int) -> None:
        monkeypatch.setattr(refine, "analysis_window", lambda: tokens)

    return set_window


@pytest.fixture
def wide_window(window: Callable[[int], None]) -> None:
    """A window that the messages of a run never fill, so the counts of requests and calls bind."""
    window(10**9)


class _FirstPhase:
    """The proposal step's client: it answers every proposal request with `proposal`."""

    def __init__(self, proposal: RefinementProposal) -> None:
        self.proposal = proposal

    def chat_structured(self, system: str, prompt: str, schema: type[Any], **_: Any) -> Any:
        return self.proposal


def _round(
    store: InMemoryRoadmapStore, git_repo: Path, first: RefinementProposal, script: Script
) -> Any:
    return plan_refine(
        store,
        repo=REPO,
        source=git_repo,
        model=_FirstPhase(first),
        investigator=script.model(),
    )


def test_a_fact_that_a_file_read_settles_makes_the_item_ready(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """The investigation reads the file the fact is about, cites its line, and the revised
    proposal validates with no open question."""
    script = Script(call("read_file", path="src/sample.py"), _SETTLED)

    plan = _round(store, git_repo, _FIRST, script)

    refined = plan.refined_items[0]
    assert (
        refined.next_step,
        refined.open_questions,
        [qa.sources for qa in refined.proposal.key_questions],
        script.tool_returns(),
    ) == (
        NextStep.READY,
        [],
        [["src/sample.py:1"]],
        ["1: def hello_world():\n2:     return 'hello'"],
    )


def test_the_investigation_request_names_the_open_questions(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    script = Script(_SETTLED)

    _round(store, git_repo, _FIRST, script)

    prompt = next(
        part.content for part in script.seen[0][0].parts if isinstance(part, UserPromptPart)
    )
    request = json.loads(str(prompt))
    assert (request["open_questions"], request["proposal"]["key_questions"][0]["question"]) == (
        ["Where is the sample function? (missing verified source)"],
        "Where is the sample function?",
    )


def test_a_proposal_with_nothing_open_runs_no_investigation(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    script = Script(_SETTLED)

    plan = _round(store, git_repo, _SETTLED, script)

    assert (plan.refined_items[0].next_step, script.seen) == (NextStep.READY, [])


@pytest.mark.usefixtures("wide_window")
def test_the_function_tools_go_when_the_budget_is_nearly_spent(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """A model that keeps calling tools gets no function tool once the budget has room for no
    more than its answer, and its next reply, the proposal, ends the run inside the budget. The
    refused path starts no git."""
    script = Script(call("read_file", path="../outside.py"), without_tools=_SETTLED)

    plan = _round(store, git_repo, _FIRST, script)

    # One call in each turn: the request limit binds first, and the last request offers no tool.
    assert (
        plan.refined_items[0].next_step,
        [len(offered) for offered in script.tools_offered],
    ) == (NextStep.READY, [3] * (CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS - 1) + [0])


def test_the_window_of_the_analysis_task_ends_the_tools_before_the_counts_do(
    git_repo: Path, store: InMemoryRoadmapStore, window: Callable[[int], None]
) -> None:
    """A refine investigation reads the context window of the `analysis` task, so a run on a
    small window ends its tools after a few turns and not after the 30 requests that the counts
    allow (#3206)."""
    window(6000)
    script = Script(call("read_file", path="../outside.py"), without_tools=_SETTLED)

    plan = _round(store, git_repo, _FIRST, script)

    offered = [len(tools) for tools in script.tools_offered]
    assert (plan.refined_items[0].next_step, offered[-1], len(offered) < 10) == (
        NextStep.READY,
        0,
        True,
    )


def _words(tokens: int) -> str:
    """Text of more than `tokens` tokens, with no repeated word."""
    return " ".join(f"word{n}" for n in range(tokens))


def _refine_request_tokens(git_repo: Path, *, body: int, replies: int, reply_tokens: int) -> int:
    """The tokens of the first request of a refine investigation for an item with a body of `body`
    tokens and `replies` replies of `reply_tokens` tokens each, as the run hook counts them: every
    message, as JSON. The model is scripted, so nothing reaches a model."""
    store = InMemoryRoadmapStore(repo=REPO, is_private=True)
    number = store.seed_issue(
        "Item", body=_words(body), fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"}
    )
    for _ in range(replies):
        store.seed_comment(number, _words(reply_tokens), author_association="OWNER")
    script = Script(_SETTLED)

    _round(store, git_repo, _FIRST, script)

    return count_tokens(ModelMessagesTypeAdapter.dump_json(script.seen[0]).decode())


def test_the_refine_request_of_a_large_item_passes_the_tool_removal_limit(
    git_repo: Path, window: Callable[[int], None]
) -> None:
    """The measure of #3477: refine reads the same window as the stage job, 65,536 tokens, so its
    investigation offers no tool from 49,152 tokens on. Refine cuts the replies, not the body. The
    largest Ready body is about 3,400 tokens; this item has a body of 8,192 tokens and three
    replies of 1,000 tokens. The test prints the counts. The worst case, 10 replies at their cap of 4,096
    tokens, prints too: it is over the limit, and this change does not alter refine."""
    window(65536)
    limit = 65536 - 65536 // CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE
    large = _refine_request_tokens(git_repo, body=8192, replies=3, reply_tokens=1000)
    worst = _refine_request_tokens(
        git_repo,
        body=8192,
        replies=CONST_ROADMAP_REFINE_MAX_REPLIES,
        reply_tokens=CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS,
    )
    print(
        f"refine request: {large} tokens for a large item, {worst} tokens for the worst case; "
        f"the tool-removal limit is {limit} tokens"
    )

    assert (large < limit, limit) == (True, 49152)


@pytest.mark.usefixtures("wide_window")
def test_a_turn_whose_calls_pass_the_budget_is_a_job_failure_that_names_the_item(
    git_repo: Path, store: InMemoryRoadmapStore, caplog: pytest.LogCaptureFixture
) -> None:
    """One turn that asks for more calls than the budget holds ends the run; its open question is
    a job failure that a later round tries again, not a person wait, and the log names the item."""
    calls = [
        ToolCallPart(tool_name="read_file", args={"path": "../outside.py"})
        for _ in range(CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS + 1)
    ]
    script = Script(ModelResponse(parts=calls))

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine"):
        plan = _round(store, git_repo, _FIRST, script)

    refined = plan.refined_items[0]
    assert refined.failure is not None
    assert (
        refined.next_step,
        refined.failure.checks,
        plan.failed_items,
        any("#1" in record.getMessage() for record in caplog.records),
    ) == (
        NextStep.RETRY,
        (JobCheck.INVESTIGATION_STOPPED, JobCheck.MISSING_SOURCE),
        [],
        True,
    )


def test_the_tools_read_only_the_pinned_commit(git_repo: Path) -> None:
    """A later commit is not visible, and a path outside the repository is refused."""
    sha = inspect_checkout(git_repo, REPO)
    (git_repo / "src" / "sample.py").write_text("def changed():\n    pass\n", encoding="utf-8")
    _git(git_repo, "commit", "-q", "-am", "later")
    tools = InvestigationTools(source=git_repo, sha=sha)

    assert (
        tools.search_code("HELLO_world"),
        tools.search_code("changed"),
        tools.list_files("src"),
        tools.list_files(""),
        tools.read_file("src/sample.py", start_line=2),
        tools.read_file("src/missing.py"),
        tools.read_file("../outside.py"),
        tools.read_file("/etc/hostname"),
    ) == (
        ok_answer("src/sample.py:1:def hello_world():"),
        empty_answer("No match."),
        ok_answer("src/sample.py"),
        ok_answer("src"),
        ok_answer("2:     return 'hello'"),
        error_answer("The commit holds no file src/missing.py."),
        error_answer("The path ../outside.py is outside the repository."),
        error_answer("The path /etc/hostname is outside the repository."),
    )


def test_web_search_is_absent_without_a_key(git_repo: Path) -> None:
    tools = InvestigationTools(source=git_repo, sha=inspect_checkout(git_repo, REPO))

    assert [tool.name for tool in tools.tools()] == ["search_code", "list_files", "read_file"]


def test_web_search_adds_each_url_and_stops_at_its_cap(git_repo: Path, web: WebFake) -> None:
    result = {"title": "Gitleaks", "url": "https://example.com/gitleaks", "description": "Scans."}
    reply = {"success": True, "data": {"web": [result]}}
    web.content(_FIRECRAWL_URL, json.dumps(reply).encode())
    tools = InvestigationTools(
        source=git_repo, sha=inspect_checkout(git_repo, REPO), firecrawl_key="fc-test"
    )

    answers = [
        tools.search_web("gitleaks dir") for _ in range(CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES + 1)
    ]

    assert (
        [tool.name for tool in tools.tools()][-1],
        answers[0],
        answers[-1],
        tools.allowed_urls,
        len(web.sent),
    ) == (
        "search_web",
        "Gitleaks\nhttps://example.com/gitleaks\nScans.",
        "The search limit for this item is reached.",
        {"https://example.com/gitleaks"},
        CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES,
    )


def _investigate(git_repo: Path, script: Script, model: Any = None) -> Any:
    tools = InvestigationTools(source=git_repo, sha=inspect_checkout(git_repo, REPO))
    return investigate(model or script.model(), "Instructions.", "{}", tools, RefinementProposal)


@pytest.mark.parametrize(
    ("answer", "raised"),
    [(ModelHTTPError(401, "m"), AICredentialsError), (ModelHTTPError(500, "m"), AIClientError)],
    ids=["refused-key", "server-error"],
)
def test_a_failed_model_call_becomes_refines_own_error(
    git_repo: Path, answer: Exception, raised: type[AIClientError]
) -> None:
    with pytest.raises(AIClientError) as caught:
        _investigate(git_repo, Script(answer))

    assert type(caught.value) is raised


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (
            ModelResponse(parts=[TextPart(content="not json")]),
            "Exceeded maximum output retries (2)",
        ),
        (
            call("read_file", path=["not", "a", "path"]),
            "Tool <text> exceeded max retries count of 2.",
        ),
    ],
    ids=["never-an-answer", "tool-arguments-never-valid"],
)
def test_a_model_that_breaks_the_rules_past_its_retries_stops_the_run(
    git_repo: Path, answer: ModelResponse, message: str
) -> None:
    """A model that never answers through the output tool, or never sends valid tool arguments,
    stops the run with no proposal; refine then keeps its first proposal. The stop holds the class
    of the error and its message."""
    stopped = _investigate(git_repo, Script(answer))

    assert (stopped.reason, stopped.message.startswith(message)) == (
        "UnexpectedModelBehavior",
        True,
    )


def test_a_stop_gives_the_first_line_of_the_message_and_none_of_the_body(git_repo: Path) -> None:
    """The `body` of the error and the later lines of its message can quote the reply, so a stop
    holds neither; a token in the first line is masked."""
    token = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
    message = f"The reply held {token} in it.\ninput_value=MODEL-TEXT"
    script = Script(UnexpectedModelBehavior(message, body="MODEL-TEXT"))

    stopped = _investigate(git_repo, script)

    assert (stopped.reason, token in stopped.message, "MODEL-TEXT" in stopped.message) == (
        "UnexpectedModelBehavior",
        False,
        False,
    )
    assert stopped.message.startswith("The reply held ")


def test_a_long_message_is_cut(git_repo: Path) -> None:
    """A message longer than the limit is cut to the limit."""
    stopped = _investigate(git_repo, Script(UnexpectedModelBehavior("x" * 5000)))

    assert len(stopped.message) == CONST_ROADMAP_RUN_ERROR_CHARS


def test_a_reply_that_repeats_a_tool_call_id_leaves_its_id_out_of_the_stop(
    git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """pydantic-ai puts the `tool_call_id` of the reply, which the model chose, in the message of
    this error, so the stop keeps the text before it only."""
    twice = [ToolCallPart("list_files", {"path": "."}, tool_call_id="MODEL-sk-ABCDEF")] * 2

    with caplog.at_level(logging.WARNING):
        stopped = _investigate(git_repo, Script(ModelResponse(parts=twice)))

    assert (stopped.reason, "MODEL" in stopped.message + caplog.text) == (
        "UnexpectedModelBehavior",
        False,
    )


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "devops_cli.roadmap.refine"]


def test_a_stopped_run_with_a_question_open_is_a_job_failure(
    git_repo: Path, store: InMemoryRoadmapStore, caplog: pytest.LogCaptureFixture
) -> None:
    script = Script(UnexpectedModelBehavior("Exceeded maximum output retries (3)"))

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine"):
        plan = _round(store, git_repo, _FIRST, script)

    refined = plan.refined_items[0]
    assert (refined.next_step, plan.failed_items, _warnings(caplog)) == (
        NextStep.RETRY,
        [],
        [
            "Refine's investigation of #1 in example/roadmap stopped with no proposal "
            "(UnexpectedModelBehavior: Exceeded maximum output retries (3))."
        ],
    )


def test_the_warning_of_a_stopped_run_holds_no_text_of_the_model(
    git_repo: Path, store: InMemoryRoadmapStore, caplog: pytest.LogCaptureFixture
) -> None:
    message = "Invalid response from openai: 1 validation error\ninput_value=MODEL-TEXT"
    script = Script(UnexpectedModelBehavior(message, body="MODEL-TEXT"))

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine"):
        plan = _round(store, git_repo, _FIRST, script)

    assert (_warnings(caplog), "MODEL-TEXT" in render_refine_plan(plan) + caplog.text) == (
        [
            "Refine's investigation of #1 in example/roadmap stopped with no proposal "
            "(UnexpectedModelBehavior: Invalid response from openai)."
        ],
        False,
    )


def test_a_failed_model_call_of_the_investigation_names_the_repository_and_the_status(
    git_repo: Path, store: InMemoryRoadmapStore, caplog: pytest.LogCaptureFixture
) -> None:
    script = Script(ModelHTTPError(504, "model", body="MODEL-TEXT"))

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine"):
        plan = _round(store, git_repo, _FIRST, script)

    assert (_warnings(caplog), "MODEL-TEXT" in render_refine_plan(plan) + caplog.text) == (
        [
            "Refine skipped #1 in example/roadmap: its model call failed (AIClientError, "
            "LLM_INFERENCE_ERROR, timeout (HTTP 504 Gateway Timeout), 0 schema violation(s))."
        ],
        False,
    )


def test_each_request_of_the_run_streams(git_repo: Path) -> None:
    """The run streams each model request, so a long reply keeps the gateway tunnel open."""
    script = Script(call("list_files", directory="src"), _SETTLED)
    streamed: list[int] = []

    async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[Any]:
        streamed.append(len(messages))
        async for chunk in script.stream(messages, info):
            yield chunk

    def refuse(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise AssertionError("the run asked for a reply that does not stream")

    result = _investigate(git_repo, script, FunctionModel(refuse, stream_function=stream))

    assert (result, len(streamed)) == (_SETTLED, 2)


def test_a_tool_answers_each_failure_as_text(git_repo: Path) -> None:
    """A binary file, a file that is not UTF-8 and an argument with a NUL byte get a plain answer,
    so no argument can stop the run."""
    (git_repo / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    (git_repo / "notes.txt").write_bytes("caf\xe9 au lait\n".encode("latin-1"))
    _git(git_repo, "add", "-A")
    _git(git_repo, "commit", "-q", "-m", "files")
    tools = InvestigationTools(source=git_repo, sha=inspect_checkout(git_repo, REPO))

    assert (
        tools.read_file("logo.png"),
        tools.read_file("notes.txt"),
        tools.search_code("caf"),
        tools.search_code("a\x00b"),
        tools.read_file("a\x00.txt"),
    ) == (
        error_answer("The file logo.png is binary."),
        ok_answer("1: caf\ufffd au lait"),
        ok_answer("notes.txt:1:caf\ufffd au lait"),
        empty_answer("No match."),
        error_answer("The commit holds no file a\x00.txt."),
    )


@pytest.mark.usefixtures("wide_window")
def test_the_function_tools_go_when_too_few_tool_calls_are_left(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """A model that makes six calls in each turn gets no function tool once fewer calls are left
    than one turn can make, and its next reply, the proposal, ends the run inside the budget."""
    six = ModelResponse(
        parts=[ToolCallPart(tool_name="read_file", args={"path": "../x"}) for _ in range(6)]
    )
    script = Script(six, without_tools=_SETTLED)

    plan = _round(store, git_repo, _FIRST, script)

    turns = CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS // 6 + 1
    calls_left = [
        CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS - 6 * turn for turn in range(turns)
    ]
    assert (
        plan.refined_items[0].next_step,
        [len(offered) for offered in script.tools_offered],
    ) == (
        NextStep.READY,
        [3 if left >= CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS else 0 for left in calls_left],
    )


def test_a_round_on_a_public_repository_with_a_key_settles_a_fact_from_the_web(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    web: WebFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With web search on, the key reaches the tools, and a fact sourced by a URL that the search
    returned validates."""
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config(firecrawl={"api_key": "fc-test"})
    store.seed_visibility(is_private=False)
    url = "https://example.com/gitleaks"
    result = {"title": "Gitleaks", "url": url, "description": "Scans a directory."}
    web.content(_FIRECRAWL_URL, json.dumps({"success": True, "data": {"web": [result]}}).encode())
    sourced = _OPEN_FACT.model_copy(update={"answer": "Yes.", "sources": [url]})
    script = Script(
        call("search_web", query="gitleaks scan a directory"),
        _FIRST.model_copy(update={"key_questions": [sourced]}),
    )

    plan = _round(store, git_repo, _FIRST, script)

    refined = plan.refined_items[0]
    assert (
        plan.web_search_off,
        "search_web" in script.tools_offered[0],
        refined.next_step,
        [qa.sources for qa in refined.proposal.key_questions],
    ) == (None, True, NextStep.READY, [[url]])


def _spend_rows(ledger: SpendLedger) -> Sequence[tuple[Any, ...]]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
        rows: Sequence[tuple[Any, ...]] = conn.execute(
            "SELECT request_type, stage, provider, server, prompt_tokens > 0, "
            "completion_tokens > 0 FROM ai_spend_records"
        ).fetchall()
    return rows


def test_the_runs_usage_reaches_the_spend_ledger_once(
    git_repo: Path, spend_ledger: SpendLedger
) -> None:
    _investigate(git_repo, Script(call("list_files", directory="src"), _SETTLED))

    assert _spend_rows(spend_ledger) == [("agent_run", "analysis", "function", "unknown", 1, 1)]


def test_a_gateway_models_run_is_recorded_under_the_gateway(
    git_repo: Path, spend_ledger: SpendLedger
) -> None:
    """A model the bridge sends to a gateway carries the gateway's URL, and its record names the
    provider `gateway` and the gateway's host, as `LLMClient`'s records do."""
    script = Script(_SETTLED)
    model = script.model()
    setattr(model, "served_by", "http://example.com:4000/v1")

    _investigate(git_repo, script, model)

    assert _spend_rows(spend_ledger) == [
        ("agent_run", "analysis", "gateway", "example.com:4000", 1, 1)
    ]


class _ShoutingTools:
    """A tool set that is not refine's: one tool, which the run offers to the model."""

    def shout(self, text: str) -> str:
        """Answer the text in capitals.

        Args:
            text: The text to answer.
        """
        return text.upper()

    def tools(self) -> list[Tool[None]]:
        return [Tool(self.shout, takes_ctx=False)]


def test_the_alternatives_tools_run_in_the_same_agent_run() -> None:
    """`investigate` runs any set of tools, not only refine's: the model calls the tool of the
    set, and the run ends with the reply of its output type (#2650)."""
    script = Script(call("shout", text="hello"), _SETTLED)

    result = investigate(
        script.model(), "Instructions.", "{}", _ShoutingTools(), RefinementProposal
    )

    assert (result, script.tool_returns(), script.tools_offered[0]) == (
        _SETTLED,
        ["HELLO"],
        ["shout"],
    )


class _BlankTools:
    """A set of one tool that answers with text of white space only and sets no outcome."""

    def blank(self) -> str:
        """Answer with white space."""
        return "  \n"

    def tools(self) -> list[Tool[None]]:
        return [Tool(self.blank, takes_ctx=False)]


def test_an_answer_with_no_mark_and_no_text_is_empty_and_an_answer_with_text_is_ok() -> None:
    """A tool that sets no outcome gives `ok`, or `empty` when the model read no character."""
    trace = RunTrace()
    script = Script(call("blank"), _SETTLED)
    investigate(
        script.model(), "Instructions.", "{}", _BlankTools(), RefinementProposal, trace=trace
    )
    shout = RunTrace()
    investigate(
        Script(call("shout", text="hi"), _SETTLED).model(),
        "Instructions.",
        "{}",
        _ShoutingTools(),
        RefinementProposal,
        trace=shout,
    )

    assert (
        [(c.outcome, c.chars) for c in trace.tool_calls],
        [(c.outcome, c.chars) for c in shout.tool_calls],
    ) == (
        [(ToolOutcome.EMPTY, 3)],
        [(ToolOutcome.OK, 2)],
    )


def _run(
    git_repo: Path, script: Script, *, limits: UsageLimits | None = None, **options: Any
) -> Any:
    """One investigation of `RefinementProposal` with the limits and options of a caller that is
    not refine, as the stage job gives them (#3037)."""
    tools = InvestigationTools(source=git_repo, sha=inspect_checkout(git_repo, REPO))
    return investigate(
        script.model(), "Instructions.", "{}", tools, RefinementProposal, limits=limits, **options
    )


def _limits(*, tool_calls: int = 6, output_tokens: int | None = None) -> UsageLimits:
    return UsageLimits(
        request_limit=20, tool_calls_limit=tool_calls, output_tokens_limit=output_tokens
    )


def _read(path: str = "../x") -> ModelResponse:
    return call("read_file", path=path)


def test_a_reply_with_more_calls_than_are_left_stops_the_run_and_names_the_limit(
    git_repo: Path,
) -> None:
    seven = ModelResponse(parts=[ToolCallPart(tool_name="read_file", args={"path": "../x"})] * 7)

    stopped = _run(git_repo, Script(seven), limits=_limits(tool_calls=6))

    assert (stopped.reason, "tool_calls_limit" in stopped.message, stopped.schema_broken) == (
        "UsageLimitExceeded",
        True,
        False,
    )


def test_the_request_after_the_third_call_offers_no_tool_when_six_calls_are_allowed(
    git_repo: Path,
) -> None:
    script = Script(_read(), without_tools=_SETTLED)

    result = _run(git_repo, script, limits=_limits(tool_calls=6))

    assert (result, [len(offered) for offered in script.tools_offered]) == (_SETTLED, [3, 3, 3, 0])


def test_a_run_that_passes_the_output_token_limit_stops_and_names_it(git_repo: Path) -> None:
    wordy = call("read_file", path="../" + "word " * 40)

    stopped = _run(git_repo, Script(wordy), limits=_limits(tool_calls=30, output_tokens=10))

    assert (stopped.reason, "output_tokens_limit" in stopped.message, stopped.schema_broken) == (
        "UsageLimitExceeded",
        True,
        False,
    )


_BROKEN = call("final_result", nothing="here")


def test_a_reply_that_breaks_the_schema_goes_back_once_with_one_output_retry(
    git_repo: Path,
) -> None:
    result = _run(git_repo, Script(_BROKEN, _SETTLED), output_retries=1)

    assert result == _SETTLED


def test_a_second_reply_that_breaks_the_schema_stops_the_run_with_one_output_retry(
    git_repo: Path,
) -> None:
    stopped = _run(git_repo, Script(_BROKEN), output_retries=1)

    assert (stopped.reason, stopped.message, stopped.schema_broken) == (
        "UnexpectedModelBehavior",
        "Exceeded maximum output retries (1)",
        True,
    )


@pytest.mark.parametrize("gone_calls", [1, 2])
def test_a_call_to_a_tool_that_is_gone_gets_a_retry_and_the_run_goes_on(
    git_repo: Path, gone_calls: int
) -> None:
    """Once fewer than four calls are left the request offers no tool. Up to two calls to a tool
    in such a request get a retry prompt; a valid plan after them ends the run."""
    replies = [_read()] * 3 + [_read()] * gone_calls + [_SETTLED]

    result = _run(git_repo, Script(*replies), limits=_limits(tool_calls=6))

    assert result == _SETTLED


def test_a_third_call_to_a_tool_that_is_gone_stops_the_run_and_it_is_no_budget_limit(
    git_repo: Path,
) -> None:
    replies = [_read()] * 6 + [_SETTLED]

    stopped = _run(git_repo, Script(*replies), limits=_limits(tool_calls=6))

    assert (
        stopped.reason,
        stopped.message.startswith("Tool <text> exceeded max retries count of 2."),
        stopped.schema_broken,
    ) == ("UnexpectedModelBehavior", True, False)


def test_a_run_with_a_trace_keeps_its_calls_and_counts(git_repo: Path) -> None:
    trace = RunTrace()

    result = _run(
        git_repo, Script(_read("src/sample.py"), _read("src/other.py"), _SETTLED), trace=trace
    )

    assert (result, [(c.name, c.argument) for c in trace.tool_calls], trace.requests) == (
        _SETTLED,
        [("read_file", '{"path":"src/sample.py"}'), ("read_file", '{"path":"src/other.py"}')],
        3,
    )


def test_a_stopped_run_keeps_its_trace(git_repo: Path) -> None:
    trace = RunTrace()

    stopped = _run(git_repo, Script(_read(), _BROKEN), output_retries=1, trace=trace)

    assert (stopped.schema_broken, len(trace.tool_calls), trace.requests) == (True, 1, 3)


# ── The limit that ends the tools of a run (#3240) ────────────────────────────────────────────


def test_a_run_that_spends_its_call_budget_names_the_calls_limit_and_counts_a_late_call_as_an_error(
    git_repo: Path,
) -> None:
    """Six calls leave room for three turns of calls, so the fourth request offers no tool. The model
    calls a tool anyway, and the run takes that call as an error with no answer."""
    trace = RunTrace()
    read = _read("src/sample.py")

    result = _run(
        git_repo,
        Script(read, read, read, read, _SETTLED),
        limits=_limits(tool_calls=6),
        trace=trace,
    )

    assert (result, trace.limit, [(c.outcome, c.chars is None) for c in trace.tool_calls]) == (
        _SETTLED,
        RunLimit.CALLS,
        [(ToolOutcome.OK, False)] * 3 + [(ToolOutcome.ERROR, True)],
    )


def test_a_run_that_spends_its_requests_names_the_requests_limit(git_repo: Path) -> None:
    trace = RunTrace()
    script = Script(_read("src/sample.py"), without_tools=_SETTLED)

    result = _run(
        git_repo,
        script,
        limits=UsageLimits(request_limit=4, tool_calls_limit=30),
        trace=trace,
    )

    assert (result, trace.limit, [len(offered) for offered in script.tools_offered]) == (
        _SETTLED,
        RunLimit.REQUESTS,
        [3, 3, 3, 0],
    )


def test_a_run_that_fills_the_window_names_the_window_limit(git_repo: Path) -> None:
    trace = RunTrace()
    wordy = call("read_file", path="../" + "word " * 300)

    result = _run(git_repo, Script(wordy, without_tools=_SETTLED), window=1000, trace=trace)

    assert (result, trace.limit) == (_SETTLED, RunLimit.WINDOW)


def test_a_reply_over_the_call_limit_names_the_calls_limit_and_leaves_each_call_with_no_answer(
    git_repo: Path,
) -> None:
    """The hook flags the requests and the window before they can stop a run, so a hard stop by
    the call limit with no earlier limit is one reply over the call budget."""
    trace = RunTrace()
    seven = ModelResponse(parts=[ToolCallPart(tool_name="read_file", args={"path": "../x"})] * 7)

    stopped = _run(git_repo, Script(seven), limits=_limits(tool_calls=6), trace=trace)

    assert (
        stopped.reason,
        trace.limit,
        [(c.outcome, c.chars) for c in trace.tool_calls],
    ) == ("UsageLimitExceeded", RunLimit.CALLS, [(ToolOutcome.ERROR, None)] * 7)


def test_a_run_that_ends_on_no_limit_names_none(git_repo: Path) -> None:
    trace = RunTrace()

    result = _run(git_repo, Script(_read("src/sample.py"), _SETTLED), trace=trace)

    assert (result, trace.limit) == (_SETTLED, None)


def test_a_run_with_no_limits_keeps_the_limits_and_retries_of_refine(git_repo: Path) -> None:
    script = Script(_read(), without_tools=_SETTLED)

    result = _run(git_repo, script)

    assert (result, len(script.seen)) == (
        _SETTLED,
        CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS,
    )


def test_a_web_search_adds_each_http_url_it_returns_and_cuts_its_answer(
    web: WebFake,
) -> None:
    found = [
        {"title": "Gitleaks", "url": "https://example.com/gitleaks", "description": "Scans."},
        {"title": "Local", "url": "file:///etc/passwd", "description": "Not a web page."},
    ]
    web.content(_FIRECRAWL_URL, json.dumps({"success": True, "data": {"web": found}}).encode())
    cited: set[str] = set()

    answer = cited_web_search("gitleaks", "fc-test", cited, results=5)

    assert (answer, cited) == (
        "Gitleaks\nhttps://example.com/gitleaks\nScans.\n\nLocal\nfile:///etc/passwd\nNot a web page.",
        {"https://example.com/gitleaks"},
    )
    assert json.loads(web.sent[0].content) == {"query": "gitleaks", "limit": 5}


def test_a_failed_web_search_answers_as_text(web: WebFake) -> None:
    cited: set[str] = set()

    answer = cited_web_search("gitleaks", "fc-test", cited, results=5)

    assert (answer, cited) == ("The search failed: HTTPStatusError.", set())
