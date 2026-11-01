"""Tests for process execution utilities (sync and async)."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

import pytest

from devops_cli.core.process import run_subprocess, run_subprocess_async
from tests.support.fakes.process import EndedProcess
from tests.support.hung_children import (
    SUMMARY_LINE,
    HungChildWatch,
    hung_script,
    hung_with_grandchild,
    interrupted_like_pytest,
    mark_second_signal,
    records_after_second_signal,
    records_stop_signals,
    watching,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

pytestmark = pytest.mark.usefixtures("refuse_nested_test_runs", "default_signal_dispositions")

# A run's timeout counts from when it starts waiting for its child. A test that returns the spawn
# only once the child has written its pids needs a short one: the child hangs, so it always fires.
STARTED_RUN_TIMEOUT_SECONDS = 0.2


def _raise_file_not_found(*_args: Any, **_kwargs: Any) -> None:
    raise FileNotFoundError(2, "No such file or directory")


@pytest.mark.live("echo")
def test_run_subprocess_success() -> None:
    proc = run_subprocess(["echo", "hello"])
    assert proc.returncode == 0
    assert proc.stdout.strip() == "hello"


def test_run_subprocess_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess.Popen, "__init__", _raise_file_not_found)
    proc = run_subprocess(["non_existent_binary_12345"])
    assert proc.returncode == 127
    assert "not found" in proc.stderr.lower()


@pytest.mark.live("echo")
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


@pytest.mark.live("false")
@pytest.mark.anyio
async def test_run_subprocess_async_non_zero() -> None:
    proc = await run_subprocess_async(["false"])
    assert proc.returncode != 0


@pytest.mark.live("false")
def test_run_subprocess_check_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run_subprocess error handling with check=True and timeouts."""
    import subprocess

    from devops_cli.dry_run import set_dry_run

    # 1. Non-zero exit with check=True
    with pytest.raises(subprocess.CalledProcessError) as raised:
        run_subprocess(["false"], check=True)
    assert raised.value is not None

    # 2. Not found with check=True
    with monkeypatch.context() as mp, pytest.raises(FileNotFoundError) as raised:
        mp.setattr(subprocess.Popen, "__init__", _raise_file_not_found)
        run_subprocess(["non_existent_binary_99999"], check=True)
    assert raised.value.errno == 2 or "No such file" in str(raised.value)

    # 3. Dry run execution
    set_dry_run(True)
    try:
        proc_dry = run_subprocess(["echo", "dry_run_test"])
        assert proc_dry.returncode == 0
    finally:
        set_dry_run(False)


