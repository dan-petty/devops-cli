"""Tests for the host-wide gate slots that limit how many CPU-heavy `devops ci` gates run at once
(#2336)."""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

import pytest

from devops_cli.ci.gate_slots import gate_slot, gate_slot_count
from devops_cli.config.defaults import DEFAULT_CI_GATE_POLL_SECONDS
from devops_cli.core import clock as clock_seam
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

HOLDER = "4321 /work/w-1111"


def _wait_in_thread(
    directory: Path, slots: int, messages: list[str], waited: list[float]
) -> tuple[threading.Thread, threading.Event]:
    """A thread that takes a slot, records how long it waited and holds the slot until its caller
    ends the test; `entered` is set once the thread has the slot."""
    entered = threading.Event()

    def take() -> None:
        with gate_slot(directory, slots, holder="9 /work/w-2222", notify=messages.append) as secs:
            waited.append(secs)
            entered.set()

    thread = threading.Thread(target=take, daemon=True)
    thread.start()
    return thread, entered


def test_a_run_takes_a_free_slot_at_once(tmp_path: Path, clock) -> None:
    messages: list[str] = []

    with gate_slot(tmp_path, 1, holder=HOLDER, notify=messages.append) as waited:
        assert waited == 0
    assert messages == []


def test_a_run_waits_while_every_slot_is_held_and_starts_when_one_is_free(
    tmp_path: Path, clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[str] = []
    other_run = gate_slot(tmp_path, 1, holder=HOLDER, notify=messages.append)
    other_run.__enter__()
    other_run_holds_the_slot = [True]

    def poll(seconds: float) -> None:
        # The other run ends during the first poll, so the wait is one poll long.
        if other_run_holds_the_slot:
            other_run_holds_the_slot.clear()
            other_run.__exit__(None, None, None)
        clock.sleep(seconds)

    monkeypatch.setattr(clock_seam, "sleep", poll)

    with gate_slot(tmp_path, 1, holder="9 /work/w-2222", notify=messages.append) as waited:
        assert not other_run_holds_the_slot
        assert waited == pytest.approx(DEFAULT_CI_GATE_POLL_SECONDS)

    assert len(messages) == 1


def test_a_second_slot_lets_a_second_run_start_at_once(tmp_path: Path, clock) -> None:
    messages: list[str] = []
    waited: list[float] = []

    with gate_slot(tmp_path, 2, holder=HOLDER, notify=messages.append):
        thread, entered = _wait_in_thread(tmp_path, 2, messages, waited)
        assert entered.wait(THREAD_HANDOFF_BOUND_SECONDS)
        thread.join(THREAD_HANDOFF_BOUND_SECONDS)

    assert waited == [0]


def test_a_slot_is_free_after_the_run_raises(tmp_path: Path, clock) -> None:
    messages: list[str] = []

    with pytest.raises(RuntimeError, match="the gate failed"):
        with gate_slot(tmp_path, 1, holder=HOLDER, notify=messages.append):
            raise RuntimeError("the gate failed")

    with gate_slot(tmp_path, 1, holder=HOLDER, notify=messages.append) as waited:
        assert waited == 0


def test_a_stop_signal_ends_the_wait_and_holds_no_slot(
    tmp_path: Path, clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[str] = []

    def stop(_seconds: float) -> None:
        raise KeyboardInterrupt

    with gate_slot(tmp_path, 1, holder=HOLDER, notify=messages.append):
        monkeypatch.setattr(clock_seam, "sleep", stop)
        with pytest.raises(KeyboardInterrupt):
            with gate_slot(tmp_path, 1, holder=HOLDER, notify=messages.append):
                pytest.fail("the run took a slot that another run held")

    monkeypatch.setattr(clock_seam, "sleep", clock.sleep)
    with gate_slot(tmp_path, 1, holder=HOLDER, notify=messages.append) as waited:
        assert waited == 0


@pytest.mark.live("python")
def test_a_slot_is_free_after_its_holder_is_killed(tmp_path: Path, clock) -> None:
    holder = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys, time\n"
            "from pathlib import Path\n"
            "from devops_cli.ci.gate_slots import gate_slot\n"
            "with gate_slot(Path(sys.argv[1]), 1, holder='1 /w', notify=print):\n"
            "    print('held', flush=True)\n"
            "    time.sleep(3600)\n",
            str(tmp_path),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout is not None
    try:
        # The child prints once it holds the slot; the read returns at once if it exits instead.
        assert holder.stdout.readline().strip() == "held"
    finally:
        holder.kill()
        holder.wait()
        holder.stdout.close()

    with gate_slot(tmp_path, 1, holder=HOLDER, notify=lambda _message: None) as waited:
        assert waited == 0


def test_a_waiting_run_names_the_process_and_worktree_of_each_holder(tmp_path: Path, clock) -> None:
    messages: list[str] = []
    waited: list[float] = []

    with gate_slot(tmp_path, 1, holder=HOLDER, notify=lambda _message: None):
        thread, entered = _wait_in_thread(tmp_path, 1, messages, waited)
        assert wait_until(lambda: bool(messages))

    assert entered.wait(THREAD_HANDOFF_BOUND_SECONDS)
    thread.join(THREAD_HANDOFF_BOUND_SECONDS)
    assert len(messages) == 1
    assert "Allowed at one time: 1" in messages[0]
    assert "process 4321 in /work/w-1111" in messages[0]


@pytest.mark.parametrize(
    ("configured", "cpus", "expected"),
    [
        (None, 4, 1),
        (None, 16, 1),
        (None, 31, 1),
        (None, 32, 2),
        (None, 3, 1),
        (None, 64, 4),
        (5, 4, 5),
    ],
)
def test_the_number_of_slots_is_the_setting_or_one_for_each_sixteen_cpus(
    configured: int | None, cpus: int, expected: int
) -> None:
    assert gate_slot_count(configured, cpus=cpus) == expected
