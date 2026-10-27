"""Tests for which `devops ci` runs take a gate slot, and what a run does while it waits (#2336)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.ci.cache import CICachedCheck, compute_workspace_fingerprint, save_ci_cache
from devops_cli.ci.gate_slots import gate_slot, gate_slots_directory
from devops_cli.commands.ci import app
from devops_cli.config.defaults import DEFAULT_CI_GATE_POLL_SECONDS
from devops_cli.core import clock as clock_seam
from devops_cli.core.repo import find_worktree_root
from devops_cli.lang import MESSAGES
from devops_cli.output import format_duration
from tests.support.fakes.process import ProcessFake
from tests.support.session_spawns import RecordedSpawn, record_spawns

pytestmark = pytest.mark.usefixtures("refuse_nested_test_runs")

runner = CliRunner()

HOLDER = "4321 /work/w-1111"
WAIT_METRIC = "ci.gate_slot_wait_seconds"

Started = Callable[[], list[tuple[str, ...]]]
"""The argv of every process the command under test has started so far."""


class HeldSlot:
    """The only gate slot, held by another run until the gate under test first sleeps.

    The gate polls through the clock seam, so the first poll is the moment the other run ends:
    the slot is given back there, and the processes started until then are kept. A test reads
    `started_while_held` to see what the gate started while it waited; it is None when the gate
    never waited.
    """

    def __init__(self, started: Started, monkeypatch: pytest.MonkeyPatch, clock: Any) -> None:
        self._started = started
        self._clock = clock
        self._other_run = gate_slot(
            gate_slots_directory(), 1, holder=HOLDER, notify=lambda _message: None
        )
        self.started_while_held: list[tuple[str, ...]] | None = None
        self.on_poll: Callable[[], None] | None = None
        monkeypatch.setattr(clock_seam, "sleep", self._poll)

    def _poll(self, seconds: float) -> None:
        if self.on_poll is not None:
            self.on_poll()
        if self.started_while_held is None:
            self.started_while_held = self._started()
            self._other_run.__exit__(None, None, None)
        self._clock.sleep(seconds)

    def hold(self) -> None:
        self._other_run.__enter__()

    def release(self) -> None:
        if self.started_while_held is None:
            self._other_run.__exit__(None, None, None)


def _ran(argvs: list[tuple[str, ...]] | None, program: str) -> bool:
    return any(program in argv for argv in argvs or [])


@pytest.fixture
def spawns(monkeypatch: pytest.MonkeyPatch) -> list[RecordedSpawn]:
    """The processes the gate starts, which `asyncio.create_subprocess_exec` is doubled to record."""
    return record_spawns(monkeypatch)


@pytest.fixture
def started(spawns: list[RecordedSpawn]) -> Started:
    return lambda: [tuple(spawn.argv) for spawn in spawns]


@pytest.fixture
def held_slot(
    config: Callable[..., Path], started: Started, monkeypatch: pytest.MonkeyPatch, clock: Any
) -> Iterator[HeldSlot]:
    """`ci.gate_slots` is 1, and another run holds the slot."""
    config(ci={"gate_slots": 1})
    held = HeldSlot(started, monkeypatch, clock)
    held.hold()
    try:
        yield held
    finally:
        held.release()


def test_a_gate_with_a_heavy_check_waits_for_a_free_slot(
    held_slot: HeldSlot, started: Started
) -> None:
    result = runner.invoke(app, ["--only", "typecheck", "--check", "--no-cache"])

    assert result.exit_code == 0, result.output
    assert held_slot.started_while_held is not None
    assert not _ran(held_slot.started_while_held, "mypy")
    assert _ran(started(), "mypy")
    assert "Allowed at one time: 1" in result.output
    assert "process 4321 in /work/w-1111" in result.output


def test_the_wait_is_recorded_and_is_not_part_of_the_gate_time(
    held_slot: HeldSlot, captured: Any
) -> None:
    result = runner.invoke(app, ["--only", "typecheck", "--check", "--no-cache"])

    assert result.exit_code == 0, result.output
    assert [value for _, value in captured.points(WAIT_METRIC)] == [
        pytest.approx(DEFAULT_CI_GATE_POLL_SECONDS)
    ]
    assert f"Total Elapsed: {format_duration(0.0)}" in result.output


def test_a_gate_with_only_light_checks_takes_no_slot(held_slot: HeldSlot, started: Started) -> None:
    result = runner.invoke(app, ["--only", "lint,format", "--check", "--no-cache"])

    assert result.exit_code == 0, result.output
    assert held_slot.started_while_held is None
    assert _ran(started(), "ruff")


def test_the_full_suite_test_command_waits_for_a_free_slot(
    held_slot: HeldSlot, started: Started
) -> None:
    result = runner.invoke(app, ["test"])

    assert result.exit_code == 0, result.output
    assert held_slot.started_while_held is not None
    assert not _ran(held_slot.started_while_held, "pytest")
    assert _ran(started(), "pytest")


def test_the_coverage_command_waits_for_a_free_slot(
    config: Callable[..., Path],
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
    clock: Any,
) -> None:
    config(ci={"gate_slots": 1})
    held = HeldSlot(lambda: [call.argv for call in process_fake.calls], monkeypatch, clock)
    held.hold()
    try:
        result = runner.invoke(app, ["coverage"])
    finally:
        held.release()

    assert result.exit_code == 0, result.output
    assert held.started_while_held is not None
    assert not _ran(held.started_while_held, "pytest")
    assert _ran([call.argv for call in process_fake.calls], "pytest")


@pytest.mark.parametrize(
    "arguments",
    [["test", "tests/test_ci_gate_slots.py"], ["test", "-n", "4"]],
    ids=["narrowed by a path", "narrowed by -n"],
)
def test_a_narrowed_test_run_never_waits(
    held_slot: HeldSlot, started: Started, arguments: list[str]
) -> None:
    result = runner.invoke(app, arguments)

    assert result.exit_code == 0, result.output
    assert held_slot.started_while_held is None
    assert _ran(started(), "pytest")


def test_a_dry_run_takes_no_slot_and_does_not_wait(held_slot: HeldSlot) -> None:
    result = runner.invoke(app, ["--dry-run"])

    assert result.exit_code == 0, result.output
    assert held_slot.started_while_held is None


def test_a_dry_run_makes_no_slot_file(config: Callable[..., Path]) -> None:
    config(ci={"gate_slots": 1})

    result = runner.invoke(app, ["--dry-run"])

    assert result.exit_code == 0, result.output
    assert not gate_slots_directory().exists()


def test_a_cached_verdict_takes_no_slot(held_slot: HeldSlot) -> None:
    root = find_worktree_root()
    options = {"fix": False, "check": True}
    fingerprint = compute_workspace_fingerprint(root=root, options=options)
    assert fingerprint is not None
    save_ci_cache(
        fingerprint=fingerprint[0],
        head_sha=fingerprint[1],
        checks=[CICachedCheck(name="test", display_title="Tests", passed=True, duration_seconds=1)],
        options=options,
        passed=True,
        root=root,
    )

    result = runner.invoke(app, ["--check"])

    assert result.exit_code == 0, result.output
    assert MESSAGES.ci.cache_hit in result.output
    assert held_slot.started_while_held is None


def test_a_stop_signal_while_a_gate_waits_ends_the_run_and_holds_no_slot(
    held_slot: HeldSlot, started: Started
) -> None:
    def stop() -> None:
        raise KeyboardInterrupt

    held_slot.on_poll = stop

    result = runner.invoke(app, ["--only", "typecheck", "--check", "--no-cache"])

    assert result.exit_code != 0
    assert not _ran(started(), "mypy")
    held_slot.release()
    with gate_slot(
        gate_slots_directory(), 1, holder=HOLDER, notify=lambda _message: None
    ) as waited:
        assert waited == 0