@pytest.mark.live("false", "sleep")
@pytest.mark.anyio
async def test_run_subprocess_async_check_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run_subprocess_async error handling with check=True and timeouts."""
    import subprocess

    # 1. Non-zero exit with check=True
    with pytest.raises(subprocess.CalledProcessError) as raised:
        await run_subprocess_async(["false"], check=True)
    assert raised.value.returncode == 1

    # 2. Not found with check=True
    with monkeypatch.context() as mp, pytest.raises(FileNotFoundError) as raised:
        mp.setattr(subprocess.Popen, "__init__", _raise_file_not_found)
        await run_subprocess_async(["non_existent_binary_99999"], check=True)
    assert raised.value.errno == 2 or "No such file" in str(raised.value)

    # 3. Timeout expiration
    with pytest.raises(subprocess.TimeoutExpired) as raised:
        await run_subprocess_async(["sleep", "10"], timeout=0.01)
    assert raised.value.timeout == 0.01


def test_run_subprocess_cwd_security() -> None:
    """Verify run_subprocess rejects traversal sequences and forbidden system directories in cwd."""
    from pathlib import Path

    from devops_cli.exceptions.security import SecurityError

    with pytest.raises(SecurityError) as raised:
        run_subprocess(["echo", "hi"], cwd=Path("../../../escaped"))
    assert raised.value.error_code == "SECURITY_ERROR"

    with pytest.raises(SecurityError) as raised:
        run_subprocess(["echo", "hi"], cwd=Path("/etc"))
    assert raised.value.error_code == "SECURITY_ERROR"


@pytest.mark.live("pwd")
def test_run_subprocess_runs_in_the_runtime_root() -> None:
    """Only a sandbox workspace refuses /run (#1115); a subprocess may still run there."""
    proc = run_subprocess(["pwd"], cwd=Path("/run"))
    assert (proc.returncode, proc.stdout.strip()) == (0, "/run")


@pytest.mark.anyio
async def test_run_subprocess_async_cwd_security() -> None:
    """Verify run_subprocess_async rejects traversal sequences and forbidden system directories in cwd."""
    from pathlib import Path

    from devops_cli.exceptions.security import SecurityError

    with pytest.raises(SecurityError) as raised:
        await run_subprocess_async(["echo", "hi"], cwd=Path("../../../escaped"))
    assert raised.value.error_code == "SECURITY_ERROR"

    with pytest.raises(SecurityError) as raised:
        await run_subprocess_async(["echo", "hi"], cwd=Path("/etc"))
    assert raised.value.error_code == "SECURITY_ERROR"


@pytest.mark.live("sh")
@pytest.mark.anyio
async def test_run_subprocess_async_timeout_kills_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify run_subprocess_async timeout kills entire process group including grandchildren.

    The spawn returns only once the child has written its pids (#1888)."""
    with watching(tmp_path / "pids") as watch:
        _spawn_once_started(monkeypatch, watch)
        with pytest.raises(subprocess.TimeoutExpired) as raised:
            await run_subprocess_async(
                hung_with_grandchild(watch.pid_file), timeout=STARTED_RUN_TIMEOUT_SECONDS
            )
        assert raised.value is not None

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


def test_terminate_process_group_guards_and_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify terminate_process_group guards against PID <= 1, self, and signals group or process."""
    import os
    import signal
    from unittest.mock import MagicMock

    from devops_cli.core.process import terminate_process_group

    assert terminate_process_group(0) is False
    assert terminate_process_group(1) is False
    assert terminate_process_group(-10) is False
    mock_pid: Any = MagicMock()
    assert terminate_process_group(mock_pid) is False
    assert terminate_process_group(os.getpid()) is False

    real_own_pgid = os.getpgid(0) if hasattr(os, "getpgid") else 1234
    mock_kill = MagicMock()
    mock_killpg = MagicMock()
    monkeypatch.setattr(os, "kill", mock_kill)
    monkeypatch.setattr(os, "killpg", mock_killpg)
    monkeypatch.setattr(os, "getpgid", lambda pid: real_own_pgid)

    assert terminate_process_group(42424, signal.SIGTERM) is True
    assert mock_kill.call_count == 1
    assert mock_killpg.call_count == 0

    mock_kill.reset_mock()
    mock_killpg.reset_mock()
    monkeypatch.setattr(os, "getpgid", lambda pid: 99999 if pid != 0 else real_own_pgid)

    assert terminate_process_group(42424, signal.SIGTERM) is True
    assert mock_kill.call_count == 0
    assert mock_killpg.call_count == 1


def _records(log: Path) -> list[str]:
    """The records in a log the hung child writes, none before it writes one."""
    return log.read_text(encoding="utf-8").split() if log.is_file() else []


async def _until(condition: Any) -> bool:
    """Whether `condition` came to hold within the handoff bound, polled off the event loop."""
    return await asyncio.to_thread(wait_until, condition)


def _spawn_once_started(monkeypatch: pytest.MonkeyPatch, watch: HungChildWatch) -> None:
    """Make each spawn return only once the hung child has written its pids (#1888, #1902).

    A run's timeout counts from when it starts waiting for its child. With this spawn, the timeout
    fires after the child and its grandchild exist, however busy the host is, so no wall-clock
    deadline for them to start remains. The child hangs, so the timeout always fires."""
    real_spawn = asyncio.create_subprocess_exec

    async def spawn_once_started(*argv: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        process = await real_spawn(*argv, **kwargs)
        assert await _until(watch.started), "the child wrote no pids"
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn_once_started)


@pytest.mark.live("sh")
@pytest.mark.anyio
async def test_a_cancelled_run_stops_its_whole_process_group(tmp_path: Path) -> None:
    """Cancelling run_subprocess_async, as Ctrl-C cancels the task `asyncio.run` drives, stops
    its child's whole process group, so the grandchild it started, which ignores SIGINT as a
    background job does, does not outlive the run, as a timeout stops it (#1669)."""
    with watching(tmp_path / "pids") as watch:
        run = asyncio.create_task(run_subprocess_async(hung_with_grandchild(watch.pid_file)))
        started = await _until(watch.started)
        run.cancel()
        with pytest.raises(asyncio.CancelledError) as raised:
            await run
        assert raised.value is not None

        assert (started, await _until(watch.stopped)) == (True, True)


@pytest.mark.live("sh")
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
        with pytest.raises(asyncio.CancelledError) as raised:
            await run
        assert raised.value is not None

        assert (started, await _until(watch.stopped), marker.is_file()) == (True, True, True)


@pytest.mark.live("sh")
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
        with pytest.raises(asyncio.CancelledError) as raised:
            await run
        assert raised.value is not None

        assert (
            started,
            interrupted,
            await _until(watch.stopped),
            "term" in records_after_second_signal(signals),
        ) == (True, True, True, False)


@pytest.mark.live("sh")
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
        with pytest.raises(asyncio.CancelledError) as raised:
            await run
        assert raised.value is not None

        assert (started, await _until(watch.stopped)) == (True, True)


@pytest.mark.live("sh")
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
        with pytest.raises(asyncio.CancelledError) as raised:
            await run
        assert raised.value is not None

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


@pytest.mark.live("true")
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

    with pytest.raises(asyncio.CancelledError) as raised:
        await run
    assert raised.type is asyncio.CancelledError


@pytest.mark.live("sh")
@pytest.mark.anyio
async def test_a_run_that_hangs_after_its_summary_line_is_stopped_at_its_bound_with_its_group(
    tmp_path: Path, capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A serial narrowed run that prints its summary line and then hangs, here a fake pytest
    with a grandchild, is stopped with its whole group at the run's timeout, which counts from
    the start of the run, not from the summary line (#1669). `devops ci test` has no timeout
    option, so its 1800 s bound cannot be shortened through it; the test drives the runner it
    uses, `run_subprocess_async`, with a short one. The spawn returns only once the child has
    written its pids, so a loaded host cannot stop the child before it writes them (#1902)."""
    script = hung_script(before=f'echo "{SUMMARY_LINE}"; ')
    with watching(tmp_path / "pids") as watch:
        _spawn_once_started(monkeypatch, watch)
        hung = hung_with_grandchild(watch.pid_file, script)
        with pytest.raises(subprocess.TimeoutExpired) as raised:
            await run_subprocess_async(
                hung, capture_output=False, timeout=STARTED_RUN_TIMEOUT_SECONDS
            )
        assert raised.value is not None

        assert (SUMMARY_LINE in capfd.readouterr().out, await _until(watch.stopped)) == (
            True,
            True,
        )


@pytest.mark.live("sh")
@pytest.mark.anyio
async def test_a_timed_out_check_is_stopped_with_sigterm_first_and_reports_as_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A timeout, which `devops ci`'s checks share, still sends SIGTERM first, never the SIGINT a
    cancellation forwards, and still raises TimeoutExpired with the command and timeout (#1669).
    The spawn returns only once the child has written its pids, so its traps are set before the
    timeout fires, however busy the host is (#1902)."""
    signals = tmp_path / "signals"
    script = hung_script(
        before=f'trap \'echo term >> "{signals}"; kill "$c"; exit 143\' TERM; ',
        on_interrupt=f'echo int >> "{signals}"',
    )
    with watching(tmp_path / "pids") as watch:
        _spawn_once_started(monkeypatch, watch)
        hung = hung_with_grandchild(watch.pid_file, script)
        with pytest.raises(subprocess.TimeoutExpired) as timed_out:
            await run_subprocess_async(hung, timeout=STARTED_RUN_TIMEOUT_SECONDS)

        assert (
            (timed_out.value.cmd, timed_out.value.timeout),
            await _until(watch.stopped),
            signals.read_text(encoding="utf-8"),
        ) == ((hung, STARTED_RUN_TIMEOUT_SECONDS), True, "term\n")


def test_process_runner_seam() -> None:
    """Verify get_process_runner returns the active runner, set replaces it, and reset restores it."""
    from collections.abc import Sequence

    from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
    from devops_cli.core.process import (
        DefaultProcessRunner,
        get_process_runner,
        reset_process_runner,
        set_process_runner,
    )

    runner = get_process_runner()
    assert isinstance(runner, DefaultProcessRunner)

    class CustomRunner:
        def prepare_cmd(self, cmd: Sequence[str] | list[str]) -> list[str]:
            return list(cmd)

        def run(
            self,
            cmd: Sequence[str] | list[str],
            *,
            input: str | None = None,
            cwd: Path | None = None,
            env: dict[str, str] | None = None,
            capture_output: bool = True,
            text: bool = True,
            check: bool = False,
            quiet: bool = False,
            timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            isolate_env: bool = True,
            extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
            local_read: bool = False,
            intent: str | None = None,
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["custom"], returncode=0, stdout="custom output"
            )

        async def run_async(
            self,
            cmd: Sequence[str] | list[str],
            *,
            cwd: Path | None = None,
            env: dict[str, str] | None = None,
            capture_output: bool = True,
            text: bool = True,
            check: bool = False,
            quiet: bool = False,
            timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            isolate_env: bool = True,
            extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
            local_read: bool = False,
            intent: str | None = None,
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["custom_async"], returncode=0, stdout="custom async"
            )

        def spawn_detached(
            self,
            cmd: Sequence[str] | list[str],
            *,
            isolate_env: bool = True,
            extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
        ) -> EndedProcess:
            return EndedProcess()

    custom = CustomRunner()
    set_process_runner(custom)
    try:
        assert get_process_runner() is custom
        proc = run_subprocess(["echo", "ignored"])
        assert proc.stdout == "custom output"
    finally:
        reset_process_runner()

    assert isinstance(get_process_runner(), DefaultProcessRunner)


def test_uv_preview_flags_injection() -> None:
    """Verify uv commands automatically receive preview features if not present."""
    from devops_cli.core.process import prepare_tool_cmd

    assert prepare_tool_cmd(["uv", "run", "pytest"]) == [
        "uv",
        "--preview-features",
        "malware-check,check-command",
        "run",
        "pytest",
    ]
    assert prepare_tool_cmd(["uv", "--preview-features", "malware-check", "run"]) == [
        "uv",
        "--preview-features",
        "malware-check",
        "run",
    ]
    assert prepare_tool_cmd(["git", "status"]) == ["git", "status"]


def test_default_process_runner_spawn_sandbox() -> None:
    """DefaultProcessRunner.spawn_sandbox starts a process in a new session with piped streams."""
    from devops_cli.core.process import DefaultProcessRunner

    proc = DefaultProcessRunner().spawn_sandbox(["git", "--version"])
    try:
        stdout, _ = proc.communicate(timeout=5)
        assert proc.returncode == 0
        assert b"git version" in stdout
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_terminate_process_group_custom_os() -> None:
    """terminate_process_group uses custom os module when passed."""
    import signal
    from unittest.mock import MagicMock

    from devops_cli.core.process import terminate_process_group

    mock_os = MagicMock()
    mock_os.getpid.return_value = 999
    mock_os.getpgrp.return_value = 100
    mock_os.getpgid.side_effect = lambda p: 200 if p == 200 else 100
    assert terminate_process_group(200, os_module=mock_os) is True
    mock_os.killpg.assert_called_once_with(200, signal.SIGTERM)


def test_dry_run_intent_handling() -> None:
    """Under dry run, mutating commands return PlannedProcessResult and do not execute; declared local reads execute."""
    from devops_cli.dry_run import set_dry_run
    from devops_cli.dry_run.requests import PlannedRequest

    set_dry_run(True)
    try:
        res_mutating = run_subprocess(["git", "commit", "-m", "fix"])
        assert isinstance(res_mutating, PlannedRequest)
        assert isinstance(res_mutating, subprocess.CompletedProcess)
        assert res_mutating.method == "git"
        assert res_mutating.argv == ("git", "commit", "-m", "fix")
        assert res_mutating.returncode == 0
        assert res_mutating.stdout == ""

        res_gh = run_subprocess(["gh", "pr", "view", "100"])
        assert isinstance(res_gh, PlannedRequest)
        assert res_gh.method == "gh"

        res_read = run_subprocess(["git", "rev-parse", "--is-inside-work-tree"], local_read=True)
        assert not isinstance(res_read, PlannedRequest)
        assert res_read.returncode == 0
        assert res_read.stdout.strip() == "true"
    finally:
        set_dry_run(False)
