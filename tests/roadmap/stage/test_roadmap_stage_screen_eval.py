"""The score of the verify screen against the reviewer alone (#4282, ADR 0019): the cascade
counts the serious defects that a cleared case loses, the oracle bounds the saving, and the
golden set holds a fixed split."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.roadmap.decision_step import Cut
from devops_cli.roadmap.stage.stage_eval_cases import CASES_DIRECTORY, load_cases
from devops_cli.roadmap.stage.stage_screen_eval import (
    ScreenRow,
    cascade_score,
    fitted_cuts,
    jev_usd,
    oracle_skip,
    read_split,
    render_screen,
    rows_from_report,
    screen_json,
    two_way,
)
from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
CUT = {"a": Cut(continue_below=0.5, flag_at=0.9), "b": Cut(continue_below=0.5, flag_at=0.9)}


def _row(
    name: str, top: float, *, serious: int, labelled: int = 2, reviewed: bool = True
) -> ScreenRow:
    return ScreenRow(
        name=name,
        good=labelled == 0,
        labelled=labelled,
        labelled_serious=labelled,
        reviewed=reviewed,
        found=serious,
        serious_found=serious,
        probabilities={"a": top, "b": 0.1},
        input_tokens=1000,
    )


ROWS = [
    _row("good", 0.1, serious=0, labelled=0),
    _row("missed", 0.2, serious=3),
    _row("caught", 0.8, serious=2),
    _row("empty", 0.3, serious=0),
    _row("unreviewed", 0.1, serious=0, reviewed=False),
]


def test_a_cleared_case_loses_the_serious_defects_that_the_reviewer_found_in_it() -> None:
    score = cascade_score(ROWS, CUT)

    assert (score.reviewed, score.skipped, score.lost_cases, score.lost_serious) == (4, 3, 1, 3)
    assert (score.alone_serious, score.false_clears, score.labelled_bad) == (5, 2, 3)
    assert score.skip_rate == pytest.approx(0.75)
    assert score.serious_recall == pytest.approx(0.4)


def test_a_case_the_reviewer_did_not_cover_is_not_scored() -> None:
    assert cascade_score([ROWS[-1]], CUT).reviewed == 0


def test_the_oracle_counts_the_reviewed_cases_with_no_serious_defect_found() -> None:
    assert oracle_skip(ROWS) == 2


def test_the_price_of_jev_follows_the_input_tokens() -> None:
    assert jev_usd(ROWS) == pytest.approx(5000 * 0.042 / 1_000_000)


def test_the_bar_needs_no_loss_and_enough_skips_on_the_other_half() -> None:
    rows = [_row(f"n{i}", 0.1, serious=0, labelled=0) for i in range(6)]
    rows += [_row(f"p{i}", 0.9, serious=2) for i in range(6)]
    split = {"A": [r.name for r in rows[::2]], "B": [r.name for r in rows[1::2]]}

    reports = two_way(rows, split)

    assert {report.rule for report in reports} == {"per_question", "shared"}
    assert all(report.on_report.lost_serious == 0 for report in reports)
    assert all(report.bar_met for report in reports)


def test_the_report_renders_the_bar_the_oracle_and_the_cost() -> None:
    split = {"A": ["good", "missed"], "B": ["caught", "empty", "unreviewed"]}

    text = render_screen(ROWS, two_way(ROWS, split), reviewer_usd=0.2)

    assert "No screen can skip more than 2 of 4 reviews (50%)" in text
    assert "Bar of pilot 1 on the other half:" in text
    assert "0.2000 USD with the reviewer alone" in text


def test_the_json_report_keeps_each_row_so_a_fit_repeats_with_no_request(tmp_path: Path) -> None:
    split = {"A": ["good", "missed"], "B": ["caught", "empty", "unreviewed"]}
    path = tmp_path / "report.json"
    path.write_text(
        screen_json(ROWS, two_way(ROWS, split), taken="now", jev_model="typesafe/jev-1.14"),
        encoding="utf-8",
    )

    assert rows_from_report(path) == ROWS


def test_the_data_file_of_the_cuts_names_the_model_the_cases_and_the_numbers() -> None:
    split = {"A": ["good", "missed"], "B": ["caught", "empty", "unreviewed"]}

    data = json.loads(
        fitted_cuts(ROWS, two_way(ROWS, split), jev_model="typesafe/jev-1.14", day="2026-11-10")
    )

    assert (data["step"], data["model"], data["fitted"], data["cases"]) == (
        "stage.verify_screen",
        "typesafe/jev-1.14",
        "2026-11-10",
        4,
    )
    assert data["report"]["oracle_skip"] == 2
    assert set(data["report"]["other_half"]) == {
        "per_question_fitted_on_A",
        "per_question_fitted_on_B",
        "shared_fitted_on_A",
        "shared_fitted_on_B",
    }


def test_the_golden_set_holds_one_fixed_split_that_covers_each_case_once() -> None:
    names = [case.name for case in load_cases(ROOT / CASES_DIRECTORY)]

    split = read_split(ROOT / CASES_DIRECTORY)

    assert sorted(split["A"] + split["B"]) == sorted(names)
    assert not set(split["A"]) & set(split["B"])
    assert abs(len(split["A"]) - len(split["B"])) <= 3
