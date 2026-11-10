"""`devops roadmap eval jev` (#4298): the Jev comparison lives in the `eval` group, and a dry run
or a run over the call limit makes no request. The scoring is tested in
`tests/roadmap/test_roadmap_jev_eval.py`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.duplicate_eval import load_cases
from devops_cli.roadmap.intake.intake_jev_shadow import ShadowIntakeModel
from devops_cli.roadmap.jev_eval import load_label_cases, planned_calls
from devops_cli.roadmap.stores.store import install_roadmap_store
from tests.support.roadmap_intake import REPO, FakeModel, Roadmap

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from tests.support.fakes.jev import JevFake
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


def test_from_shadow_prints_the_report_of_the_records_and_makes_no_model_call(
    cli: Callable[..., Any], model_fake: ModelFake, jev: JevFake
) -> None:
    roadmap = Roadmap()
    roadmap.issue("Cache embeddings")
    roadmap.run(ShadowIntakeModel(FakeModel(), jev.model))
    install_roadmap_store(lambda repo, **_: roadmap.store)

    result = cli("roadmap", "eval", "jev", "--from-shadow", "--repo", REPO)

    assert result.exit_code == 0
    text = " ".join(result.output.split())
    assert "1 issue(s)" in text
    assert "- priority: 1 record(s)" in text
    assert model_fake.call_count == 0


def test_from_shadow_with_no_record_says_how_to_start_one(cli: Callable[..., Any]) -> None:
    install_roadmap_store(lambda repo, **_: Roadmap().store)

    result = cli("roadmap", "eval", "jev", "--from-shadow", "--repo", REPO)

    assert (
        result.exit_code,
        "roadmap.intake.jev to shadow" in " ".join(result.output.split()),
    ) == (
        0,
        True,
    )


def test_from_shadow_with_dry_run_opens_no_store(cli: Callable[..., Any]) -> None:
    def refuse(repo: str, **_: object) -> object:
        raise AssertionError("opened a store")

    install_roadmap_store(refuse)  # type: ignore[arg-type]

    result = cli("roadmap", "eval", "jev", "--from-shadow", "--dry-run", "--repo", REPO)

    assert (result.exit_code, "no request was made" in " ".join(result.output.split())) == (0, True)
