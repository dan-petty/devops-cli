"""The Service's poll intervals (#3672): a repository with no open work polls less often."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from devops_cli.config.settings import ServiceConfig


def test_the_idle_interval_must_not_be_shorter_than_the_normal_one() -> None:
    with pytest.raises(ValidationError) as raised:
        ServiceConfig(poll_interval_seconds=120, poll_interval_idle_seconds=60)

    message = str(raised.value)
    assert (
        "poll_interval_idle_seconds" in message,
        "poll_interval_seconds" in message,
    ) == (True, True)
