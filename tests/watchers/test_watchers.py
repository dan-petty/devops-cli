"""Tests for the live resource state watcher and the debounced file watcher.

Time is `ClockFake`, so a watcher's poll and debounce waits take no real time and a test reads
them from `clock.waits`. A test changes the files while a watcher waits, through the clock's
`after_each_sleep` hook, as an editor changes them between two polls.
"""

from __future__ import annotations

import os
from pathlib import Path

from rich.text import Text

from devops_cli.watchers.file_watcher import DebouncedFileWatcher
from devops_cli.watchers.live_resource import LiveResourceWatcher
from tests.support.fakes.clock import ClockFake


def test_live_resource_watcher_bounded_iterations(clock: ClockFake) -> None:
    """LiveResourceWatcher renders once to open, then once per iteration, and waits between."""
    renders = 0

    def render_state() -> Text:
        nonlocal renders
        renders += 1
        return Text(f"State iteration {renders}")

    watcher = LiveResourceWatcher(render_state, interval_seconds=0.5, name="test_watcher")
    watcher.watch(max_iterations=3)

    assert (renders, clock.waits) == (4, [0.5, 0.5])


def test_live_resource_watcher_manual_stop(clock: ClockFake) -> None:
    """Calling stop() from the render function ends the watcher loop after that render."""
    renders = 0

    def render_state() -> Text:
        nonlocal renders
        renders += 1
        if renders >= 3:
            watcher.stop()
        return Text(f"Count {renders}")

    watcher = LiveResourceWatcher(render_state, interval_seconds=0.5, name="test_manual_stop")
    watcher.watch()

    assert (renders, clock.waits) == (3, [0.5, 0.5])


def test_live_resource_watcher_keyboard_interrupt_ends_the_watch(clock: ClockFake) -> None:
    """A Ctrl+C during the wait ends the watch without an error, and the watcher runs again."""
    renders = 0

    def render_state() -> Text:
        nonlocal renders
        renders += 1
        return Text(f"Count {renders}")

    def interrupt() -> None:
        raise KeyboardInterrupt

    watcher = LiveResourceWatcher(render_state, interval_seconds=0.5, name="test_interrupt")
    clock.after_each_sleep(interrupt)
    watcher.watch()
    interrupted_at = renders
    clock.after_each_sleep(lambda: None)
    watcher.watch(max_iterations=1)

    assert (interrupted_at, renders) == (2, 4)


def test_debounced_file_watcher_detects_changes(tmp_path: Path, clock: ClockFake) -> None:
    """DebouncedFileWatcher should detect new and modified files in watched directories."""
    file1 = tmp_path / "app.py"
    file1.write_text("print('v1')", encoding="utf-8")

    watcher = DebouncedFileWatcher(
        [tmp_path],
        lambda files: None,
        debounce_ms=50,
        poll_interval_seconds=0.01,
        name="test_file_watcher",
    )

    # Initial scan via check_changes
    initial_changes = watcher.check_changes()
    assert file1 in initial_changes

    # Modify file
    clock.sleep(0.05)
    file1.write_text("print('v2')", encoding="utf-8")
    os.utime(file1, (file1.stat().st_mtime + 1, file1.stat().st_mtime + 1))

    subsequent_changes = watcher.check_changes()
    assert file1 in subsequent_changes


def test_debounced_file_watcher_ignores_hidden_and_git(tmp_path: Path) -> None:
    """DebouncedFileWatcher should ignore files inside .git, .data, and hidden directories."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "config").write_text("git config", encoding="utf-8")

    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "cache.json").write_text("{}", encoding="utf-8")

    watcher = DebouncedFileWatcher(
        [tmp_path],
        lambda files: None,
        name="test_ignore",
    )
    changes = watcher.check_changes()
    assert all(".git" not in str(p) and ".data" not in str(p) for p in changes)


def test_debounced_file_watcher_single_file_and_missing(tmp_path: Path) -> None:
    """DebouncedFileWatcher handles single file path and non-existent path."""
    single_file = tmp_path / "single.py"
    single_file.write_text("x = 1", encoding="utf-8")
    missing_dir = tmp_path / "nonexistent"

    watcher = DebouncedFileWatcher(
        [single_file, missing_dir],
        lambda files: None,
        name="test_single_and_missing",
    )
    changes = watcher.check_changes()
    assert single_file in changes


def test_debounced_file_watcher_skips_a_hidden_file_target(tmp_path: Path) -> None:
    """A watched file with a hidden name is never reported."""
    hidden_file = tmp_path / ".hidden.py"
    hidden_file.write_text("# hidden", encoding="utf-8")

    watcher = DebouncedFileWatcher([hidden_file], lambda files: None, name="test_hidden")

    assert watcher.check_changes() == []


def test_debounced_file_watcher_skips_an_entry_it_cannot_stat(tmp_path: Path) -> None:
    """A link that points nowhere cannot be read, so the scan skips it and reports the rest."""
    readable = tmp_path / "readable.py"
    readable.write_text("x = 1", encoding="utf-8")
    (tmp_path / "dangling.py").symlink_to(tmp_path / "gone.py")

    watcher = DebouncedFileWatcher([tmp_path], lambda files: None, name="test_unreadable")

    assert watcher.check_changes() == [readable.resolve()]


def test_debounced_file_watcher_notifies_after_the_debounce_wait(
    tmp_path: Path, clock: ClockFake
) -> None:
    """A file that changes between two polls is reported once, after the debounce wait."""
    script = tmp_path / "script.py"
    script.write_text("a = 1", encoding="utf-8")
    notified: list[list[Path]] = []
    edited = False

    def edit_during_the_poll_wait() -> None:
        nonlocal edited
        if edited:
            return
        edited = True
        script.write_text("a = 2", encoding="utf-8")
        later = script.stat().st_mtime + 10
        os.utime(script, (later, later))

    watcher = DebouncedFileWatcher(
        [tmp_path],
        notified.append,
        debounce_ms=100,
        poll_interval_seconds=0.5,
        name="test_watch_loop",
    )
    clock.after_each_sleep(edit_during_the_poll_wait)

    watcher.watch(max_iterations=2)

    assert (notified, clock.waits) == ([[script.resolve()]], [0.5, 0.1])


def test_debounced_file_watcher_stops_when_interrupted(tmp_path: Path, clock: ClockFake) -> None:
    """A Ctrl+C during the poll wait ends the watch without an error."""
    (tmp_path / "script.py").write_text("a = 1", encoding="utf-8")
    notified: list[list[Path]] = []

    def interrupt() -> None:
        raise KeyboardInterrupt

    watcher = DebouncedFileWatcher(
        [tmp_path], notified.append, poll_interval_seconds=0.5, name="test_interrupt"
    )
    clock.after_each_sleep(interrupt)

    watcher.watch(max_iterations=5)

    assert (notified, clock.waits) == ([], [0.5])
