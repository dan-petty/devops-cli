"""Tests for the planner client that calls the tools (#3037, #3238): the run that offers the tools of
the toolbox, its budget, its trace and its errors. The runs of the budget and the trace use the
nine tools of the toolset `base`; the toolset tests use `extended`, the default.

pydantic-ai's `FunctionModel` answers each model request from a `Script`, so no test reaches a
model. The tools read a temporary git repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import BaseModel
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
)

from devops_cli.ai.client.models import (
    AIClientError,
    AICredentialsError,
    StructuredOutputValidationError,
)
from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config import settings
from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS,
    CONST_ROADMAP_STAGE_TOOL_MAX_CALLS,
)
from devops_cli.config.defaults import StageToolset
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.roadmap import stage_toolbox
from devops_cli.roadmap.agent_run import RunLimit, RunTrace, ToolCallRecord, ToolOutcome
from devops_cli.roadmap.stage_change import StageProposal, StageSplit
from devops_cli.roadmap.stage_toolbox import ToolboxClient
from devops_cli.roadmap.stage_tools import StageTools
from devops_cli.telemetry.instruments import (
    ROADMAP_TOOL_ANSWER_CHARS,
    ROADMAP_TOOL_CALLS_PER_RUN,
    ROADMAP_TOOL_CALLS_TOTAL,
    ROADMAP_TOOL_LIMIT_HITS_TOTAL,
)
from tests.support.builders import make_stage_proposal
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

_TOOLS = [
    "list_files",
    "read_file",
    "search_code",
    "git_log",
    "git_show",
    "file_symbols",
    "callers",
    "repo_map",
    "read_spec",
]
_EXTENDED_TOOLS = [*_TOOLS, "references", "read_issue", "find_issues"]
_PLAN = make_stage_proposal()
# The calls after which a request offers no tool: fewer than a turn of calls is left.
_LAST_WITH_TOOLS = (
    CONST_ROADMAP_STAGE_TOOL_MAX_CALLS - CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS + 1
)


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


class _Inner:
    """The client of the calls that use no tool: it records them and answers `StageSplit`."""

    def __init__(self) -> None:
        self.asked: list[type[BaseModel]] = []

    def chat_structured[M: BaseModel](
        self, system: str, prompt: str, schema: type[M], *, max_retries: int
    ) -> M:
        self.asked.append(schema)
        return schema.model_validate({"groups": [g.model_dump() for g in _PLAN.groups]})


@pytest.fixture
def checkout(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        _git(root, "config", key, value)
    _git(root, "config", "commit.gpgsign", "false")
    (root / "src" / "sample.py").write_text("def hello_world():\n    return 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root, _git(root, "rev-parse", "HEAD")


def _client(
    checkout: tuple[Path, str], script: Script, toolset: StageToolset = "base"
) -> ToolboxClient:
    source, sha = checkout
    return ToolboxClient(script.model(), _Inner(), source, sha, toolset=toolset)


def _plan(client: ToolboxClient) -> Any:
    return client.chat_structured("System.", "{}", StageProposal, max_retries=1)


def _read(path: str = "src/sample.py") -> ModelResponse:
    return call("read_file", path=path)


def test_a_plan_run_offers_the_nine_tools_and_returns_the_plan(
    checkout: tuple[Path, str],
) -> None:
    script = Script(_read(), _PLAN)

    plan = _plan(_client(checkout, script))

    assert (plan, script.tools_offered[0], script.tool_returns()[0].splitlines()[0]) == (
        _PLAN,
        _TOOLS,
        "1: def hello_world():",
    )


def test_the_split_call_goes_to_the_inner_client_with_no_tool(checkout: tuple[Path, str]) -> None:
    source, sha = checkout
    script = Script(_PLAN)
    inner = _Inner()
    client = ToolboxClient(script.model(), inner, source, sha)

    client.chat_structured("System.", "{}", StageSplit, max_retries=1)

    assert (inner.asked, script.seen, client.traces) == ([StageSplit], [], [])


def test_one_reply_over_the_call_limit_fails_the_run_and_names_the_limit(
    checkout: tuple[Path, str],
) -> None:
    too_many = ModelResponse(
        parts=[ToolCallPart("read_file", {"path": "src/sample.py"})]
        * (CONST_ROADMAP_STAGE_TOOL_MAX_CALLS + 1)
    )

    with pytest.raises(RoadmapStageError, match="tool_calls_limit"):
        _plan(_client(checkout, Script(too_many)))


def test_the_request_after_the_last_call_that_leaves_a_turn_offers_no_tool(
    checkout: tuple[Path, str],
) -> None:
    script = Script(_read(), without_tools=_PLAN)

    plan = _plan(_client(checkout, script))

    offered = [len(tools) for tools in script.tools_offered]
    assert (plan, offered) == (_PLAN, [9] * _LAST_WITH_TOOLS + [0])


@pytest.mark.parametrize("gone_calls", [1, 2])
def test_a_call_to_a_tool_that_is_gone_gets_a_retry_and_the_plan_stands(
    checkout: tuple[Path, str], gone_calls: int
) -> None:
    script = Script(*([_read()] * (_LAST_WITH_TOOLS + gone_calls)), _PLAN)

    assert _plan(_client(checkout, script)) == _PLAN


def test_a_third_call_to_a_tool_that_is_gone_fails_the_run_with_the_retry_limit(
    checkout: tuple[Path, str],
) -> None:
    script = Script(*([_read()] * CONST_ROADMAP_STAGE_TOOL_MAX_CALLS), _PLAN)

    with pytest.raises(RoadmapStageError) as caught:
        _plan(_client(checkout, script))

    message = str(caught.value)
    assert ("max retries count of 2" in message, "_limit" in message) == (True, False)


def test_the_output_tokens_of_a_run_have_no_limit_of_their_own(
    checkout: tuple[Path, str],
) -> None:
    """A reply of more than the old limit of 50,000 output tokens does not fail the run: the
    context window ends the tools of a run, and no count of output tokens does (#3206)."""
    wordy = call("read_file", path="../" + "word " * 50_100)
    client = _client(checkout, Script(wordy, _PLAN))

    assert (_plan(client), client.traces[0].output_tokens > 50_000) == (_PLAN, True)


def test_a_reply_that_breaks_the_schema_twice_raises_with_the_count_of_violations(
    checkout: tuple[Path, str],
) -> None:
    group = _PLAN.groups[0].model_dump() | {"changes": []}
    broken = call("final_result", **(_PLAN.model_dump() | {"groups": [group]}))
    client = _client(checkout, Script(broken))

    with pytest.raises(StructuredOutputValidationError) as caught:
        _plan(client)

    assert (caught.value.violations, len(client.traces), client.traces[0].violations) == (1, 1, 1)


def test_a_reply_that_breaks_the_schema_once_goes_back_and_the_second_stands(
    checkout: tuple[Path, str],
) -> None:
    group = _PLAN.groups[0].model_dump() | {"changes": []}
    broken = call("final_result", **(_PLAN.model_dump() | {"groups": [group]}))

    assert _plan(_client(checkout, Script(broken, _PLAN))) == _PLAN


def test_the_system_text_holds_the_tools_prompt_and_it_names_every_tool(
    checkout: tuple[Path, str],
) -> None:
    script = Script(_PLAN)

    _plan(_client(checkout, script))

    request = script.seen[0][-1]
    assert isinstance(request, ModelRequest)
    prompt = load_task_prompt("roadmap_stage_tools.md")
    assert (
        (request.instructions or "").startswith("System."),
        prompt in (request.instructions or ""),
        [name for name in _TOOLS if f"`{name}`" not in prompt],
    ) == (True, True, [])


def test_the_tools_prompt_names_exactly_the_tools_of_the_toolbox(
    checkout: tuple[Path, str],
) -> None:
    source, sha = checkout
    base = [tool.name for tool in StageTools(source, sha, toolset="base").tools()]
    extended = [tool.name for tool in StageTools(source, sha).tools()]
    base_prompt = load_task_prompt("roadmap_stage_tools.md")
    extended_prompt = base_prompt + load_task_prompt("roadmap_stage_tools_extended.md")

    assert (
        base,
        extended,
        [name for name in base if f"`{name}`" not in base_prompt],
        [name for name in extended if f"`{name}`" not in extended_prompt],
        [name for name in extended if name not in base and f"`{name}`" in base_prompt],
    ) == (_TOOLS, _EXTENDED_TOOLS, [], [], [])


def test_a_failed_model_call_raises_the_clients_own_error(checkout: tuple[Path, str]) -> None:
    with pytest.raises(AIClientError) as caught:
        _plan(_client(checkout, Script(ModelHTTPError(500, "m"))))

    assert type(caught.value) is AIClientError


def test_a_refused_key_raises_the_credentials_error(checkout: tuple[Path, str]) -> None:
    with pytest.raises(AICredentialsError, match="refused the key"):
        _plan(_client(checkout, Script(ModelHTTPError(401, "m"))))


def test_the_client_keeps_one_trace_for_each_run(checkout: tuple[Path, str]) -> None:
    client = _client(checkout, Script(_read("src/sample.py"), _PLAN, _read("src/sample.py"), _PLAN))

    _plan(client)
    _plan(client)

    first, second = client.traces
    assert (
        [(c.name, c.argument) for c in first.tool_calls],
        [(c.name, c.argument) for c in second.tool_calls],
        first.requests,
        first.output_tokens > 0,
    ) == (
        [("read_file", '{"path":"src/sample.py"}')],
        [("read_file", '{"path":"src/sample.py"}')],
        2,
        True,
    )


def test_each_run_has_a_new_budget(checkout: tuple[Path, str]) -> None:
    """A first run of 20 calls does not shorten a second run of 20 calls: the second run still
    offers its tools for all its 20 calls."""
    script = Script(*([_read()] * 20), _PLAN, *([_read()] * 20), _PLAN)
    client = _client(checkout, script)

    _plan(client)
    _plan(client)

    assert (
        [len(tools) for tools in script.tools_offered],
        [len(trace.tool_calls) for trace in client.traces],
    ) == ([9] * 42, [20, 20])


def _big_file_checkout(checkout: tuple[Path, str]) -> tuple[Path, str]:
    """The checkout with one committed file whose first 120 lines fill a tool answer."""
    source, _ = checkout
    text = "".join(f"line {n} of the big file with words that a model reads\n" for n in range(300))
    (source / "src" / "big.py").write_text(text, encoding="utf-8")
    _git(source, "add", "-A")
    _git(source, "commit", "-q", "-m", "big")
    return source, _git(source, "rev-parse", "HEAD")


def test_a_window_takes_the_tools_away_before_the_messages_pass_it(
    checkout: tuple[Path, str],
) -> None:
    source, sha = _big_file_checkout(checkout)
    window = 12000
    script = Script(_read("src/big.py"), without_tools=_PLAN)
    client = ToolboxClient(script.model(), _Inner(), source, sha, window=window)

    plan = _plan(client)

    offered = [len(tools) for tools in script.tools_offered]
    last = ModelMessagesTypeAdapter.dump_json(script.seen[-1]).decode()
    assert (plan, offered[0], offered[-1], 1 < len(offered) < 27) == (
        _PLAN,
        len(_EXTENDED_TOOLS),
        0,
        True,
    )
    assert count_tokens(last) < window


def test_the_trace_records_the_tools_offered_for_each_request(
    checkout: tuple[Path, str],
) -> None:
    source, sha = _big_file_checkout(checkout)
    script = Script(_read("src/big.py"), without_tools=_PLAN)
    client = ToolboxClient(script.model(), _Inner(), source, sha, window=12000)

    _plan(client)

    (trace,) = client.traces
    assert [list(offered) for offered in trace.offered] == script.tools_offered
    assert (trace.offered[0], trace.offered[-1]) == (tuple(_EXTENDED_TOOLS), ())


def test_the_combined_trace_holds_the_offers_of_every_run() -> None:
    first, second = RunTrace(offered=[("read_file",)]), RunTrace(offered=[("read_file",), ()])

    assert RunTrace.combined([first, second]).offered == [("read_file",), ("read_file",), ()]


def test_a_run_with_no_window_keeps_the_tools_until_the_budget_takes_them(
    checkout: tuple[Path, str],
) -> None:
    source, sha = _big_file_checkout(checkout)
    script = Script(_read("src/big.py"), without_tools=_PLAN)

    _plan(ToolboxClient(script.model(), _Inner(), source, sha))

    assert [len(tools) for tools in script.tools_offered] == [
        len(_EXTENDED_TOOLS)
    ] * _LAST_WITH_TOOLS + [0]


def test_a_checkout_that_is_not_the_staged_commit_is_refused_before_a_run(
    checkout: tuple[Path, str],
) -> None:
    source, sha = checkout
    (source / "src" / "sample.py").write_text("changed = 1\n", encoding="utf-8")
    script = Script(_PLAN)

    with pytest.raises(RoadmapStageError, match="not committed"):
        ToolboxClient(script.model(), _Inner(), source, sha)

    assert script.seen == []


def test_the_default_toolset_offers_twelve_tools_and_its_prompt_says_when_to_call_three(
    checkout: tuple[Path, str],
) -> None:
    source, sha = checkout
    script = Script(_read(), _PLAN)
    client = ToolboxClient(script.model(), _Inner(), source, sha)

    _plan(client)

    request = script.seen[0][-1]
    assert isinstance(request, ModelRequest)
    instructions = request.instructions or ""
    assert (
        script.tools_offered[0],
        load_task_prompt("roadmap_stage_tools_extended.md") in instructions,
    ) == (_EXTENDED_TOOLS, True)


def test_the_base_toolset_offers_nine_tools_and_its_prompt_names_no_other(
    checkout: tuple[Path, str],
) -> None:
    script = Script(_read(), _PLAN)

    _plan(_client(checkout, script, "base"))

    request = script.seen[0][-1]
    assert isinstance(request, ModelRequest)
    instructions = request.instructions or ""
    assert (
        script.tools_offered[0],
        [name for name in _EXTENDED_TOOLS[len(_TOOLS) :] if name in instructions],
    ) == (_TOOLS, [])


def test_the_setting_chooses_the_toolset_when_the_caller_names_none(
    checkout: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, sha = checkout
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_TOOLSET", "base")
    settings.reset_settings_cache()
    script = Script(_read(), _PLAN)

    _plan(ToolboxClient(script.model(), _Inner(), source, sha))

    assert script.tools_offered[0] == _TOOLS


# ── The outcome, the size and the limit of each tool call (#3240) ─────────────


def _blank_git_log(self: StageTools, path: str = "") -> str:
    """List the newest commits that changed a path."""
    return "  \n"


_blank_git_log.__name__ = "git_log"


def test_a_call_records_its_outcome_and_the_length_of_its_answer(
    checkout: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(StageTools, "git_log", _blank_git_log)
    script = Script(_read(), call("git_log"), call("read_file"), _PLAN)
    client = _client(checkout, script)

    _plan(client)

    (trace,) = client.traces
    assert [(c.name, c.outcome, c.chars) for c in trace.tool_calls] == [
        ("read_file", ToolOutcome.OK, len(script.tool_returns()[0])),
        ("git_log", ToolOutcome.EMPTY, len("  \n")),
        ("read_file", ToolOutcome.ERROR, 0),
    ]


_SMALL_BUDGET = 12
_SMALL_LAST_WITH_TOOLS = _SMALL_BUDGET - CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS + 1


@pytest.fixture
def small_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """A budget of 12 tool calls, so a run that spends it makes few model requests."""
    monkeypatch.setattr(stage_toolbox, "CONST_ROADMAP_STAGE_TOOL_MAX_CALLS", _SMALL_BUDGET)


@pytest.mark.usefixtures("small_budget")
def test_a_call_to_a_tool_that_the_run_removed_is_an_error(checkout: tuple[Path, str]) -> None:
    client = _client(checkout, Script(*([_read()] * (_SMALL_LAST_WITH_TOOLS + 1)), _PLAN))

    _plan(client)

    outcomes = [record.outcome for record in client.traces[0].tool_calls]
    assert (outcomes[:-1] == [ToolOutcome.OK] * _SMALL_LAST_WITH_TOOLS, outcomes[-1]) == (
        True,
        ToolOutcome.ERROR,
    )


def test_the_size_of_an_answer_is_the_length_after_the_cut(checkout: tuple[Path, str]) -> None:
    source, sha = _big_file_checkout(checkout)
    script = Script(_read("src/big.py"), _PLAN)
    client = ToolboxClient(script.model(), _Inner(), source, sha)

    _plan(client)

    (record,) = client.traces[0].tool_calls
    file_size = len((source / "src" / "big.py").read_text(encoding="utf-8"))
    assert (record.chars == len(script.tool_returns()[0]), 0 < record.chars < file_size) == (
        True,
        True,
    )


@pytest.mark.usefixtures("small_budget")
def test_a_run_that_spends_its_call_budget_names_the_calls_limit(
    checkout: tuple[Path, str],
) -> None:
    client = _client(checkout, Script(_read(), without_tools=_PLAN))

    _plan(client)

    assert client.traces[0].limit is RunLimit.CALLS


def test_a_run_that_spends_its_requests_names_the_requests_limit(
    checkout: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(stage_toolbox, "CONST_ROADMAP_STAGE_MAX_REQUESTS", 4)
    client = _client(checkout, Script(_read(), without_tools=_PLAN))

    _plan(client)

    assert client.traces[0].limit is RunLimit.REQUESTS


def test_a_run_that_fills_the_window_names_the_window_limit(checkout: tuple[Path, str]) -> None:
    source, sha = _big_file_checkout(checkout)
    script = Script(_read("src/big.py"), without_tools=_PLAN)
    client = ToolboxClient(script.model(), _Inner(), source, sha, window=12000)

    _plan(client)

    assert client.traces[0].limit is RunLimit.WINDOW


def test_a_run_that_ends_on_no_limit_names_none(checkout: tuple[Path, str]) -> None:
    client = _client(checkout, Script(_read(), _PLAN))

    _plan(client)

    assert client.traces[0].limit is None


def _too_many_calls() -> ModelResponse:
    """One reply with one more parallel call than the small budget has."""
    return ModelResponse(
        parts=[ToolCallPart("read_file", {"path": "src/sample.py"})] * (_SMALL_BUDGET + 1)
    )


@pytest.mark.usefixtures("small_budget")
def test_one_reply_over_the_call_limit_names_the_calls_limit_and_marks_each_call_an_error(
    checkout: tuple[Path, str],
) -> None:
    client = _client(checkout, Script(_too_many_calls()))

    with pytest.raises(RoadmapStageError, match="tool_calls_limit"):
        _plan(client)

    (trace,) = client.traces
    assert (trace.limit, {c.outcome for c in trace.tool_calls}, len(trace.tool_calls)) == (
        RunLimit.CALLS,
        {ToolOutcome.ERROR},
        _SMALL_BUDGET + 1,
    )


def test_the_combined_trace_keeps_the_last_limit() -> None:
    window, calls = RunTrace(limit=RunLimit.WINDOW), RunTrace(limit=RunLimit.CALLS)

    assert (
        RunTrace.combined([window, calls]).limit,
        RunTrace.combined([calls, RunTrace()]).limit,
        RunTrace.combined([]).limit,
    ) == (RunLimit.CALLS, RunLimit.CALLS, None)


def test_the_tool_counts_give_the_calls_and_the_empty_answers_of_each_tool_by_name() -> None:
    def record(name: str, outcome: ToolOutcome) -> ToolCallRecord:
        return ToolCallRecord(name, "{}", outcome, 0)

    trace = RunTrace(
        tool_calls=[
            record("read_file", ToolOutcome.OK),
            record("list_files", ToolOutcome.EMPTY),
            record("read_file", ToolOutcome.ERROR),
        ]
    )

    assert trace.tool_counts() == {"list_files": (1, 1), "read_file": (2, 0)}


# ── The metrics of each plan run (#3240) ──────────────────────────────────────

_OUTCOMES = {"ok", "empty", "error"}
_LIMITS = {"calls", "requests", "window"}


def test_a_run_counts_one_call_of_each_outcome_with_bounded_labels(
    checkout: tuple[Path, str], monkeypatch: pytest.MonkeyPatch, otlp: FakeCollector
) -> None:
    monkeypatch.setattr(StageTools, "git_log", _blank_git_log)
    client = _client(checkout, Script(_read(), call("git_log"), call("read_file"), _PLAN))

    _plan(client)

    points = otlp.points(ROADMAP_TOOL_CALLS_TOTAL.name)
    assert {(a["tool"], a["outcome"]): value for a, value in points if value} == {
        ("read_file", "ok"): 1.0,
        ("read_file", "error"): 1.0,
        ("git_log", "empty"): 1.0,
    }
    assert [
        a
        for a, _ in points
        if set(a) != {"tool", "row", "toolset", "outcome"}
        or (a["row"], a["toolset"]) != ("stage", "base")
        or a["tool"] not in _TOOLS
        or a["outcome"] not in _OUTCOMES
    ] == []


def test_a_run_that_calls_no_tool_adds_zero_for_each_tool_of_its_toolset(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    _plan(_client(checkout, Script(_PLAN)))

    points = otlp.points(ROADMAP_TOOL_CALLS_TOTAL.name)
    assert (
        sorted(a["tool"] for a, _ in points),
        {value for _, value in points},
        {a["outcome"] for a, _ in points},
    ) == (sorted(_TOOLS), {0.0}, {"ok"})


def test_the_extended_toolset_adds_zero_for_its_twelve_tools(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    _plan(_client(checkout, Script(_PLAN), toolset="extended"))

    points = otlp.points(ROADMAP_TOOL_CALLS_TOTAL.name)
    assert (sorted(a["tool"] for a, _ in points), {a["toolset"] for a, _ in points}) == (
        sorted(_EXTENDED_TOOLS),
        {"extended"},
    )


def test_the_answer_histogram_observes_the_cut_length_and_not_the_file_length(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    source, sha = _big_file_checkout(checkout)
    script = Script(_read("src/big.py"), _PLAN)

    _plan(ToolboxClient(script.model(), _Inner(), source, sha, toolset="base"))

    file_size = len((source / "src" / "big.py").read_text(encoding="utf-8"))
    ((attributes, observed),) = otlp.points(ROADMAP_TOOL_ANSWER_CHARS.name)
    assert (attributes, observed == len(script.tool_returns()[0]), observed < file_size) == (
        {"tool": "read_file", "row": "stage", "toolset": "base"},
        True,
        True,
    )


def test_a_call_with_no_answer_adds_no_observation_to_the_answer_histogram(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    _plan(_client(checkout, Script(call("read_file"), _PLAN)))

    assert otlp.points(ROADMAP_TOOL_ANSWER_CHARS.name) == []


@pytest.mark.usefixtures("small_budget")
def test_a_run_that_spends_its_call_budget_observes_its_calls_and_counts_the_calls_limit(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    _plan(_client(checkout, Script(_read(), without_tools=_PLAN)))

    assert (
        otlp.points(ROADMAP_TOOL_CALLS_PER_RUN.name),
        otlp.points(ROADMAP_TOOL_LIMIT_HITS_TOTAL.name),
    ) == (
        [({"row": "stage", "toolset": "base"}, float(_SMALL_LAST_WITH_TOOLS))],
        [({"row": "stage", "toolset": "base", "limit": "calls"}, 1.0)],
    )


@pytest.mark.usefixtures("small_budget")
def test_a_run_that_fails_on_the_call_limit_counts_one_hit_and_one_run(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    with pytest.raises(RoadmapStageError, match="tool_calls_limit"):
        _plan(_client(checkout, Script(_too_many_calls())))

    assert [a["limit"] for a, _ in otlp.points(ROADMAP_TOOL_LIMIT_HITS_TOTAL.name)] == ["calls"]
    assert len(otlp.points(ROADMAP_TOOL_CALLS_PER_RUN.name)) == 1


def test_a_run_that_ends_on_no_limit_counts_no_hit(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    _plan(_client(checkout, Script(_read(), _PLAN)))

    assert (
        otlp.points(ROADMAP_TOOL_LIMIT_HITS_TOTAL.name),
        [value for _, value in otlp.points(ROADMAP_TOOL_CALLS_PER_RUN.name)],
    ) == ([], [1.0])


def test_a_run_that_fails_on_a_model_call_counts_its_calls_and_observes_no_run(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    with pytest.raises(AIClientError, match="model call failed"):
        _plan(_client(checkout, Script(_read(), ModelHTTPError(500, "m"))))

    points = otlp.points(ROADMAP_TOOL_CALLS_TOTAL.name)
    assert (
        otlp.points(ROADMAP_TOOL_CALLS_PER_RUN.name),
        {(a["tool"], a["outcome"]): value for a, value in points if value},
        len(points),
    ) == ([], {("read_file", "ok"): 1.0}, len(_TOOLS))


def test_the_limit_label_has_a_closed_set_of_values(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    source, sha = _big_file_checkout(checkout)
    script = Script(_read("src/big.py"), without_tools=_PLAN)

    _plan(ToolboxClient(script.model(), _Inner(), source, sha, window=12000, toolset="base"))

    limits = {a["limit"] for a, _ in otlp.points(ROADMAP_TOOL_LIMIT_HITS_TOTAL.name)}
    assert (limits <= _LIMITS, limits) == (True, {"window"})
