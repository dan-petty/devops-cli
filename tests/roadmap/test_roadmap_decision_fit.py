"""The fit of the cuts of a decision step (ADR 0019): the cuts skip as many cases as they can
without a loss on the fitted half, and the report counts the loss on the other half."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.decision_fit import (
    FitCase,
    evaluate_cuts,
    fit_cuts,
    fit_shared_cut,
    halves,
)


def _case(name: str, a: float, b: float, *, must_run: bool, weight: int = 1) -> FitCase:
    return FitCase(name, {"a": a, "b": b}, must_run=must_run, weight=weight)


FITTED = [
    _case("p1", 0.9, 0.1, must_run=True),
    _case("p2", 0.2, 0.8, must_run=True),
    _case("n1", 0.1, 0.1, must_run=False),
    _case("n2", 0.3, 0.2, must_run=False),
    _case("n3", 0.15, 0.05, must_run=False),
]


def test_the_cuts_lose_no_case_that_must_run_and_skip_the_rest() -> None:
    cuts = fit_cuts(FITTED)

    score = evaluate_cuts(FITTED, cuts)

    assert (score.lost, score.skipped) == (0, 3)


def test_a_case_that_must_run_beats_a_skip() -> None:
    mixed = [*FITTED, _case("p3", 0.05, 0.05, must_run=True)]

    score = evaluate_cuts(mixed, fit_cuts(mixed))

    assert (score.lost, score.skipped) == (0, 0)


def test_the_report_counts_the_loss_in_defects_on_the_other_half() -> None:
    cuts = fit_cuts(FITTED)
    other = [_case("q1", 0.1, 0.1, must_run=True, weight=4), _case("q2", 0.1, 0.0, must_run=False)]

    score = evaluate_cuts(other, cuts)

    assert (score.lost, score.lost_weight, score.skipped, score.cases) == (1, 4, 2, 2)


def test_the_flag_cut_needs_support_and_no_miss() -> None:
    cuts = fit_cuts(
        [*FITTED, _case("p4", 0.95, 0.0, must_run=True), _case("p5", 0.97, 0.0, must_run=True)]
    )

    assert cuts["a"].flag_at == pytest.approx(0.9)
    assert cuts["b"].flag_at == 1.0


def test_the_halves_are_stable_and_stratified() -> None:
    names = [f"c{i}" for i in range(10)]
    strata = {name: ("g" if i < 4 else "x") for i, name in enumerate(names)}

    first = halves(names, strata, seed=1)
    again = halves(list(reversed(names)), strata, seed=1)

    assert first == again
    assert sorted(first[0] + first[1]) == sorted(names)
    assert abs(len(first[0]) - len(first[1])) <= 1
    assert sum(strata[n] == "g" for n in first[0]) == 2


def test_the_shared_cut_is_one_number_below_the_lowest_case_that_must_run() -> None:
    cuts = fit_shared_cut(FITTED)

    assert {cut.continue_below for cut in cuts.values()} == {0.55}
    score = evaluate_cuts(FITTED, cuts)
    assert (score.lost, score.skipped) == (0, 3)


def test_the_shared_cut_with_no_case_below_keeps_a_margin() -> None:
    only = [_case("p1", 0.5, 0.1, must_run=True), _case("p2", 0.6, 0.1, must_run=True)]

    assert fit_shared_cut(only)["a"].continue_below == pytest.approx(0.45)
    assert fit_shared_cut([_case("n", 0.1, 0.1, must_run=False)])["a"].continue_below == 1.0
