"""Process runner fake and recording types for hermetic subprocess testing (#775, ADR 0007).

Provides `ProcessFake` to replace real child process execution across sync and async
interfaces, recording calls and returning scripted answers.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import (
    PlannedProcessResult,
    _prepare_cmd,
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


class ProcessFake:
    """A fake process runner that records calls and returns scripted answers."""

    def __init__(self) -> None:
        self.calls: list[ProcessCall] = []
        self._answers: list[tuple[Callable[[ProcessCall], bool], ProcessAnswer]] = []

    @property
    def call_count(self) -> int:
        """The total number of commands executed through this fake."""
        return len(self.calls)

    def answer(
        self,
        matcher: str | Sequence[str] | Callable[[ProcessCall], bool],
        answer: ProcessAnswer,
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
                return ans
        return ProcessAnswer()

    def prepare_cmd(self, cmd: Sequence[str] | list[str]) -> list[str]:
        """Prepare command arguments list, injecting standardized uv preview features when starting uv."""
        from devops_cli.core.process import prepare_tool_cmd

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
        full_cmd = _prepare_cmd(cmd)
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
            time.sleep(timeout)
            raise subprocess.TimeoutExpired(cmd=list(call.argv), timeout=timeout)
        if ans.delay > 0:
            time.sleep(ans.delay)

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
        full_cmd = _prepare_cmd(cmd)
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
            await asyncio.sleep(timeout)
            raise subprocess.TimeoutExpired(cmd=list(call.argv), timeout=timeout)
        if ans.delay > 0:
            await asyncio.sleep(ans.delay)

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
