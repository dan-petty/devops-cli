"""A poll that reads no check is a poll with no data and reports pending, not ready (#4927)."""

from __future__ import annotations

import devops_cli.github.pr_monitor as pr_monitor
from devops_cli.github.pr_monitor import PRMonitorStatus


def test_settled_result_with_empty_checks_reports_not_ready() -> None:
    """A settled result with no check runs reported must fail closed and not report ready (#4927)."""
    status = PRMonitorStatus(number=4916, head_sha="7316135", checks=[], blockers=[])
    settle_fn = getattr(pr_monitor, "settled_result", getattr(pr_monitor, "_settled_result", None))
    assert settle_fn is not None
    result = settle_fn(status, 4916)
    assert result.success is False
    assert result.exit_code != 0
    assert "ready" not in result.message.lower()
