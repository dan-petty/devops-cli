"""A failed read of the pull request is one poll with no data, not the end of the watch (#4838)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github import pr_monitor
from devops_cli.github.pr_monitor import PRMonitorStatus, monitor_pr


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    clock = _Clock()
    monkeypatch.setattr(pr_monitor.clock, "monotonic", clock.monotonic)
    monkeypatch.setattr(pr_monitor.clock, "sleep", clock.sleep)
    return clock


def _terminal() -> PRMonitorStatus:
    return PRMonitorStatus(number=7, merged=True)


def test_a_failed_read_says_so_and_polls_again(
    fake_clock: _Clock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    answers: list[Callable[[], Any]] = [
        lambda: (_ for _ in ()).throw(GitHubOperationError("timed out")),
        lambda: (_ for _ in ()).throw(GitHubOperationError("timed out")),
        _terminal,
    ]
    monkeypatch.setattr(pr_monitor, "get_pr_monitoring_status", lambda *a, **k: answers.pop(0)())

    result = monitor_pr("owner", "repo", 7, timeout=1800, interval=60)

    assert result.success is True
    assert len(fake_clock.sleeps) == 2
    assert "1 of 3" in capsys.readouterr().out


def test_three_failed_reads_in_a_row_end_the_watch_with_the_last_error(
    fake_clock: _Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        pr_monitor,
        "get_pr_monitoring_status",
        lambda *a, **k: (_ for _ in ()).throw(GitHubOperationError("timed out")),
    )

    with pytest.raises(GitHubOperationError, match="timed out"):
        monitor_pr("owner", "repo", 7, timeout=1800, interval=60)
