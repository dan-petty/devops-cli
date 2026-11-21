"""`devops roadmap step`: the group of the roadmap steps (ADR 0021, section 8)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]


def test_the_group_has_no_scaffold_step(cli: Cli) -> None:
    """The scaffold step is gone (#6654): the first push of a job makes the item branch."""
    result = cli("roadmap", "step", "scaffold", "--help")

    assert (result.exit_code, "No such command 'scaffold'" in result.output) == (2, True)
