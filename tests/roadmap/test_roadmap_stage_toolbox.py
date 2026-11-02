"""Tests for the planner client that calls the tools (#3037): the run that offers the nine tools of
the toolbox, its budget, its trace and its errors.

pydantic-ai's `FunctionModel` answers each model request from a `Script`, so no test reaches a
model. The tools read a temporary git repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart

from devops_cli.ai.client.models import (
    AIClientError,
    AICredentialsError,
    StructuredOutputValidationError,
)
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.roadmap.stage_change import StageProposal, StageSplit
from devops_cli.roadmap.stage_toolbox import ToolboxClient
from devops_cli.roadmap.stage_tools import StageTools
from tests.support.builders import make_stage_proposal
from tests.support.scripted_model import Script, call

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
_PLAN = make_stage_proposal()


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


def _client(checkout: tuple[Path, str], script: Script) -> ToolboxClient:
    source, sha = checkout
    return ToolboxClient(script.model(), _Inner(), source, sha)


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


def test_one_reply_with_31_calls_fails_the_run_and_names_the_limit(
    checkout: tuple[Path, str],
) -> None:
    thirty_one = ModelResponse(parts=[ToolCallPart("read_file", {"path": "src/sample.py"})] * 31)

    with pytest.raises(RoadmapStageError, match="tool_calls_limit"):
        _plan(_client(checkout, Script(thirty_one)))


def test_the_request_after_the_27th_call_offers_no_tool(checkout: tuple[Path, str]) -> None:
    script = Script(_read(), without_tools=_PLAN)

    plan = _plan(_client(checkout, script))

    offered = [len(tools) for tools in script.tools_offered]
    assert (plan, offered) == (_PLAN, [9] * 27 + [0])


@pytest.mark.parametrize("gone_calls", [1, 2])
def test_a_call_to_a_tool_that_is_gone_gets_a_retry_and_the_plan_stands(
    checkout: tuple[Path, str], gone_calls: int
) -> None:
    script = Script(*([_read()] * (27 + gone_calls)), _PLAN)

    assert _plan(_client(checkout, script)) == _PLAN


def test_a_third_call_to_a_tool_that_is_gone_fails_the_run_with_the_retry_limit(
    checkout: tuple[Path, str],
) -> None:
    script = Script(*([_read()] * 30), _PLAN)

    with pytest.raises(RoadmapStageError) as caught:
        _plan(_client(checkout, script))

    message = str(caught.value)
    assert ("max retries count of 2" in message, "_limit" in message) == (True, False)


def test_a_run_that_passes_the_output_token_limit_fails_and_names_it(
    checkout: tuple[Path, str],
) -> None:
    wordy = call("read_file", path="../" + "word " * 50_100)

    with pytest.raises(RoadmapStageError, match="output_tokens_limit"):
        _plan(_client(checkout, Script(wordy)))


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
    names = [tool.name for tool in StageTools(source, sha).tools()]

    assert names == _TOOLS


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
