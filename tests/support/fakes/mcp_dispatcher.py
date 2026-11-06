"""The MCP dispatcher seam faked for tests, and the `mcp_dispatcher` fixture that installs it (#3760).

An MCP tool hands one `devops` command line to the CLI through the dispatcher
(`devops_cli.ai.mcp.dispatcher`). Nothing starts a process there: the real dispatcher runs the
Typer app in the same process. So the process fake never sees the argv of a tool, and this fake
records it. A test installs the fake with the `mcp_dispatcher` fixture, scripts the exit code and
the output of a command with `answer`, and reads each call back from `calls`.

The fake keeps the rules of the real dispatcher. It refuses an argv that is not a `devops` argv
with the same `ValidationError`. A command with no scripted answer exits 0 with no output, and the
fake gives the output the text `Success`, as the real one does. `tests/ai/mcp/test_dispatcher_contract.py`
holds the fake to the real dispatcher.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

import pytest

from devops_cli.ai.mcp.dispatcher import (
    ResourceSubscriptionManager,
    devops_sub_args,
    install_mcp_dispatcher,
    reset_mcp_dispatcher,
)
from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

# The exit code the real dispatcher gives a command that outlasts its timeout.
TIMEOUT_EXIT_CODE = 124


@dataclass(frozen=True)
class DispatchCall:
    """One command line that an MCP tool handed to the dispatcher."""

    argv: tuple[str, ...]
    timeout: float
    env: dict[str, str] | None = None

    @property
    def sub_args(self) -> tuple[str, ...]:
        """The arguments after `devops`: the command, its options and its operands."""
        return tuple(devops_sub_args(list(self.argv)))


@dataclass(frozen=True)
class DispatchAnswer:
    """The scripted answer for a matching command."""

    exit_code: int = 0
    output: str = ""
    # Answer as the real dispatcher answers a command that outlasts its timeout.
    timed_out: bool = False
    error: BaseException | None = None


class DispatcherFake:
    """A fake MCP dispatcher that records calls and returns scripted answers."""

    def __init__(self) -> None:
        self.calls: list[DispatchCall] = []
        self.subscriptions = ResourceSubscriptionManager()
        self._answers: list[tuple[Callable[[DispatchCall], bool], DispatchAnswer]] = []

    @property
    def call_count(self) -> int:
        """The number of command lines handed to the dispatcher."""
        return len(self.calls)

    @property
    def last(self) -> DispatchCall:
        """The latest call. Fails the test when no tool handed over a command."""
        assert self.calls, "no command reached the dispatcher"
        return self.calls[-1]

    def answer(
        self,
        output: str = "",
        *,
        exit_code: int = 0,
        command: Sequence[str] = (),
    ) -> None:
        """Script an answer for each command whose arguments after `devops` start with `command`.

        No `command` matches every command. The latest matching answer wins.
        """
        self._script(command, DispatchAnswer(exit_code=exit_code, output=output))

    def time_out(self, command: Sequence[str] = ()) -> None:
        """Script a command that outlasts its timeout: exit code 124 and the real timeout text."""
        self._script(command, DispatchAnswer(exit_code=TIMEOUT_EXIT_CODE, timed_out=True))

    def fail(self, error: BaseException, command: Sequence[str] = ()) -> None:
        """Script a command whose dispatch raises `error`."""
        self._script(command, DispatchAnswer(error=error))

    def _script(self, command: Sequence[str], answer: DispatchAnswer) -> None:
        prefix = tuple(command)
        self._answers.append((lambda call: call.sub_args[: len(prefix)] == prefix, answer))

    def dispatch(
        self,
        cmd: list[str],
        timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        """Record the command and answer it. A program other than `devops` raises
        `ValidationError` before anything is recorded, as the real dispatcher raises it."""
        devops_sub_args(cmd)
        call = DispatchCall(tuple(cmd), timeout, env)
        self.calls.append(call)
        answer = self._match(call)
        if answer.error is not None:
            raise answer.error
        if answer.timed_out:
            return answer.exit_code, f"Command timed out after {timeout} seconds: {' '.join(cmd)}"
        fallback = "Success" if answer.exit_code == 0 else "no output captured"
        return answer.exit_code, answer.output or fallback

    def _match(self, call: DispatchCall) -> DispatchAnswer:
        for matches, answer in reversed(self._answers):
            if matches(call):
                return answer
        return DispatchAnswer()


@pytest.fixture
def mcp_dispatcher() -> Iterator[DispatcherFake]:
    """Install `DispatcherFake` as the dispatcher of every MCP tool, and remove it at teardown."""
    fake = DispatcherFake()
    install_mcp_dispatcher(fake)
    try:
        yield fake
    finally:
        reset_mcp_dispatcher()
