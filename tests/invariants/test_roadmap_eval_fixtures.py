"""The committed fixtures of `devops roadmap eval implement` (#3030): the set loads against its
schema, holds the items the baseline needs, keeps every recorded result as recorded, and stays
small."""

from __future__ import annotations

import pytest

from devops_cli.roadmap.implement_eval import LoadedCase, load_cases
from devops_cli.roadmap.implement_eval_run import check_recorded
from tests.support.paths import FIXTURES

ROOT = FIXTURES / "roadmap_eval" / "implement"
MAX_BYTES = 300_000


@pytest.fixture(scope="module")
def cases() -> list[LoadedCase]:
    return load_cases(ROOT)


def test_the_set_holds_at_least_ten_fixtures_with_the_items_of_the_baseline(
    cases: list[LoadedCase],
) -> None:
    issues = {case.case.issue for case in cases}

    assert len(cases) >= 10
    assert {2175, 2735} <= issues


def test_the_names_are_unique_and_every_base_is_a_full_sha(cases: list[LoadedCase]) -> None:
    names = [case.name for case in cases]

    assert len(names) == len(set(names))
    assert all(len(case.case.base) == 40 for case in cases)


def test_the_set_holds_a_result_that_fails_no_diff_property_and_one_that_fails_some(
    cases: list[LoadedCase],
) -> None:
    fails = [result.fails for case in cases for result in case.case.results]

    assert () in fails
    assert any(fails)


def test_the_set_holds_a_deletion_item_with_a_corrected_plan_and_a_scratch_file_result(
    cases: list[LoadedCase],
) -> None:
    by_name = {case.name: case for case in cases}
    scratch = by_name["2175-dead-code-first-plan-group-2"].case.results

    assert "2175-dead-code" in by_name
    assert [(result.name, [p.value for p in result.fails]) for result in scratch] == [
        ("stopped-with-scratch-file", ["diff_scope", "no_scratch"])
    ]


def test_every_recorded_result_fails_the_diff_properties_it_is_recorded_to_fail(
    cases: list[LoadedCase],
) -> None:
    reports = [report for case in cases for report in check_recorded(case)]

    assert reports
    assert [(r.fixture, r.result) for r in reports if r.matches is not True] == []


def test_the_set_stays_small() -> None:
    size = sum(path.stat().st_size for path in ROOT.rglob("*") if path.is_file())

    assert size < MAX_BYTES
