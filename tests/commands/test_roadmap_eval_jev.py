"""`devops roadmap eval jev` (#4298): the Jev comparison lives in the `eval` group, and a dry run
or a run over the call limit makes no request. The scoring is tested in
`tests/roadmap/test_roadmap_jev_eval.py`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.duplicate_eval import load_cases
from devops_cli.roadmap.jev_eval import load_label_cases, planned_calls

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from tests.support.fakes.model import ModelFake

CALLS = planned_calls(len(load_cases()), len(load_label_cases()))


def test_the_eval_group_lists_the_jev_comparison(cli: Callable[..., Any]) -> None:
    result = cli("roadmap", "eval", "jev", "--help")
    assert (result.exit_code, "--max-calls" in result.output, "--dry-run" in result.output) == (
        0,
        True,
        True,
    )


def test_a_dry_run_names_the_calls_and_makes_no_model_call(
    cli: Callable[..., Any], model_fake: ModelFake
) -> None:
    result = cli("roadmap", "eval", "jev", "--dry-run")

    assert result.exit_code == 0
    assert f"{CALLS} call(s)" in " ".join(result.output.split())
    assert model_fake.call_count == 0


def test_a_run_that_needs_more_calls_than_the_limit_stops_before_the_first_call(
    cli: Callable[..., Any], model_fake: ModelFake
) -> None:
    result = cli("roadmap", "eval", "jev", "--max-calls", str(CALLS - 1))

    expected = MESSAGES.roadmap.jev_compare_over_limit.format(calls=CALLS, limit=CALLS - 1)
    assert (result.exit_code, expected in " ".join(result.output.split())) == (2, True)
    assert model_fake.call_count == 0
