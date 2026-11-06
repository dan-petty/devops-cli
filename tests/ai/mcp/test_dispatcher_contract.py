"""Contract suite for the MCP dispatcher seam (`devops_cli.ai.mcp.dispatcher`) and `DispatcherFake` (#3760).

Each contract case runs against the fake (`mcp_dispatcher` fixture) and against
`InProcessDispatcher`, which runs the Typer app of devops-cli in the test process. The real side
starts no program and reaches no network: it runs help text, a bad option, an unknown command and
hidden commands that the test registers on the app. The cases after the contract hold the fake
alone: the record of calls, the scripted answers, the install and the reset.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pytest
import typer

from devops_cli.ai.mcp.dispatcher import (
    InProcessDispatcher,
    McpDispatcher,
    devops_sub_args,
    get_mcp_dispatcher,
    install_mcp_dispatcher,
    reset_mcp_dispatcher,
)
from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS
from devops_cli.exceptions import ValidationError
from devops_cli.main import app
from tests.support.fakes.mcp_dispatcher import DispatchCall, DispatcherFake

_MODES = ["fake", "real"]


def _dispatcher(request: pytest.FixtureRequest, mode: str) -> McpDispatcher:
    """The fake behind the `mcp_dispatcher` fixture, or the real in-process dispatcher."""
    if mode == "fake":
        fake: DispatcherFake = request.getfixturevalue("mcp_dispatcher")
        return fake
    return InProcessDispatcher()


@contextmanager
def _hidden_command(name: str, body: Callable[[], None]) -> Iterator[None]:
    """Register a hidden command on the app of devops-cli, and remove it at the end."""
    app.command(name=name, hidden=True)(body)
    try:
        yield
    finally:
        app.registered_commands = [c for c in app.registered_commands if c.name != name]


@pytest.mark.parametrize("mode", _MODES)
def test_a_command_that_succeeds_returns_exit_code_zero_and_its_output(
    request: pytest.FixtureRequest, mode: str
) -> None:
    dispatcher = _dispatcher(request, mode)
    if isinstance(dispatcher, DispatcherFake):
        dispatcher.answer("Usage: devops workspace")

    code, output = dispatcher.dispatch(["devops", "workspace", "-h"])

    assert (code, "Usage: devops workspace" in output) == (0, True)


@pytest.mark.parametrize("mode", _MODES)
def test_the_uv_run_prefix_and_the_bare_program_run_the_same_command(
    request: pytest.FixtureRequest, mode: str
) -> None:
    dispatcher = _dispatcher(request, mode)
    if isinstance(dispatcher, DispatcherFake):
        dispatcher.answer("Usage: devops workspace")

    answers = [
        dispatcher.dispatch(["uv", "run", "devops", "workspace", "-h"]),
        dispatcher.dispatch(["devops", "workspace", "-h"]),
    ]

    assert [(code, "Usage: devops workspace" in output) for code, output in answers] == [
        (0, True),
        (0, True),
    ]


@pytest.mark.parametrize("mode", _MODES)
def test_a_bad_option_returns_a_non_zero_exit_code_and_a_diagnostic(
    request: pytest.FixtureRequest, mode: str
) -> None:
    dispatcher = _dispatcher(request, mode)
    if isinstance(dispatcher, DispatcherFake):
        dispatcher.answer("No such option: --no-such-option", exit_code=2)

    code, output = dispatcher.dispatch(["devops", "workspace", "--no-such-option"])

    assert (code, "no-such-option" in output) == (2, True)


@pytest.mark.parametrize("mode", _MODES)
def test_an_unknown_command_returns_a_non_zero_exit_code_and_a_diagnostic(
    request: pytest.FixtureRequest, mode: str
) -> None:
    dispatcher = _dispatcher(request, mode)
    if isinstance(dispatcher, DispatcherFake):
        dispatcher.answer("No such command 'no-such-command'.", exit_code=2)

    code, output = dispatcher.dispatch(["devops", "no-such-command"])

    assert (code, "no-such-command" in output) == (2, True)


@pytest.mark.parametrize("mode", _MODES)
def test_a_command_that_prints_nothing_and_succeeds_returns_success(
    request: pytest.FixtureRequest, mode: str
) -> None:
    dispatcher = _dispatcher(request, mode)

    def silent() -> None:
        return None

    with _hidden_command("_test_silent_3760", silent):
        result = dispatcher.dispatch(["devops", "_test_silent_3760"])

    assert result == (0, "Success")


@pytest.mark.parametrize("mode", _MODES)
def test_a_command_that_prints_nothing_and_fails_returns_no_output_captured(
    request: pytest.FixtureRequest, mode: str
) -> None:
    dispatcher = _dispatcher(request, mode)
    if isinstance(dispatcher, DispatcherFake):
        dispatcher.answer(exit_code=1)

    def failing() -> None:
        raise typer.Exit(1)

    with _hidden_command("_test_failing_3760", failing):
        result = dispatcher.dispatch(["devops", "_test_failing_3760"])

    assert result == (1, "no output captured")


@pytest.mark.parametrize("mode", _MODES)
def test_a_command_that_outlasts_its_timeout_returns_exit_code_124_and_names_the_command(
    request: pytest.FixtureRequest, mode: str
) -> None:
    dispatcher = _dispatcher(request, mode)
    if isinstance(dispatcher, DispatcherFake):
        dispatcher.time_out()
    release = threading.Event()

    def hang() -> None:
        release.wait(10)

    try:
        with _hidden_command("_test_hang_3760", hang):
            code, output = dispatcher.dispatch(["devops", "_test_hang_3760"], timeout=0.1)
    finally:
        release.set()

    assert (code, "timed out after 0.1 seconds" in output, "_test_hang_3760" in output) == (
        124,
        True,
        True,
    )


@pytest.mark.parametrize("mode", _MODES)
@pytest.mark.parametrize(
    "argv",
    [["kubectl", "get", "pods"], ["uv", "pip", "list"], ["git", "status"], []],
    ids=["kubectl", "uv-pip", "git", "empty"],
)
def test_a_command_line_that_is_not_a_devops_one_is_refused_and_nothing_runs(
    request: pytest.FixtureRequest, mode: str, argv: list[str]
) -> None:
    dispatcher = _dispatcher(request, mode)

    with pytest.raises(ValidationError, match="not one"):
        dispatcher.dispatch(argv)

    if isinstance(dispatcher, DispatcherFake):
        assert dispatcher.calls == []


def test_the_arguments_after_devops_are_read_from_both_spellings() -> None:
    assert (
        devops_sub_args(["uv", "run", "devops", "config", "show"]),
        devops_sub_args(["devops", "repos", "list"]),
    ) == (["config", "show"], ["repos", "list"])


# ── The fake alone ───────────────────────────────────────────────────────────


def test_the_fake_records_each_call_with_its_timeout_and_environment(
    mcp_dispatcher: DispatcherFake,
) -> None:
    mcp_dispatcher.dispatch(["uv", "run", "devops", "ci", "--check"], timeout=30.0, env={"A": "b"})
    mcp_dispatcher.dispatch(["devops", "repos", "list"])

    assert mcp_dispatcher.calls == [
        DispatchCall(("uv", "run", "devops", "ci", "--check"), 30.0, {"A": "b"}),
        DispatchCall(("devops", "repos", "list"), DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS, None),
    ]
    assert (mcp_dispatcher.call_count, mcp_dispatcher.last.sub_args) == (2, ("repos", "list"))


def test_the_latest_answer_that_matches_wins_and_the_rest_fall_back_to_success(
    mcp_dispatcher: DispatcherFake,
) -> None:
    mcp_dispatcher.answer("any command")
    mcp_dispatcher.answer("pods listed", command=["k8s", "pods"])
    mcp_dispatcher.answer("no pods", exit_code=3, command=["k8s", "pods", "--bad"])

    assert [
        mcp_dispatcher.dispatch(["devops", "k8s", "pods"]),
        mcp_dispatcher.dispatch(["devops", "k8s", "pods", "--bad"]),
        mcp_dispatcher.dispatch(["devops", "k8s", "nodes"]),
    ] == [(0, "pods listed"), (3, "no pods"), (0, "any command")]


def test_a_command_with_no_answer_succeeds_with_the_success_text(
    mcp_dispatcher: DispatcherFake,
) -> None:
    assert mcp_dispatcher.dispatch(["devops", "ci"]) == (0, "Success")


def test_a_scripted_error_is_raised_by_the_dispatch_and_the_call_is_recorded(
    mcp_dispatcher: DispatcherFake,
) -> None:
    mcp_dispatcher.fail(RuntimeError("a handler ran"), command=["ci"])

    with pytest.raises(RuntimeError, match="a handler ran"):
        mcp_dispatcher.dispatch(["devops", "ci"])

    assert mcp_dispatcher.call_count == 1


def test_the_fixture_installs_the_fake_and_the_reset_brings_the_real_dispatcher_back(
    mcp_dispatcher: DispatcherFake,
) -> None:
    installed = get_mcp_dispatcher()
    reset_mcp_dispatcher()

    assert installed is mcp_dispatcher
    assert type(get_mcp_dispatcher()) is InProcessDispatcher


def test_a_dispatcher_installed_by_hand_is_the_one_the_getter_returns() -> None:
    fake = DispatcherFake()

    install_mcp_dispatcher(fake)

    assert get_mcp_dispatcher() is fake
