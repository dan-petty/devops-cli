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
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.usage import UsageLimits

from devops_cli.ai.client.models import (
    AIClientError,
    AICredentialsError,
    StructuredOutputValidationError,
)
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config import constants, settings
from devops_cli.config.constants import CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS
from devops_cli.config.defaults import DEFAULT_ROADMAP_STAGE_MAX_TOOL_CALLS, StageToolset
from devops_cli.config.settings import (
    RoadmapConfig,
    RoadmapMcpConfig,
    RoadmapStageConfig,
    Settings,
)
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.agent_run import RunLimit, RunTrace, ToolCallRecord, ToolOutcome
from devops_cli.roadmap.refine.refine_investigation import tokens_of
from devops_cli.roadmap.stage.stage_change import StageProposal, StageSplit
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient
from devops_cli.roadmap.stage.stage_tools import StageTools, with_call_budget
from devops_cli.roadmap.stage.stage_verify import Verification
from devops_cli.roadmap.tool_metrics import end_run
from devops_cli.telemetry.instruments import (
    ROADMAP_TOOL_ANSWER_CHARS,
    ROADMAP_TOOL_CALLS_PER_RUN,
    ROADMAP_TOOL_CALLS_TOTAL,
    ROADMAP_TOOL_CUTS_TOTAL,
    ROADMAP_TOOL_LIMIT_HITS_TOTAL,
)
from tests.support.builders import make_stage_proposal
from tests.support.length_stop import length_stopped_model
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.support.fakes.http import WebFake
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
_RESEARCH_TOOLS = [*_EXTENDED_TOOLS, "search_web"]
_PLAN = make_stage_proposal()
# The limits of the runs that spend their call budget (#4688): a run spends it in a few requests,
# and the request limit comes after the call budget.
_CALLS = 8
_SMALL_LIMITS = UsageLimits(request_limit=12, tool_calls_limit=_CALLS)
# The calls after which a request offers no tool: fewer than a turn of calls is left.
_LAST_WITH_TOOLS = _CALLS - CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS + 1


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


def _limited_client(checkout: tuple[Path, str], script: Script) -> ToolboxClient:
    source, sha = checkout
    return ToolboxClient(
        script.model(), _Inner(), source, sha, toolset="base", usage_limits=_SMALL_LIMITS
    )


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
        * (DEFAULT_ROADMAP_STAGE_MAX_TOOL_CALLS + 1)
    )

    with pytest.raises(RoadmapStageError, match="tool_calls_limit"):
        _plan(_client(checkout, Script(too_many)))


def test_the_request_after_the_last_call_that_leaves_a_turn_offers_no_tool(
    checkout: tuple[Path, str],
) -> None:
    script = Script(_read(), without_tools=_PLAN)

    plan = _plan(_limited_client(checkout, script))

    offered = [len(tools) for tools in script.tools_offered]
    assert (plan, offered) == (_PLAN, [9] * _LAST_WITH_TOOLS + [0])


@pytest.mark.parametrize("gone_calls", [1, 2])
def test_a_call_to_a_tool_that_is_gone_gets_a_retry_and_the_plan_stands(
    checkout: tuple[Path, str], gone_calls: int
) -> None:
    script = Script(*([_read()] * (_LAST_WITH_TOOLS + gone_calls)), _PLAN)

    assert _plan(_limited_client(checkout, script)) == _PLAN


def test_a_third_call_to_a_tool_that_is_gone_fails_the_run_with_the_retry_limit(
    checkout: tuple[Path, str],
) -> None:
    script = Script(*([_read()] * _CALLS), _PLAN)

    with pytest.raises(RoadmapStageError) as caught:
        _plan(_limited_client(checkout, script))

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


