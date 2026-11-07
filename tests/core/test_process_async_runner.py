"""The async start of a program goes through the active process runner, as the sync start does."""

from __future__ import annotations

import subprocess

import pytest

from devops_cli.core.process import run_subprocess_async
from devops_cli.dry_run import set_dry_run
from devops_cli.dry_run.requests import PlannedRequest
from tests.support.fakes.process import ProcessAnswer, ProcessFake


async def test_an_async_start_is_answered_by_the_active_runner(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A test replaces `subprocess.run`, the way the old reroute looked for: the start is still
    the runner's, not a start of its own."""
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: pytest.fail("started a process"))
    process_fake.answer("npm audit", ProcessAnswer(returncode=1, stdout="report"))

    result = await run_subprocess_async(["npm", "audit"])

    assert (result.returncode, result.stdout, [call.argv for call in process_fake.calls]) == (
        1,
        "report",
        [("npm", "audit")],
    )


async def test_an_async_start_in_a_dry_run_plans_the_command_and_runs_nothing() -> None:
    set_dry_run(True)
    try:
        result = await run_subprocess_async(["npm", "audit"])
    finally:
        set_dry_run(False)

    assert isinstance(result, PlannedRequest)
    assert result.returncode == 0
