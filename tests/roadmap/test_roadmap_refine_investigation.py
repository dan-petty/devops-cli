"""Tests for refine's investigation (#2398): the read-only tools on the pinned commit, the
pydantic-ai run that settles a proposal's open questions, its budget, its errors and its spend.

pydantic-ai's `FunctionModel` answers each model request from a script, so no test reaches a
model. Firecrawl is answered at the HTTP edge by `stub_web`, and git runs on a temporary repository.
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
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from devops_cli.ai.client.models import AIClientError, AICredentialsError
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS,
    CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS,
    CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS,
    CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES,
    CONST_ROADMAP_RUN_ERROR_CHARS,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.refine import (
    AcceptanceCriterion,
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
from tests.support.scripted_model import Script, call
from tests.web_fakes import StubWeb

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


class _FirstPhase:
    """The proposal step's client: it answers every proposal request with `proposal`."""

    def __init__(self, proposal: RefinementProposal) -> None:
        self.proposal = proposal

    def chat_structured(self, system: str, prompt: str, schema: type[Any]) -> Any:
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


def test_a_turn_whose_calls_pass_the_budget_keeps_the_first_proposal(
    git_repo: Path, store: InMemoryRoadmapStore, caplog: pytest.LogCaptureFixture
) -> None:
    """One turn that asks for more calls than the budget holds ends the run; the item keeps its
    open question and waits on a person, and the log names the item."""
    calls = [
        ToolCallPart(tool_name="read_file", args={"path": "../outside.py"})
        for _ in range(CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS + 1)
    ]
    script = Script(ModelResponse(parts=calls))

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine"):
        plan = _round(store, git_repo, _FIRST, script)

    refined = plan.refined_items[0]
    assert (
        refined.next_step,
        refined.step_details,
        plan.failed_items,
        any("#1" in record.getMessage() for record in caplog.records),
    ) == (NextStep.PERSON, ("Where is the sample function? (missing verified source)",), [], True)


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
        "src/sample.py:1:def hello_world():",
        "No match.",
        "src/sample.py",
        "src",
        "2:     return 'hello'",
        "The commit holds no file src/missing.py.",
        "The path ../outside.py is outside the repository.",
        "The path /etc/hostname is outside the repository.",
    )


def test_web_search_is_absent_without_a_key(git_repo: Path) -> None:
    tools = InvestigationTools(source=git_repo, sha=inspect_checkout(git_repo, REPO))

    assert [tool.name for tool in tools.tools()] == ["search_code", "list_files", "read_file"]


def test_web_search_adds_each_url_and_stops_at_its_cap(git_repo: Path, stub_web: StubWeb) -> None:
    result = {"title": "Gitleaks", "url": "https://example.com/gitleaks", "description": "Scans."}
    reply = {"success": True, "data": {"web": [result]}}
    stub_web.content(_FIRECRAWL_URL, json.dumps(reply).encode())
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
        len(stub_web.sent),
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


def test_a_stopped_run_keeps_the_first_proposal(
    git_repo: Path, store: InMemoryRoadmapStore, caplog: pytest.LogCaptureFixture
) -> None:
    script = Script(UnexpectedModelBehavior("Exceeded maximum output retries (3)"))

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine"):
        plan = _round(store, git_repo, _FIRST, script)

    refined = plan.refined_items[0]
    assert (refined.next_step, plan.failed_items, _warnings(caplog)) == (
        NextStep.PERSON,
        [],
        [
            "Refine's investigation of #1 in example/roadmap stopped with no proposal "
            "(UnexpectedModelBehavior: Exceeded maximum output retries (3)); "
            "the item keeps its open questions."
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
            "(UnexpectedModelBehavior: Invalid response from openai); "
            "the item keeps its open questions."
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
        "The file logo.png is binary.",
        "1: caf\ufffd au lait",
        "notes.txt:1:caf\ufffd au lait",
        "No match.",
        "The commit holds no file a\x00.txt.",
    )


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

    calls_left = [CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS - 6 * turn for turn in range(4)]
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
    stub_web: StubWeb,
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
    stub_web.content(
        _FIRECRAWL_URL, json.dumps({"success": True, "data": {"web": [result]}}).encode()
    )
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


def test_a_web_search_adds_each_http_url_it_returns_and_cuts_its_answer(
    stub_web: StubWeb,
) -> None:
    found = [
        {"title": "Gitleaks", "url": "https://example.com/gitleaks", "description": "Scans."},
        {"title": "Local", "url": "file:///etc/passwd", "description": "Not a web page."},
    ]
    stub_web.content(_FIRECRAWL_URL, json.dumps({"success": True, "data": {"web": found}}).encode())
    cited: set[str] = set()

    answer = cited_web_search("gitleaks", "fc-test", cited, results=5)

    assert (answer, cited) == (
        "Gitleaks\nhttps://example.com/gitleaks\nScans.\n\nLocal\nfile:///etc/passwd\nNot a web page.",
        {"https://example.com/gitleaks"},
    )
    assert json.loads(stub_web.sent[0].content) == {"query": "gitleaks", "limit": 5}


def test_a_failed_web_search_answers_as_text(stub_web: StubWeb) -> None:
    cited: set[str] = set()

    answer = cited_web_search("gitleaks", "fc-test", cited, results=5)

    assert (answer, cited) == ("The search failed: HTTPStatusError.", set())
