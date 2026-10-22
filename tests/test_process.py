"""Tests for process execution utilities (sync and async)."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

import pytest

from devops_cli.core.process import run_subprocess, run_subprocess_async
from tests.support.hung_children import (
    SUMMARY_LINE,
    hung_script,
    hung_with_grandchild,
    interrupted_like_pytest,
    mark_second_signal,
    records_after_second_signal,
    records_stop_signals,
    watching,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

pytestmark = [
    pytest.mark.usefixtures("refuse_nested_test_runs", "default_signal_dispositions"),
    pytest.mark.live("true", "sh", "false", "sleep", "echo", "python", "pwd"),
]

# A hung run's timeout: its child writes its pids within milliseconds, and this leaves a loaded
# host sufficient headroom before the run's process group is stopped (#1748).
HUNG_RUN_TIMEOUT_SECONDS = 1.0

# A run's timeout counts from when it starts waiting for its child. A test that returns the spawn
# only once the child has written its pids needs a short one: the child hangs, so it always fires.
STARTED_RUN_TIMEOUT_SECONDS = 0.2


def _raise_file_not_found(*_args: Any, **_kwargs: Any) -> None:
    raise FileNotFoundError(2, "No such file or directory")


def test_run_subprocess_success() -> None:
    proc = run_subprocess(["echo", "hello"])
    assert proc.returncode == 0
    assert proc.stdout.strip() == "hello"


def test_run_subprocess_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess.Popen, "__init__", _raise_file_not_found)
    proc = run_subprocess(["non_existent_binary_12345"])
    assert proc.returncode == 127
    assert "not found" in proc.stderr.lower()


@pytest.mark.anyio
async def test_run_subprocess_async_success() -> None:
    proc = await run_subprocess_async(["echo", "hello async"])
    assert proc.returncode == 0
    assert proc.stdout.strip() == "hello async"


@pytest.mark.anyio
async def test_run_subprocess_async_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess.Popen, "__init__", _raise_file_not_found)
    proc = await run_subprocess_async(["non_existent_binary_12345"])
    assert proc.returncode == 127
    assert "not found" in proc.stderr.lower()


@pytest.mark.anyio
async def test_run_subprocess_async_non_zero() -> None:
    proc = await run_subprocess_async(["false"])
    assert proc.returncode != 0


def test_run_subprocess_check_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run_subprocess error handling with check=True and timeouts."""
    import subprocess

    from devops_cli.dry_run import set_dry_run

    # 1. Non-zero exit with check=True
    with pytest.raises(subprocess.CalledProcessError):
        run_subprocess(["false"], check=True)

    # 2. Not found with check=True
    with monkeypatch.context() as mp, pytest.raises(FileNotFoundError):
        mp.setattr(subprocess.Popen, "__init__", _raise_file_not_found)
        run_subprocess(["non_existent_binary_99999"], check=True)

    # 3. Dry run execution
    set_dry_run(True)
    try:
        proc_dry = run_subprocess(["echo", "dry_run_test"])
        assert proc_dry is not None
    finally:
        set_dry_run(False)


