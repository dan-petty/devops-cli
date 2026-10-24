"""Contract suite for the process runner edge: real DefaultProcessRunner and ProcessFake (#775, ADR 0007).

Tests the promises of the process runner edge:
- Sync and async subprocess execution return CompletedProcess with matching fields.
- Command argv preparation standardizes uv preview feature flags.
- Dry-run mode intercepts mutating commands, returning PlannedProcessResult without starting child processes.
- Read intents (local_read=True, intent="read" or "local_read") bypass dry-run interception.
- Error handling raises CalledProcessError when check=True and returncode != 0.
- Timeout raises TimeoutExpired.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from devops_cli.core.process import (
    DefaultProcessRunner,
    PlannedProcessResult,
    ProcessRunner,
)
from devops_cli.dry_run import PlannedRequest
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake


@pytest.fixture
def runner_instance(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[ProcessRunner, bool]:
    """Provide a ProcessRunner instance and a flag indicating if it is a fake."""
    runner_type = request.param
    if runner_type == "fake":
        fake = ProcessFake()
        fake.answer(
            ["git", "version"],
            ProcessAnswer(returncode=0, stdout="git version 2.43.0\n", stderr=""),
        )
        fake.answer(
            ["git", "status"],
            ProcessAnswer(returncode=0, stdout="On branch main\nnothing to commit\n", stderr=""),
        )
        fake.answer(
            ["git", "non-existent-subcommand"],
            ProcessAnswer(
                returncode=1,
                stdout="",
                stderr="git: 'non-existent-subcommand' is not a git command.\n",
            ),
        )
        fake.answer(
            ["git", "hash-object", "--stdin"],
            ProcessAnswer(
                side_effect=subprocess.TimeoutExpired(
                    cmd=["git", "hash-object", "--stdin"], timeout=0.05
                )
            ),
        )
        return fake, True
    return DefaultProcessRunner(), False


@pytest.mark.parametrize("runner_instance", ["real", "fake"], indirect=True)
def test_sync_execution_contract(
    runner_instance: tuple[ProcessRunner, bool], tmp_path: Path
) -> None:
    """Both real and fake runners execute sync commands returning CompletedProcess with correct fields."""
    runner, _is_fake = runner_instance
    result = runner.run(["git", "version"], cwd=tmp_path)

    assert isinstance(result, subprocess.CompletedProcess)
    assert result.returncode == 0
    assert "git version" in result.stdout
    assert result.args == ["git", "version"]


@pytest.mark.parametrize("runner_instance", ["real", "fake"], indirect=True)
@pytest.mark.asyncio
async def test_async_execution_contract(
    runner_instance: tuple[ProcessRunner, bool], tmp_path: Path
) -> None:
    """Both real and fake runners execute async commands returning CompletedProcess with correct fields."""
    runner, _is_fake = runner_instance
    result = await runner.run_async(["git", "version"], cwd=tmp_path)

    assert isinstance(result, subprocess.CompletedProcess)
    assert result.returncode == 0
    assert "git version" in result.stdout
    assert result.args == ["git", "version"]


@pytest.mark.parametrize("runner_instance", ["real", "fake"], indirect=True)
def test_uv_flag_injection_contract(
    runner_instance: tuple[ProcessRunner, bool], tmp_path: Path
) -> None:
    """Both real and fake runners inject standardized preview flags into uv command lines."""
    runner, _is_fake = runner_instance
    prepared = runner.prepare_cmd(["uv", "run", "pytest"])
    assert prepared == [
        "uv",
        "--preview-features",
        "malware-check,check-command",
        "run",
        "pytest",
    ]


@pytest.mark.parametrize("runner_instance", ["real", "fake"], indirect=True)
def test_dry_run_mutating_command_contract(
    runner_instance: tuple[ProcessRunner, bool], tmp_path: Path
) -> None:
    """Under dry-run mode, mutating commands return PlannedProcessResult without starting child processes."""
    runner, _is_fake = runner_instance
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        res = runner.run(["git", "commit", "-m", "feat: new feature"], cwd=tmp_path)
        assert isinstance(res, PlannedProcessResult)
        assert isinstance(res, PlannedRequest)
        assert isinstance(res, subprocess.CompletedProcess)
        assert res.returncode == 0
        assert res.stdout == ""
        assert res.args == ["git", "commit", "-m", "feat: new feature"]
        assert res.method == "git"
        assert res.target == "commit -m feat: new feature"
    finally:
        set_dry_run(False)


@pytest.mark.parametrize("runner_instance", ["real", "fake"], indirect=True)
def test_dry_run_local_read_bypass_contract(
    runner_instance: tuple[ProcessRunner, bool], tmp_path: Path, git: Any
) -> None:
    """Under dry-run mode, commands declared as local reads execute normally."""
    runner, is_fake = runner_instance
    if not is_fake:
        git(tmp_path, "init")
        (tmp_path / "file.txt").write_text("hello", encoding="utf-8")

    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        res = runner.run(["git", "status"], cwd=tmp_path, local_read=True)
        assert not isinstance(res, PlannedRequest)
        assert isinstance(res, subprocess.CompletedProcess)
        assert res.returncode == 0

        res2 = runner.run(["git", "status"], cwd=tmp_path, intent="read")
        assert not isinstance(res2, PlannedRequest)
        assert isinstance(res2, subprocess.CompletedProcess)
        assert res2.returncode == 0
    finally:
        set_dry_run(False)


@pytest.mark.parametrize("runner_instance", ["real", "fake"], indirect=True)
def test_check_flag_raises_called_process_error(
    runner_instance: tuple[ProcessRunner, bool], tmp_path: Path
) -> None:
    """When check=True and command returns non-zero, CalledProcessError is raised."""
    runner, _is_fake = runner_instance
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        runner.run(["git", "non-existent-subcommand"], cwd=tmp_path, check=True)
    assert exc_info.value.returncode != 0


@pytest.mark.parametrize("runner_instance", ["real", "fake"], indirect=True)
def test_timeout_expired_contract(
    runner_instance: tuple[ProcessRunner, bool], tmp_path: Path
) -> None:
    """When a command exceeds timeout, TimeoutExpired is raised."""
    runner, is_fake = runner_instance
    if is_fake:
        assert isinstance(runner, ProcessFake)
        fake_runner = runner
        fake_runner.answer(["git", "slow_test"], ProcessAnswer(delay=1.0))
        with pytest.raises(subprocess.TimeoutExpired):
            fake_runner.run(["git", "slow_test"], cwd=tmp_path, timeout=0.01)
    else:
        with pytest.raises(subprocess.TimeoutExpired):
            runner.run(["git", "status"], cwd=tmp_path, timeout=1e-9)


def test_process_fake_call_recording(tmp_path: Path) -> None:
    """ProcessFake records detailed ProcessCall metadata for assertions."""
    fake = ProcessFake()
    fake.answer(["git", "status"], ProcessAnswer(returncode=0, stdout="clean\n"))
    res = fake.run(["git", "status"], cwd=tmp_path, intent="read", local_read=True)

    assert res.returncode == 0
    assert fake.call_count == 1
    call = fake.calls[0]
    assert isinstance(call, ProcessCall)
    assert call.argv == ("git", "status")
    assert call.cwd == tmp_path
    assert call.intent == "read"
    assert call.local_read is True


@pytest.mark.asyncio
async def test_process_fake_async_parity(tmp_path: Path) -> None:
    """ProcessFake run_async records calls and honors answers identically to sync run."""
    fake = ProcessFake()
    fake.answer(["git", "branch"], ProcessAnswer(returncode=0, stdout="* main\n"))
    res = await fake.run_async(["git", "branch"], cwd=tmp_path)

    assert res.returncode == 0
    assert res.stdout == "* main\n"
    assert fake.call_count == 1
    assert fake.calls[0].argv == ("git", "branch")


def test_process_fake_fixture_and_which_interception(process_fake: ProcessFake) -> None:
    """The process_fake fixture sets the seam and hermetically fakes shutil.which for non-passthrough tools."""
    import shutil

    from devops_cli.core.process import get_process_runner

    assert shutil.which("git") is not None
    fake_tool = shutil.which("some-arbitrary-cli-tool")
    assert fake_tool == "/usr/local/bin/some-arbitrary-cli-tool"

    assert get_process_runner() is process_fake
