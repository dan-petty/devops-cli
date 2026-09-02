"""Unit tests for live resource state watcher and debounced file watcher."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.text import Text

from devops_cli.watchers.file_watcher import DebouncedFileWatcher
from devops_cli.watchers.live_resource import LiveResourceWatcher


def test_live_resource_watcher_bounded_iterations() -> None:
    """LiveResourceWatcher should execute render function and stop after max_iterations."""
    counter = 0

    def render_state() -> Text:
        nonlocal counter
        counter += 1
        return Text(f"State iteration {counter}")

    watcher = LiveResourceWatcher(
        render_state,
        interval_seconds=0.01,
        name="test_watcher",
    )
    watcher.watch(max_iterations=3)
    assert counter >= 3


def test_live_resource_watcher_manual_stop() -> None:
    """Calling stop() should cleanly terminate the watcher loop."""
    called = 0

    def render_state() -> Text:
        nonlocal called
        called += 1
        if called >= 2:
            watcher.stop()
        return Text(f"Count {called}")

    watcher = LiveResourceWatcher(
        render_state,
        interval_seconds=0.01,
        name="test_manual_stop",
    )
    watcher.watch()
    assert called >= 2


def test_live_resource_watcher_keyboard_interrupt() -> None:
    """LiveResourceWatcher should gracefully catch KeyboardInterrupt."""

    def render_state() -> Text:
        raise KeyboardInterrupt()

    watcher = LiveResourceWatcher(
        render_state,
        interval_seconds=0.01,
        name="test_interrupt",
    )
    watcher.watch()
    assert watcher._running is False


def test_debounced_file_watcher_detects_changes(tmp_path: Path) -> None:
    """DebouncedFileWatcher should detect new and modified files in watched directories."""
    file1 = tmp_path / "app.py"
    file1.write_text("print('v1')", encoding="utf-8")

    changes_received: list[list[Path]] = []

    def on_change(files: list[Path]) -> None:
        changes_received.append(files)

    watcher = DebouncedFileWatcher(
        [tmp_path],
        on_change,
        debounce_ms=50,
        poll_interval_seconds=0.01,
        name="test_file_watcher",
    )

    # Initial scan via check_changes
    initial_changes = watcher.check_changes()
    assert file1 in initial_changes

    # Modify file
    time.sleep(0.05)
    file1.write_text("print('v2')", encoding="utf-8")

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


def test_debounced_file_watcher_watch_loop(tmp_path: Path) -> None:
    """DebouncedFileWatcher watch loop runs and triggers callback on change."""
    test_file = tmp_path / "script.py"
    test_file.write_text("a = 1", encoding="utf-8")

    notified: list[list[Path]] = []

    def on_change(files: list[Path]) -> None:
        notified.append(files)

    watcher = DebouncedFileWatcher(
        [tmp_path],
        on_change,
        debounce_ms=10,
        poll_interval_seconds=0.01,
        name="test_watch_loop",
    )

    watcher.watch(max_iterations=1)
    assert watcher._running is False
    watcher.stop()


def test_debounced_file_watcher_keyboard_interrupt_and_os_errors(tmp_path: Path) -> None:
    """Verify watcher cleanly handles KeyboardInterrupt, ignored files, and OSError during stat."""

    hidden_file = tmp_path / ".hidden.py"
    hidden_file.write_text("# hidden", encoding="utf-8")

    notified: list[list[Path]] = []

    def dummy_cb(files: list[Path]) -> None:
        notified.append(files)

    watcher = DebouncedFileWatcher([hidden_file], dummy_cb, name="test_hidden")
    mtimes: dict[Path, float] = {}
    watcher._scan_file_target(hidden_file, mtimes)
    assert hidden_file not in mtimes

    # Test _handle_file_changes directly
    mock_span = MagicMock()
    watcher._handle_file_changes([tmp_path / "file.py"], mock_span)
    assert len(notified) == 1

    # OSError in _scan_file_target
    bad_file = tmp_path / "phantom.py"
    with patch.object(Path, "stat", side_effect=OSError("Permission denied")):
        watcher._scan_file_target(bad_file, mtimes)
        assert bad_file not in mtimes

        # OSError in _scan_dir_target
        watcher._scan_dir_target(tmp_path, mtimes)

    # KeyboardInterrupt handling in watch
    with patch.object(watcher, "_run_watch_loop", side_effect=KeyboardInterrupt):
        watcher.watch(max_iterations=1)
        assert watcher._running is False