@pytest.mark.anyio
async def test_run_subprocess_async_check_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run_subprocess_async error handling with check=True and timeouts."""
    import subprocess

    # 1. Non-zero exit with check=True
    with pytest.raises(subprocess.CalledProcessError):
        await run_subprocess_async(["false"], check=True)

    # 2. Not found with check=True
    with monkeypatch.context() as mp, pytest.raises(FileNotFoundError):
        mp.setattr(subprocess.Popen, "__init__", _raise_file_not_found)
        await run_subprocess_async(["non_existent_binary_99999"], check=True)

    # 3. Timeout expiration
    with pytest.raises(subprocess.TimeoutExpired):
        await run_subprocess_async(["sleep", "10"], timeout=0.01)


def test_run_subprocess_cwd_security() -> None:
    """Verify run_subprocess rejects traversal sequences and forbidden system directories in cwd."""
    from pathlib import Path

    from devops_cli.exceptions.security import SecurityError

    with pytest.raises(SecurityError):
        run_subprocess(["echo", "hi"], cwd=Path("../../../escaped"))

    with pytest.raises(SecurityError):
        run_subprocess(["echo", "hi"], cwd=Path("/etc"))


def test_run_subprocess_runs_in_the_runtime_root() -> None:
    """Only a sandbox workspace refuses /run (#1115); a subprocess may still run there."""
    proc = run_subprocess(["pwd"], cwd=Path("/run"))
    assert (proc.returncode, proc.stdout.strip()) == (0, "/run")


@pytest.mark.anyio
async def test_run_subprocess_async_cwd_security() -> None:
    """Verify run_subprocess_async rejects traversal sequences and forbidden system directories in cwd."""
    from pathlib import Path

    from devops_cli.exceptions.security import SecurityError

    with pytest.raises(SecurityError):
        await run_subprocess_async(["echo", "hi"], cwd=Path("../../../escaped"))

    with pytest.raises(SecurityError):
        await run_subprocess_async(["echo", "hi"], cwd=Path("/etc"))


@pytest.mark.anyio
async def test_run_subprocess_async_telemetry_sanitizes_secrets() -> None:
    """Verify run_subprocess_async redacts secrets in telemetry command attributes."""
    from unittest.mock import MagicMock, patch

    captured_attrs: dict[str, Any] = {}

    def fake_trace_span(name: str, attributes: dict[str, Any] | None = None):
        if attributes:
            captured_attrs.update(attributes)
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = MagicMock()
        mock_ctx.__exit__.return_value = None
        return mock_ctx

    token = "ghp_1234567890abcdef1234567890abcdef1234"
    cmd = [
        "python3",
        "-c",
        "pass",
        "--token",
        token,
        "--body",
        "super_secret_body",
        "title=super_secret_title",
    ]
    with patch("devops_cli.core.process.trace_span", side_effect=fake_trace_span):
        await run_subprocess_async(cmd)

    cmd_summary = captured_attrs.get("subprocess.cmd", "")
    proc_cmd = captured_attrs.get("process.command_line", "")
    assert (
        token in cmd_summary,
        "super_secret_body" in cmd_summary,
        "super_secret_title" in cmd_summary,
        cmd_summary == proc_cmd,
    ) == (False, False, False, True)


@pytest.mark.anyio
async def test_run_subprocess_async_timeout_kills_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify run_subprocess_async timeout kills entire process group including grandchildren.

    A run's timeout counts from when it starts waiting for its child. The spawn here returns only
    once the child has written its pids, so the timeout fires after the child and its grandchild
    exist, however busy the host is, and no wall-clock deadline for them to start remains. The
    child hangs, so the timeout always fires, and a short one is enough (#1888)."""
    real_spawn = asyncio.create_subprocess_exec
    with watching(tmp_path / "pids") as watch:

        async def spawn_once_started(*argv: Any, **kwargs: Any) -> asyncio.subprocess.Process:
            process = await real_spawn(*argv, **kwargs)
            assert await _until(watch.started), "the child wrote no pids"
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn_once_started)
        with pytest.raises(subprocess.TimeoutExpired):
            await run_subprocess_async(
                hung_with_grandchild(watch.pid_file), timeout=STARTED_RUN_TIMEOUT_SECONDS
            )

        assert await _until(watch.stopped)


def test_process_group_guard_helpers() -> None:
    """Verify process group validation guards against PID 1, 0, negative PIDs, and self."""
    import os

    from devops_cli.core.process import _is_invalid_pgid

    self_pgrp = os.getpgrp() if hasattr(os, "getpgrp") else -1
    assert (
        _is_invalid_pgid(1),
        _is_invalid_pgid(0),
        _is_invalid_pgid(-1),
        _is_invalid_pgid(None),  # type: ignore[arg-type]
        _is_invalid_pgid(self_pgrp) if self_pgrp > 1 else True,
        _is_invalid_pgid(999999),
    ) == (True, True, True, True, True, False)


def _records(log: Path) -> list[str]:
    """The records in a log the hung child writes, none before it writes one."""
    return log.read_text(encoding="utf-8").split() if log.is_file() else []


async def _until(condition: Any) -> bool:
    """Whether `condition` came to hold within the handoff bound, polled off the event loop."""
    return await asyncio.to_thread(wait_until, condition)


@pytest.mark.anyio
async def test_a_cancelled_run_stops_its_whole_process_group(tmp_path: Path) -> None:
    """Cancelling run_subprocess_async, as Ctrl-C cancels the task `asyncio.run` drives, stops
    its child's whole process group, so the grandchild it started, which ignores SIGINT as a
    background job does, does not outlive the run, as a timeout stops it (#1669)."""
    with watching(tmp_path / "pids") as watch:
        run = asyncio.create_task(run_subprocess_async(hung_with_grandchild(watch.pid_file)))
        started = await _until(watch.started)
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run

        assert (started, await _until(watch.stopped)) == (True, True)


@pytest.mark.anyio
async def test_a_cancelled_run_sends_its_group_sigint_first_so_its_teardown_runs(
    tmp_path: Path,
) -> None:
    """A cancelled run first sends its group the SIGINT a terminal would have sent, so a pytest
    in it runs its KeyboardInterrupt teardown, which here records itself and stops the
    grandchild it started, before any SIGTERM (#1669)."""
    marker = tmp_path / "teardown"
    with watching(tmp_path / "pids") as watch:
        hung = hung_with_grandchild(watch.pid_file, interrupted_like_pytest(marker))
        run = asyncio.create_task(run_subprocess_async(hung))
        started = await _until(watch.started)
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run

        assert (started, await _until(watch.stopped), marker.is_file()) == (True, True, True)


@pytest.mark.anyio
async def test_a_further_cancellation_during_the_stop_cannot_skip_its_sigkill(
    tmp_path: Path,
) -> None:
    """A second cancellation while the stop waits out its grace, as a second Ctrl-C or SIGTERM
    makes, cuts the grace short and is raised only once the group is killed: a child and
    grandchild that ignore SIGINT and SIGTERM are stopped by SIGKILL, and the child records no
    SIGTERM after the test marked its second cancellation (#1669)."""
    signals = tmp_path / "signals"
    script = records_stop_signals(signals)
    with watching(tmp_path / "pids") as watch:
        run = asyncio.create_task(
            run_subprocess_async(hung_with_grandchild(watch.pid_file, script))
        )
        started = await _until(watch.started)
        run.cancel()
        interrupted = await _until(lambda: "int" in _records(signals))
        mark_second_signal(signals)
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run

        assert (
            started,
            interrupted,
            await _until(watch.stopped),
            "term" in records_after_second_signal(signals),
        ) == (True, True, True, False)


@pytest.mark.anyio
async def test_a_cancellation_while_the_child_starts_still_stops_its_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cancellation that lands while `asyncio.create_subprocess_exec` is still returning, here a
    double of it that yields after the real start, still stops the child's whole group once the
    start completes, where asyncio's own clean-up would kill the child alone (#1669)."""
    real_spawn = asyncio.create_subprocess_exec
    spawned, release = asyncio.Event(), asyncio.Event()

    async def slow_spawn(*argv: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        proc = await real_spawn(*argv, **kwargs)
        spawned.set()
        await release.wait()
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", slow_spawn)
    with watching(tmp_path / "pids") as watch:
        hung = hung_with_grandchild(watch.pid_file, interrupted_like_pytest(tmp_path / "teardown"))
        run = asyncio.create_task(run_subprocess_async(hung))
        await asyncio.wait_for(spawned.wait(), THREAD_HANDOFF_BOUND_SECONDS)
        started = await _until(watch.started)
        run.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await run

        assert (started, await _until(watch.stopped)) == (True, True)


@pytest.mark.anyio
async def test_a_cancellation_after_the_child_exited_still_stops_the_members_left(
    tmp_path: Path,
) -> None:
    """A run cancelled after its child has exited still stops the child's group, since killpg
    reaches the members left: here a grandchild that holds the run's output pipes open. The child
    exits once the test has watched it, so the watch checks it while it still runs (#1669)."""
    go = tmp_path / "go"
    script = hung_script(after_start=f'while [ ! -e "{go}" ]; do sleep 0.01; done; exit 0; ')
    with watching(tmp_path / "pids") as watch:
        hung = hung_with_grandchild(watch.pid_file, script)
        run = asyncio.create_task(run_subprocess_async(hung, capture_output=True))
        started = await _until(watch.started)
        go.touch()
        leader_exited = await _until(watch.leader_stopped)
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run

        assert (started, leader_exited, await _until(watch.grandchild_stopped)) == (
            True,
            True,
            True,
        )


class _ExitedProcess:
    """A process whose output was read to the end and that then never reports done, standing in
    for a run cancelled after its child exited. asyncio's own Process raises ProcessLookupError
    from `kill()` once its transport has closed; this one does too."""

    def __init__(self, proc: asyncio.subprocess.Process) -> None:
        self._proc = proc
        self.pid = proc.pid
        self.exited = asyncio.Event()

    @property
    def returncode(self) -> int | None:
        return self._proc.returncode

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
        await self._proc.communicate()
        self.exited.set()
        await asyncio.Event().wait()
        return b"", b""

    async def wait(self) -> int:
        return await self._proc.wait()

    def kill(self) -> None:
        raise ProcessLookupError


@pytest.mark.anyio
async def test_a_cancellation_after_the_child_exited_stays_a_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancellation that arrives once the child has exited, and its group is gone, stays a
    CancelledError, so `devops ci test` still exits as cancelled, rather than a
    ProcessLookupError from killing a child already reaped (#1669)."""
    real_spawn = asyncio.create_subprocess_exec
    started: list[_ExitedProcess] = []
    created = asyncio.Event()

    async def spawn(*argv: Any, **kwargs: Any) -> _ExitedProcess:
        started.append(_ExitedProcess(await real_spawn(*argv, **kwargs)))
        created.set()
        return started[-1]

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    run = asyncio.create_task(run_subprocess_async(["true"]))
    await asyncio.wait_for(created.wait(), THREAD_HANDOFF_BOUND_SECONDS)
    await asyncio.wait_for(started[0].exited.wait(), THREAD_HANDOFF_BOUND_SECONDS)
    run.cancel()

    with pytest.raises(asyncio.CancelledError):
        await run


@pytest.mark.anyio
async def test_a_run_that_hangs_after_its_summary_line_is_stopped_at_its_bound_with_its_group(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """A serial narrowed run that prints its summary line and then hangs, here a fake pytest
    with a grandchild, is stopped with its whole group at the run's timeout, which counts from
    the start of the run, not from the summary line (#1669). `devops ci test` has no timeout
    option, so its 1800 s bound cannot be shortened through it; the test drives the runner it
    uses, `run_subprocess_async`, with a short one."""
    script = hung_script(before=f'echo "{SUMMARY_LINE}"; ')
    with watching(tmp_path / "pids") as watch:
        hung = hung_with_grandchild(watch.pid_file, script)
        run = asyncio.create_task(
            run_subprocess_async(hung, capture_output=False, timeout=HUNG_RUN_TIMEOUT_SECONDS)
        )
        started = await _until(watch.started)
        with pytest.raises(subprocess.TimeoutExpired):
            await run

        assert (
            SUMMARY_LINE in capfd.readouterr().out,
            started,
            await _until(watch.stopped),
        ) == (True, True, True)


@pytest.mark.anyio
async def test_a_timed_out_check_is_stopped_with_sigterm_first_and_reports_as_before(
    tmp_path: Path,
) -> None:
    """A timeout, which `devops ci`'s checks share, still sends SIGTERM first, never the SIGINT a
    cancellation forwards, and still raises TimeoutExpired with the command and timeout (#1669)."""
    signals = tmp_path / "signals"
    script = hung_script(
        before=f'trap \'echo term >> "{signals}"; kill "$c"; exit 143\' TERM; ',
        on_interrupt=f'echo int >> "{signals}"',
    )
    with watching(tmp_path / "pids") as watch:
        hung = hung_with_grandchild(watch.pid_file, script)
        run = asyncio.create_task(run_subprocess_async(hung, timeout=HUNG_RUN_TIMEOUT_SECONDS))
        started = await _until(watch.started)
        with pytest.raises(subprocess.TimeoutExpired) as timed_out:
            await run

        assert (
            started,
            (timed_out.value.cmd, timed_out.value.timeout),
            await _until(watch.stopped),
            signals.read_text(encoding="utf-8"),
        ) == (True, (hung, HUNG_RUN_TIMEOUT_SECONDS), True, "term\n")
