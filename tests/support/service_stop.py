"""The error a request gets when the Service is stopping (#2753)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from devops_cli.exceptions import RoadmapRunError
from devops_cli.server.service import RequestBudget

_NOW = datetime(2026, 10, 30, 12, tzinfo=UTC)


def stop_error() -> RoadmapRunError:
    """The error of a request that a closed budget refuses because its window is full: the
    budget itself raises it, so a test holds no copy of its class or its text."""
    budget = RequestBudget(lambda: _NOW, 1)
    budget.admit()
    budget.close()
    with pytest.raises(RoadmapRunError) as raised:
        budget.admit()
    return raised.value
