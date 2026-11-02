"""Process runner fake and recording types for hermetic subprocess testing (#775, ADR 0007).

Provides `ProcessFake` to replace real child process execution across sync and async
interfaces, recording calls and returning scripted answers.
"""

from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core import clock as clock_seam
from devops_cli.core.process import (
    PlannedProcessResult,
    prepare_tool_cmd,
)
from devops_cli.dry_run import is_dry_run


@dataclass(frozen=True)
class ProcessCall:
    """A single process execution recorded by `ProcessFake`."""

    argv: tuple[str, ...]
    cwd: Path | None = None
    env: dict[str, str] | None = None
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
    capture_output: bool = True
    intent: str | None = None
    local_read: bool = False
    stdin: str | bytes | None = None
    check: bool = False
    # Started with `spawn_detached`: in a session of its own, with nothing to wait for.
    detached: bool = False


@dataclass(frozen=True)
class ProcessAnswer:
    """Scripted response for a matching command."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    delay: float = 0.0
    side_effect: (
        BaseException
        | type[BaseException]
        | Callable[[ProcessCall], subprocess.CompletedProcess[str]]
        | None
    ) = None
    # The child that `spawn_detached` answers with, such as a process the test started itself,
    # or a callable that takes the call and returns that child.
    process: Any = None


@dataclass(frozen=True)
class EndedProcess:
    """A detached child that ended at once with `returncode`, as a program that fails at start."""

    returncode: int = 0
    pid: int = -1

    def poll(self) -> int | None:
        """The return code: the child has ended."""
        return self.returncode


class FakeSandboxProcess:
    """A double for a sandboxed child process with real OS pipes for stdout and stderr (#2149)."""

    def __init__(
        self,
        *,
        pid: int = 12345,
        returncode: int | None = None,
        stdout: bytes = b"",
        stderr: bytes = b"",
        hang_on_first_wait: bool = False,
        pipe_stdout_writer: bool = False,
    ) -> None:
        self.pid = pid
        self.returncode = (
            returncode if returncode is not None else (None if pipe_stdout_writer else 0)
        )
        self.signals: list[int] = []
        self.waits: list[float | None] = []
        self._hang_on_first_wait = hang_on_first_wait
        self._wait_count = 0
        self._poll_count = 0

        r_out, self._w_out = os.pipe()
        r_err, self._w_err = os.pipe()

        if stdout:
            os.write(self._w_out, stdout)
        if not pipe_stdout_writer:
            os.close(self._w_out)
            self._w_out = -1

        if stderr:
            os.write(self._w_err, stderr)
        os.close(self._w_err)
        self._w_err = -1

        self.stdout = os.fdopen(r_out, "rb", buffering=0)
        self.stderr = os.fdopen(r_err, "rb", buffering=0)

    def write_stdout(self, data: bytes) -> None:
        """Write additional bytes to stdout pipe while open."""
        if self._w_out >= 0:
            os.write(self._w_out, data)

    def close_stdout_writer(self) -> None:
        """Close write end of stdout pipe to signal EOF."""
        if self._w_out >= 0:
            os.close(self._w_out)
            self._w_out = -1

    def poll(self) -> int | None:
        self._poll_count += 1
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.waits.append(timeout)
        self._wait_count += 1
        if self._hang_on_first_wait and self._wait_count == 1:
            raise subprocess.TimeoutExpired(cmd=["bwrap"], timeout=timeout or 1.0)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)
        if self.returncode is None:
            self.returncode = -sig

    def kill(self) -> None:
        self.send_signal(signal.SIGKILL)

    def terminate(self) -> None:
        self.send_signal(signal.SIGTERM)

    def close(self) -> None:
        self.close_stdout_writer()
        if not self.stdout.closed:
            self.stdout.close()
        if not self.stderr.closed:
            self.stderr.close()


