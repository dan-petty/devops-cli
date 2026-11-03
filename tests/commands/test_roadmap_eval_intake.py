"""`devops roadmap eval intake` (#3185): the intake duplicate evaluation lives in the `eval` group.
The scoring itself is tested in `tests/roadmap/test_roadmap_duplicate_eval.py`."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Cli = Callable[..., Any]


def test_the_eval_group_lists_the_intake_evaluation(cli: Cli) -> None:
    result = cli("roadmap", "eval", "intake", "--help")
    assert (result.exit_code, "--dry-run" in result.output) == (0, True)


def test_the_old_top_level_name_is_gone(cli: Cli) -> None:
    result = cli("roadmap", "intake-eval")
    assert result.exit_code == 2
    listing = cli("roadmap", "--help").output
    assert "intake-eval" not in listing