def test_a_reply_cut_by_the_output_token_limit_raises_an_error_that_names_the_limit(
    checkout: tuple[Path, str], web: WebFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plan reply that the output token limit cuts holds no part. The error is no schema
    failure, so the stage does not report it as "0 schema violation(s)" (#4220)."""
    model, sent = length_stopped_model(web, monkeypatch)
    source, sha = checkout
    client = ToolboxClient(model, _Inner(), source, sha)

    with pytest.raises(RoadmapStageError) as raised:
        _plan(client)

    message = str(raised.value)
    assert not isinstance(raised.value, StructuredOutputValidationError)
    assert message.count("output token limit") == 1
    assert message.count("max_tokens") == 1
    assert message.count("schema violation") == 0
    assert len(sent) == 1


def test_a_review_reply_cut_by_the_output_token_limit_raises_the_same_error(
    checkout: tuple[Path, str], web: WebFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review run of a plan names the output token limit too (#4220)."""
    model, _sent = length_stopped_model(web, monkeypatch)
    source, sha = checkout
    client = ToolboxClient(model, _Inner(), source, sha)

    with pytest.raises(RoadmapStageError) as raised:
        client.chat_structured("System.", "{}", Verification, max_retries=1)

    assert not isinstance(raised.value, StructuredOutputValidationError)
    assert str(raised.value).count("output token limit") == 1


@pytest.mark.parametrize("tool", ["final_result", "search_code"])
def test_a_tool_call_with_invalid_arguments_raises_an_error_that_names_the_cause(
    checkout: tuple[Path, str], tool: str
) -> None:
    """The gateway joined the arguments of two calls into one JSON text that does not parse. The
    run stops and the error says so: it is no schema failure with a count of 0 violations, and
    no retry limit of a tool (#4228)."""
    joined = ModelResponse(parts=[ToolCallPart(tool, '{"query": "alpha"}{"query": "beta"}')])
    client = _client(checkout, Script(joined))

    with pytest.raises(RoadmapStageError) as raised:
        _plan(client)

    message = str(raised.value)
    assert not isinstance(raised.value, StructuredOutputValidationError)
    assert message.count("invalid arguments") == 1
    assert message.count("schema violation") == 0


def test_a_review_run_with_invalid_arguments_raises_the_same_error(
    checkout: tuple[Path, str],
) -> None:
    """The review run of a plan names the invalid arguments too (#4228)."""
    joined = ModelResponse(parts=[ToolCallPart("final_result", '{"a": 1}{"b": 2}')])
    client = _client(checkout, Script(joined))

    with pytest.raises(RoadmapStageError) as raised:
        client.chat_structured("System.", "{}", Verification, max_retries=1)

    assert not isinstance(raised.value, StructuredOutputValidationError)
    assert str(raised.value).count("invalid arguments") == 1


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
    prompt = with_call_budget(load_task_prompt("roadmap_stage_tools.md"))
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
    window = 45000
    script = Script(_read("src/big.py"), without_tools=_PLAN, reports_input=True)
    client = ToolboxClient(script.model(), _Inner(), source, sha, window=window)

    plan = _plan(client)

    offered = [len(tools) for tools in script.tools_offered]
    assert (plan, offered[0], offered[-1], 1 < len(offered) < 27) == (
        _PLAN,
        len(_EXTENDED_TOOLS),
        0,
        True,
    )
    assert tokens_of(script.seen[-1]) < window


def test_a_plan_run_whose_tools_the_window_ends_too_soon_fails_and_names_the_window_setting(
    checkout: tuple[Path, str],
) -> None:
    """The window of 12000 tokens ends the tools after fewer calls than the minimum. The run gives
    a valid plan, and the error is still the window and not a fault of the plan (#3880)."""
    source, sha = _big_file_checkout(checkout)
    script = Script(_read("src/big.py"), without_tools=_PLAN, reports_input=True)
    client = ToolboxClient(script.model(), _Inner(), source, sha, window=12000)

    with pytest.raises(RoadmapStageError) as raised:
        _plan(client)

    (trace,) = client.traces
    assert (trace.limit, len(trace.tool_calls) < constants.CONST_ROADMAP_STAGE_MIN_TOOL_CALLS) == (
        RunLimit.WINDOW,
        True,
    )
    assert all(
        text in str(raised.value)
        for text in ("12000", "ai.tasks.stage.context_window", "ai.tasks.analysis.context_window")
    )


def test_a_plan_run_whose_window_ends_the_tools_after_the_minimum_calls_gives_its_plan(
    checkout: tuple[Path, str],
) -> None:
    source, sha = _big_file_checkout(checkout)
    script = Script(_read("src/big.py"), without_tools=_PLAN, reports_input=True)
    client = ToolboxClient(script.model(), _Inner(), source, sha, window=45000)

    plan = _plan(client)

    (trace,) = client.traces
    assert (
        plan,
        trace.limit,
        len(trace.tool_calls) >= constants.CONST_ROADMAP_STAGE_MIN_TOOL_CALLS,
    ) == (
        _PLAN,
        RunLimit.WINDOW,
        True,
    )


def test_a_review_run_whose_tools_the_window_ends_too_soon_fails_and_names_the_review_window(
    checkout: tuple[Path, str],
) -> None:
    """A review that read almost none of the code gives no findings that a person can trust, and a
    plan with no finding would stage as clean. So the run fails the item, and the error names the
    window of the review and not the window of the planner (#3911)."""
    source, sha = _big_file_checkout(checkout)
    script = Script(
        _read("src/big.py"), without_tools=Verification(findings=[]), reports_input=True
    )
    client = ToolboxClient(script.model(), _Inner(), source, sha, window=12000)

    with pytest.raises(RoadmapStageError) as raised:
        client.chat_structured("System.", "{}", Verification, max_retries=1)

    message = str(raised.value)
    assert ("12000" in message, "ai.tasks.verification.context_window" in message) == (True, True)
    assert "ai.tasks.stage.context_window" not in message


def test_a_review_run_whose_window_ends_the_tools_after_the_minimum_calls_gives_its_findings(
    checkout: tuple[Path, str],
) -> None:
    source, sha = _big_file_checkout(checkout)
    verdict = Verification(findings=[])
    script = Script(_read("src/big.py"), without_tools=verdict, reports_input=True)
    client = ToolboxClient(script.model(), _Inner(), source, sha, window=45000)

    result = client.chat_structured("System.", "{}", Verification, max_retries=1)

    (trace,) = client.traces
    assert (
        result,
        trace.limit,
        len(trace.tool_calls) >= constants.CONST_ROADMAP_STAGE_MIN_TOOL_CALLS,
    ) == (verdict, RunLimit.WINDOW, True)


def test_the_trace_records_the_tools_offered_for_each_request(
    checkout: tuple[Path, str],
) -> None:
    source, sha = _big_file_checkout(checkout)
    script = Script(_read("src/big.py"), without_tools=_PLAN)
    client = ToolboxClient(
        script.model(), _Inner(), source, sha, window=45000, usage_limits=_SMALL_LIMITS
    )

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

    _plan(ToolboxClient(script.model(), _Inner(), source, sha, usage_limits=_SMALL_LIMITS))

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


def test_the_research_toolset_offers_thirteen_tools_and_its_prompt_says_when_to_search(
    checkout: tuple[Path, str],
) -> None:
    source, sha = checkout
    script = Script(_read(), _PLAN)
    client = ToolboxClient(script.model(), _Inner(), source, sha, toolset="research")

    _plan(client)

    request = script.seen[0][-1]
    assert isinstance(request, ModelRequest)
    instructions = request.instructions or ""
    assert (
        script.tools_offered[0],
        load_task_prompt("roadmap_stage_tools_research.md") in instructions,
    ) == (_RESEARCH_TOOLS, True)


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
        [name for name in _RESEARCH_TOOLS[len(_TOOLS) :] if name in instructions],
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


def test_a_call_records_the_outcome_that_its_tool_gave_and_the_length_of_its_answer(
    checkout: tuple[Path, str],
) -> None:
    script = Script(
        _read(),
        call("search_code", text="zzqq"),
        call("read_file", path="../x"),
        call("read_file"),
        _PLAN,
    )
    client = _client(checkout, script)

    _plan(client)

    (trace,) = client.traces
    returns = script.tool_returns()
    assert [(c.name, c.outcome, c.chars) for c in trace.tool_calls] == [
        ("read_file", ToolOutcome.OK, len(returns[0])),
        ("search_code", ToolOutcome.EMPTY, len("No match.")),
        ("read_file", ToolOutcome.ERROR, len("The path ../x is outside the repository.")),
        ("read_file", ToolOutcome.ERROR, None),
    ]


def test_the_size_of_an_answer_is_the_length_after_the_cut(checkout: tuple[Path, str]) -> None:
    source, sha = _big_file_checkout(checkout)
    script = Script(_read("src/big.py"), _PLAN)
    client = ToolboxClient(script.model(), _Inner(), source, sha)

    _plan(client)

    (record,) = client.traces[0].tool_calls
    file_size = len((source / "src" / "big.py").read_text(encoding="utf-8"))
    assert (record.chars == len(script.tool_returns()[0]), 0 < (record.chars or 0) < file_size) == (
        True,
        True,
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
_RUN = {"row": "stage", "toolset": "base"}


def test_a_run_counts_one_call_of_each_outcome_with_bounded_labels(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    client = _client(
        checkout,
        Script(_read(), call("search_code", text="zzqq"), call("read_file", path="../x"), _PLAN),
    )

    _plan(client)

    points = otlp.points(ROADMAP_TOOL_CALLS_TOTAL.name)
    assert {(a["tool"], a["outcome"]): value for a, value in points if value} == {
        ("read_file", "ok"): 1.0,
        ("search_code", "empty"): 1.0,
        ("read_file", "error"): 1.0,
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


def test_a_verification_run_counts_its_calls_in_its_own_row(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    script = Script(_read(), Verification(findings=[]))

    _client(checkout, script).chat_structured("System.", "{}", Verification, max_retries=1)

    points = otlp.points(ROADMAP_TOOL_CALLS_TOTAL.name)
    assert ({a["row"] for a, _ in points}, sum(value for _, value in points)) == (
        {"stage_verify"},
        1.0,
    )


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


def test_the_answer_histogram_observes_the_text_of_each_answer_and_none_for_a_call_with_no_answer(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    refused = "The path ../x is outside the repository."
    client = _client(
        checkout,
        Script(
            call("search_code", text="zzqq"),
            call("read_file", path="../x"),
            call("read_file"),
            _PLAN,
        ),
    )

    _plan(client)

    observed = [(a["tool"], value) for a, value in otlp.points(ROADMAP_TOOL_ANSWER_CHARS.name)]
    assert sorted(observed) == [
        ("read_file", float(len(refused))),
        ("search_code", float(len("No match."))),
    ]


def test_a_run_that_spends_its_call_budget_observes_its_calls_and_counts_the_calls_limit(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    _plan(_limited_client(checkout, Script(_read(), without_tools=_PLAN)))

    assert (
        otlp.points(ROADMAP_TOOL_CALLS_PER_RUN.name),
        otlp.points(ROADMAP_TOOL_LIMIT_HITS_TOTAL.name),
    ) == (
        [(_RUN, float(_LAST_WITH_TOOLS))],
        [({**_RUN, "limit": "calls"}, 1.0)],
    )


def test_a_run_that_fails_on_one_reply_over_the_call_limit_counts_one_hit_and_one_run(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    too_many = ModelResponse(
        parts=[ToolCallPart("read_file", {"path": "src/sample.py"})]
        * (DEFAULT_ROADMAP_STAGE_MAX_TOOL_CALLS + 1)
    )
    client = _client(checkout, Script(too_many))

    with pytest.raises(RoadmapStageError, match="tool_calls_limit"):
        _plan(client)

    assert [a["limit"] for a, _ in otlp.points(ROADMAP_TOOL_LIMIT_HITS_TOTAL.name)] == ["calls"]
    assert [value for _, value in otlp.points(ROADMAP_TOOL_CALLS_PER_RUN.name)] == [
        float(DEFAULT_ROADMAP_STAGE_MAX_TOOL_CALLS + 1)
    ]
    assert client.traces[0].limit is RunLimit.CALLS


def test_a_run_that_fills_the_window_counts_the_window_limit(
    checkout: tuple[Path, str], otlp: FakeCollector
) -> None:
    source, sha = _big_file_checkout(checkout)
    script = Script(_read("src/big.py"), without_tools=_PLAN, reports_input=True)

    _plan(ToolboxClient(script.model(), _Inner(), source, sha, window=45000, toolset="base"))

    assert [a["limit"] for a, _ in otlp.points(ROADMAP_TOOL_LIMIT_HITS_TOTAL.name)] == ["window"]


@pytest.mark.parametrize("limit", list(RunLimit))
def test_the_limit_label_of_a_run_is_one_of_the_three_limits(
    otlp: FakeCollector, limit: RunLimit
) -> None:
    trace = RunTrace(tool_calls=[ToolCallRecord("read_file", "{}", ToolOutcome.OK, 5)], limit=limit)

    end_run(trace, row="stage", toolset="base", finished=True)

    ((attributes, count),) = otlp.points(ROADMAP_TOOL_LIMIT_HITS_TOTAL.name)
    assert (attributes, count, limit.value in _LIMITS) == (
        {**_RUN, "limit": limit.value},
        1.0,
        True,
    )


def test_end_run_counts_one_cut_answer_and_no_whole_answer(otlp: FakeCollector) -> None:
    trace = RunTrace(
        tool_calls=[
            ToolCallRecord("read_file", "{}", ToolOutcome.OK, 5, cut="lines"),
            ToolCallRecord("read_file", "{}", ToolOutcome.OK, 5),
        ]
    )

    end_run(trace, row="stage", toolset="base", finished=True)

    assert otlp.points(ROADMAP_TOOL_CUTS_TOTAL.name) == [
        ({**_RUN, "tool": "read_file", "cap": "lines"}, 1.0)
    ]


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


def test_toolbox_client_initializes_mcp_when_stage_mcp_enabled(
    checkout: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, sha = checkout
    monkeypatch.setenv("DEVOPS_CLI_MCP_STAGE_TOKEN", "fake-token")
    settings = Settings(
        roadmap=RoadmapConfig(
            mcp=RoadmapMcpConfig(url="http://mcp-server:8000"),
            stage=RoadmapStageConfig(mcp=True),
        )
    )
    monkeypatch.setattr("devops_cli.roadmap.stage.stage_toolbox.load_settings", lambda: settings)
    client = ToolboxClient(
        Script(_PLAN).model(),
        _Inner(),
        source,
        sha,
    )
    assert client._mcp_toolset._target_url == "http://mcp-server:8000/planning/mcp"
    assert client._mcp_toolset._timeout_seconds == 30.0


def _broken_plan(*dropped: str, empty_changes: bool = True) -> ModelResponse:
    """A plan reply with one violation for each dropped key, and one more when the changes of its
    first group are empty."""
    plan = _PLAN.model_dump()
    for key in dropped:
        del plan[key]
    if empty_changes:
        plan["groups"] = [plan["groups"][0] | {"changes": []}, *plan["groups"][1:]]
    return call("final_result", **plan)


def _retry(*errors: dict[str, Any]) -> ModelRequest:
    """The request after a reply that broke the schema: pydantic-ai sends the errors back."""
    return ModelRequest(parts=[RetryPromptPart(content=list(errors), tool_name="final_result")])


def _error(loc: tuple[int | str, ...], message: str = "Field required") -> dict[str, Any]:
    return {"type": "missing", "loc": loc, "msg": message, "input": {}}


def test_a_reply_that_breaks_the_schema_twice_keeps_the_text_of_its_violations(
    checkout: tuple[Path, str],
) -> None:
    client = _client(checkout, Script(_broken_plan("why")))

    with pytest.raises(StructuredOutputValidationError) as caught:
        _plan(client)

    error = caught.value
    assert sorted((v.loc, v.type) for v in error.violation_texts) == [
        ("groups.0.changes", "too_short"),
        ("why", "missing"),
    ]
    assert (error.violations, error.stop_reason) == (2, "validation")
    assert client.traces[0].violation_texts == error.violation_texts


def test_a_reply_with_five_violations_keeps_three_texts_and_the_count_of_five(
    checkout: tuple[Path, str],
) -> None:
    client = _client(
        checkout, Script(_broken_plan("summary", "why", "what_changes", "existing_tool"))
    )

    with pytest.raises(StructuredOutputValidationError) as caught:
        _plan(client)

    assert (caught.value.violations, len(caught.value.violation_texts)) == (5, 3)


def test_a_reply_of_text_that_is_no_json_names_the_root_and_the_type_json_invalid(
    checkout: tuple[Path, str],
) -> None:
    client = _client(checkout, Script(ModelResponse(parts=[TextPart("I will write the plan.")])))

    with pytest.raises(StructuredOutputValidationError) as caught:
        _plan(client)

    assert [(v.loc, v.type) for v in caught.value.violation_texts] == [("root", "json_invalid")]
    assert caught.value.stop_reason == "validation"


def test_a_reply_that_calls_no_tool_of_the_run_raises_with_the_stop_reason_no_tool_call(
    checkout: tuple[Path, str],
) -> None:
    client = _client(checkout, Script(call("no_such_tool", path="src/sample.py")))

    with pytest.raises(StructuredOutputValidationError) as caught:
        _plan(client)

    assert (caught.value.violations, caught.value.violation_texts, caught.value.stop_reason) == (
        0,
        (),
        "no tool call",
    )


def test_the_trace_cuts_a_violation_message_at_200_characters() -> None:
    trace = RunTrace()

    trace.absorb([_retry(_error(("references", 0, "reason"), "m" * 300))], tools=[])

    assert [len(v.message) for v in trace.violation_texts] == [200]


def test_the_trace_keeps_three_texts_of_five_violations_and_the_count_of_five() -> None:
    errors = [_error(("references", index, "reason")) for index in range(5)]
    trace = RunTrace()

    trace.absorb([_retry(*errors)], tools=[])

    assert (trace.violations, [v.loc for v in trace.violation_texts]) == (
        5,
        ["references.0.reason", "references.1.reason", "references.2.reason"],
    )


def test_the_trace_masks_a_secret_in_a_violation_message() -> None:
    secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    trace = RunTrace()

    trace.absorb([_retry(_error(("references", 0, "reason"), f"bad value {secret}"))], tools=[])

    assert secret not in trace.violation_texts[0].message


def test_a_later_trace_with_no_violation_leaves_the_texts_of_an_earlier_one() -> None:
    broken = RunTrace()
    broken.absorb([_retry(_error(("a",)))], tools=[])

    total = RunTrace.combined([broken, RunTrace()])

    assert (total.violations, total.violation_texts) == (1, broken.violation_texts)


def test_a_violation_text_masks_and_cuts_each_of_its_fields() -> None:
    from devops_cli.ai.schema_reflection import ViolationText

    secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"

    text = ViolationText(loc=f"a.{secret}", type="t" * 300, message=f"{secret} " + "m" * 300)

    assert (secret in text.loc, len(text.type), len(text.message)) == (False, 200, 200)
    assert secret not in text.message


def _noticed(returns: list[str]) -> list[bool]:
    """Whether each tool answer ends with the notice to give the reply."""
    return [
        answer.rstrip().endswith(MESSAGES.roadmap.stage_calls_notice.format(calls=n))
        for n, answer in enumerate(returns, start=1)
    ]


def _call_budget(config: Callable[..., Path], plan: int, review: int = 60) -> None:
    """Set the notice of a plan run at call `plan` and of a review run at call `review`, with the
    advice at the same calls."""
    config(
        roadmap={
            "stage": {
                "plan_calls_advised": plan,
                "plan_calls_notice": plan,
                "review_calls_advised": review,
                "review_calls_notice": review,
            }
        }
    )


def test_the_answers_from_the_call_budget_of_a_plan_run_end_with_a_notice(
    checkout: tuple[Path, str], config: Callable[..., Path]
) -> None:
    _call_budget(config, 2)
    script = Script(_read(), _read(), _read(), _PLAN)

    _plan(_client(checkout, script))

    assert _noticed(script.tool_returns()) == [False, True, True]


def test_the_review_run_has_its_own_call_budget(
    checkout: tuple[Path, str], config: Callable[..., Path]
) -> None:
    _call_budget(config, 1, 3)
    script = Script(_read(), _read(), _read(), Verification(findings=[]))

    _client(checkout, script).chat_structured("System.", "{}", Verification, max_retries=1)

    assert _noticed(script.tool_returns()) == [False, False, True]


def test_a_new_run_starts_its_count_at_zero(
    checkout: tuple[Path, str], config: Callable[..., Path]
) -> None:
    _call_budget(config, 2)
    first = Script(_read(), _read(), _PLAN)
    client = _client(checkout, first)
    _plan(client)
    second = Script(_read(), _PLAN)
    again = ToolboxClient(second.model(), _Inner(), *checkout)

    _plan(again)

    assert (_noticed(first.tool_returns()), _noticed(second.tool_returns())) == (
        [False, True],
        [False],
    )


def test_the_prompts_name_the_budgets_of_the_settings(config: Callable[..., Path]) -> None:
    """The plan prompt and the review prompt name the call budget of `roadmap.stage` that the run
    reads (#4346, #5440)."""
    defaults = (
        with_call_budget(load_task_prompt("roadmap_stage_tools.md")),
        with_call_budget(load_task_prompt("roadmap_stage_verify_tools.md")),
    )
    config(
        roadmap={
            "stage": {
                "plan_calls_advised": 61,
                "plan_calls_notice": 81,
                "review_calls_advised": 82,
                "review_calls_notice": 121,
            }
        }
    )
    plan = with_call_budget(load_task_prompt("roadmap_stage_tools.md"))
    review = with_call_budget(load_task_prompt("roadmap_stage_verify_tools.md"))

    assert ["about 30 tool calls" in defaults[0], "From call number 40," in defaults[0]] == [
        True,
        True,
    ]
    assert ["about 40 tool calls" in defaults[1], "From call number 60," in defaults[1]] == [
        True,
        True,
    ]
    assert "about 61 tool calls" in plan
    assert "From call number 81," in plan
    assert "call a tool only to check what the problem names" in plan
    assert "about 82 tool calls" in review
    assert "From call number 121," in review
    assert "{{" not in plan + review


def test_a_toolbox_run_reads_its_call_limit_from_the_settings(
    checkout: tuple[Path, str], config: Callable[..., Path]
) -> None:
    """The client reads `roadmap.stage.max_tool_calls` when the round makes it (#5440)."""
    _call_budget(config, 5, 5)
    config(roadmap={"stage": {"max_tool_calls": 5}})
    too_many = ModelResponse(parts=[ToolCallPart("read_file", {"path": "src/sample.py"})] * 6)

    with pytest.raises(RoadmapStageError, match="tool_calls_limit"):
        _plan(_client(checkout, Script(too_many)))