class ProcessFake:
    """A fake process runner that records calls and returns scripted answers."""

    def __init__(self) -> None:
        self.calls: list[ProcessCall] = []
        self._answers: list[
            tuple[
                Callable[[ProcessCall], bool],
                ProcessAnswer | Callable[[ProcessCall], ProcessAnswer],
            ]
        ] = []
        self.sandbox_processes: list[FakeSandboxProcess] = []
        self._sandbox_answers: list[FakeSandboxProcess | Callable[..., FakeSandboxProcess]] = []
        self.terminated_pids: list[tuple[int, int]] = []

    def answer_sandbox(
        self,
        answer: FakeSandboxProcess | Callable[..., FakeSandboxProcess],
    ) -> None:
        """Script an answer for sandbox process execution."""
        self._sandbox_answers.append(answer)

    def spawn_sandbox(
        self,
        cmd: Sequence[str] | list[str],
    ) -> FakeSandboxProcess:
        """Spawn a fake sandbox process with piped streams and recorded execution."""
        call = ProcessCall(argv=tuple(cmd), capture_output=True)
        self.calls.append(call)
        if self._sandbox_answers:
            item = self._sandbox_answers.pop(0)
            proc = item(call) if callable(item) else item
        else:
            proc = FakeSandboxProcess(returncode=0)
        self.sandbox_processes.append(proc)
        return proc

    def terminate_process_group(self, pid: int, sig: int = signal.SIGTERM) -> bool:
        """Record process group termination and signal matching fake processes."""
        self.terminated_pids.append((pid, sig))
        for proc in self.sandbox_processes:
            if proc.pid == pid:
                proc.send_signal(sig)
                return True
        from devops_cli.core.process import _terminate_process_group_os

        return _terminate_process_group_os(pid, sig)

    @property
    def call_count(self) -> int:
        """The total number of commands executed through this fake."""
        return len(self.calls)

    def answer(
        self,
        matcher: str | Sequence[str] | Callable[[ProcessCall], bool],
        answer: ProcessAnswer | Callable[[ProcessCall], ProcessAnswer],
    ) -> None:
        """Script an answer for commands matching `matcher`.

        `matcher` can be:
        - A string: matches if the first argv word matches or argv starts with words.
        - A sequence of strings: matches if argv starts with this prefix.
        - A callable: called with `ProcessCall`, matches if returning true.
        """
        if callable(matcher):
            pred = matcher
        elif isinstance(matcher, str):
            tokens = tuple(matcher.split())

            def pred(call: ProcessCall, _tokens: tuple[str, ...] = tokens) -> bool:
                return call.argv[: len(_tokens)] == _tokens

        else:
            prefix = tuple(matcher)

            def pred(call: ProcessCall, _prefix: tuple[str, ...] = prefix) -> bool:
                return call.argv[: len(_prefix)] == _prefix

        self._answers.append((pred, answer))

    def _match_answer(self, call: ProcessCall) -> ProcessAnswer:
        for pred, ans in reversed(self._answers):
            if pred(call):
                return ans(call) if callable(ans) else ans
        return ProcessAnswer()

    def prepare_cmd(self, cmd: Sequence[str] | list[str]) -> list[str]:
        """Prepare command arguments list, injecting standardized uv preview features when starting uv."""
        return prepare_tool_cmd(cmd)

    def run(
        self,
        cmd: Sequence[str],
        *,
        input: str | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        capture_output: bool = True,
        intent: str | None = None,
        local_read: bool = False,
        stdin: str | bytes | None = None,
        check: bool = False,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        """Record and execute a synchronous subprocess command.

        `run_subprocess` sends a body as `input`, as the real runner takes it; the call records it
        as `stdin`.
        """
        full_cmd = prepare_tool_cmd(cmd)
        call = ProcessCall(
            argv=tuple(full_cmd),
            cwd=cwd,
            env=env,
            timeout=timeout,
            capture_output=capture_output,
            intent=intent,
            local_read=local_read,
            stdin=stdin if stdin is not None else input,
            check=check,
        )
        self.calls.append(call)

        if is_dry_run() and not (local_read or intent in ("read", "local_read")):
            method = call.argv[0] if call.argv else "process"
            target = " ".join(call.argv[1:]) if len(call.argv) > 1 else "workspace"
            return PlannedProcessResult(
                method=method,
                target=target,
                argv=call.argv,
                stdin=call.stdin if isinstance(call.stdin, str) else None,
                env=tuple((k, v) for k, v in sorted((call.env or {}).items())),
            )

        ans = self._match_answer(call)

        if timeout > 0 and ans.delay > timeout:
            raise subprocess.TimeoutExpired(cmd=list(call.argv), timeout=timeout)
        if ans.delay > 0:
            clock_seam.sleep(ans.delay)

        if ans.side_effect is not None:
            if isinstance(ans.side_effect, BaseException):
                raise ans.side_effect
            if isinstance(ans.side_effect, type) and issubclass(ans.side_effect, BaseException):
                raise ans.side_effect()
            if callable(ans.side_effect):
                return ans.side_effect(call)

        res = subprocess.CompletedProcess[str](
            args=list(call.argv),
            returncode=ans.returncode,
            stdout=ans.stdout,
            stderr=ans.stderr,
        )
        if check and res.returncode != 0:
            raise subprocess.CalledProcessError(
                res.returncode, res.args, output=res.stdout, stderr=res.stderr
            )
        return res

    def spawn_detached(
        self,
        cmd: Sequence[str] | list[str],
        *,
        isolate_env: bool = True,
        extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
    ) -> Any:
        """Record a detached start and answer with the scripted answer's `process`.

        With no `process` scripted, the child has ended at once with the answer's return code.
        """
        call = ProcessCall(argv=tuple(cmd), capture_output=False, detached=True)
        self.calls.append(call)
        ans = self._match_answer(call)
        if isinstance(ans.side_effect, BaseException):
            raise ans.side_effect
        if isinstance(ans.side_effect, type) and issubclass(ans.side_effect, BaseException):
            raise ans.side_effect()
        if ans.process is None:
            return EndedProcess(ans.returncode)
        return ans.process(call) if callable(ans.process) else ans.process

    async def run_async(
        self,
        cmd: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        capture_output: bool = True,
        intent: str | None = None,
        local_read: bool = False,
        stdin: str | bytes | None = None,
        check: bool = False,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        """Record and execute an asynchronous subprocess command."""
        full_cmd = prepare_tool_cmd(cmd)
        call = ProcessCall(
            argv=tuple(full_cmd),
            cwd=cwd,
            env=env,
            timeout=timeout,
            capture_output=capture_output,
            intent=intent,
            local_read=local_read,
            stdin=stdin,
            check=check,
        )
        self.calls.append(call)

        if is_dry_run() and not (local_read or intent in ("read", "local_read")):
            method = call.argv[0] if call.argv else "process"
            target = " ".join(call.argv[1:]) if len(call.argv) > 1 else "workspace"
            return PlannedProcessResult(
                method=method,
                target=target,
                argv=call.argv,
                stdin=call.stdin if isinstance(call.stdin, str) else None,
                env=tuple((k, v) for k, v in sorted((call.env or {}).items())),
            )

        ans = self._match_answer(call)

        if timeout > 0 and ans.delay > timeout:
            raise subprocess.TimeoutExpired(cmd=list(call.argv), timeout=timeout)
        if ans.delay > 0:
            clock_seam.sleep(ans.delay)

        if ans.side_effect is not None:
            if isinstance(ans.side_effect, BaseException):
                raise ans.side_effect
            if isinstance(ans.side_effect, type) and issubclass(ans.side_effect, BaseException):
                raise ans.side_effect()
            if callable(ans.side_effect):
                return ans.side_effect(call)

        res = subprocess.CompletedProcess[str](
            args=list(call.argv),
            returncode=ans.returncode,
            stdout=ans.stdout,
            stderr=ans.stderr,
        )
        if check and res.returncode != 0:
            raise subprocess.CalledProcessError(
                res.returncode, res.args, output=res.stdout, stderr=res.stderr
            )
        return res


@pytest.fixture
def process_fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[ProcessFake]:
    """The process runner edge, faked for every command that starts child processes (ADR 0007, #775).

    Installs an in-memory `ProcessFake` into the process runner seam. Any subprocess call
    via `run_subprocess`, `run_subprocess_async`, or `get_process_runner()` routes to this fake.
    Also fakes `shutil.which` for any tool not on the passthrough list (`git`, `bwrap`),
    returning a hermetic fake path `/usr/local/bin/<tool>`.
    """
    import shutil

    from devops_cli.core.process import reset_process_runner, set_process_runner

    fake = ProcessFake()
    set_process_runner(fake)

    real_which = shutil.which

    def fake_which(cmd: str, *args: Any, **kwargs: Any) -> str | None:
        cmd_name = Path(cmd).name
        if cmd_name in {"git", "bwrap"}:
            return real_which(cmd, *args, **kwargs)
        return f"/usr/local/bin/{cmd_name}"

    monkeypatch.setattr(shutil, "which", fake_which)
    try:
        yield fake
    finally:
        for proc in fake.sandbox_processes:
            proc.close()
        reset_process_runner()
