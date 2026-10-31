"""Tests for CLI Tab Resolution behaviour in reactive dashboard."""

from __future__ import annotations

import pytest

from devops_cli.commands.dashboard import TAB_NUM_MAP
from devops_cli.config.constants import (
    CONST_DASHBOARD_DOMAINS,
)


@pytest.mark.parametrize(
    ("selector", "expected"),
    [(str(i), f"tab-{d}") for i, d in enumerate(CONST_DASHBOARD_DOMAINS, start=1)]
    + [(d, f"tab-{d}") for d in CONST_DASHBOARD_DOMAINS],
)
def test_every_domain_is_selectable_by_number_and_by_name(selector: str, expected: str) -> None:
    """A tab reachable in the TUI must also be selectable from the command line.

    The map is derived from the configured domains rather than written out, so adding a
    domain cannot leave the `--tab` option silently behind.
    """
    assert TAB_NUM_MAP[selector] == expected
