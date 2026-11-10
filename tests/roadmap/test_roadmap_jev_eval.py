"""`devops roadmap eval jev` compares Jev with the triage model (#4298): the false duplicates
of each model come first, then the agreement of each label field with the labels of closed
issues."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.config.constants import (
    CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD,
    CONST_ROADMAP_MODEL_PRIORITIES,
    CONST_ROADMAP_SIZE_OPTIONS,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.commit_title import commit_summary
from devops_cli.roadmap.duplicate_eval import evaluate_duplicates, load_cases
from devops_cli.roadmap.intake.intake_jev import JevIntakeModel
from devops_cli.roadmap.jev_eval import (
    LabelScore,
    ModelScores,
    evaluate_labels,
    jev_has_no_more_false_duplicates,
    load_label_cases,
    planned_calls,
    render_comparison,
)
from tests.support.roadmap_intake import LABELS_YML, FakeModel

if TYPE_CHECKING:
    from tests.support.fakes.jev import JevFake

LABEL_CASES = load_label_cases()
DUPLICATE_CASES = load_cases()
LEVEL = {"Low": 0, "Medium": 1, "High": 2}
TEXTS = MESSAGES.roadmap


def _jev(jev: JevFake) -> JevIntakeModel:
    return JevIntakeModel(FakeModel(), jev.model, fall_back=False)


def test_the_label_set_holds_named_closed_issues_with_values_from_the_lists() -> None:
    declared = LABELS_YML
    names = [case.name for case in LABEL_CASES]
    assert len(set(names)) == len(names) >= 20
    for case in LABEL_CASES:
        expected = case.expected
        assert f'name: "{expected.type}"' in declared
        assert expected.priority in CONST_ROADMAP_MODEL_PRIORITIES
        assert {expected.value, expected.effort} <= set(CONST_ROADMAP_SIZE_OPTIONS)


def test_a_model_that_answers_as_the_person_did_agrees_on_every_field(jev: JevFake) -> None:
    case = LABEL_CASES[0]
    expected = case.expected
    jev.picks = {
        "type": expected.type,
        "priority": expected.priority,
        "value": LEVEL[expected.value],
        "effort": LEVEL[expected.effort],
    }

    score = evaluate_labels([case], _jev(jev), LABELS_YML)

    assert score == LabelScore(
        cases=1, agreed={"type": 1, "priority": 1, "value": 1, "effort": 1}, failed=()
    )


def test_the_title_is_sent_without_its_commit_prefix_so_the_model_gives_the_type(
    jev: JevFake,
) -> None:
    evaluate_labels(LABEL_CASES[:1], _jev(jev), LABELS_YML)

    assert jev.asked == [["type", "priority", "value", "effort"]]
    assert jev.requests[0]["state"]["title"] == commit_summary(LABEL_CASES[0].candidate.title)


def test_a_case_that_jev_cannot_decide_is_listed_and_agrees_on_no_field(jev: JevFake) -> None:
    jev.fail(503)

    score = evaluate_labels(LABEL_CASES[:2], _jev(jev), LABELS_YML)

    assert score == LabelScore(
        cases=2,
        agreed={"type": 0, "priority": 0, "value": 0, "effort": 0},
        failed=(LABEL_CASES[0].name, LABEL_CASES[1].name),
    )


def test_a_jev_that_flags_every_neighbour_has_a_false_duplicate_for_each_new_item(
    jev: JevFake,
) -> None:
    jev.picks = {"duplicate_of_1": CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD}

    score = evaluate_duplicates(DUPLICATE_CASES, _jev(jev), LABELS_YML)

    new_items = sum(not case.duplicate for case in DUPLICATE_CASES)
    assert (score.false_duplicates, score.true_duplicates, score.missed_duplicates) == (
        new_items,
        3,
        0,
    )


def test_a_jev_that_flags_nothing_has_no_false_duplicate_and_misses_every_duplicate(
    jev: JevFake,
) -> None:
    score = evaluate_duplicates(DUPLICATE_CASES, _jev(jev), LABELS_YML)

    assert (score.false_duplicates, score.true_duplicates, score.missed_duplicates) == (0, 0, 3)


def _scores(triage_false: int, jev_false: int, jev: JevFake) -> list[ModelScores]:
    flagged = {"duplicate_of_1": CONST_ROADMAP_JEV_DUPLICATE_THRESHOLD}
    jev.picks = flagged if jev_false else {}
    labels = LabelScore(cases=1, agreed={"type": 1, "priority": 0, "value": 1, "effort": 0})
    jev_dup = evaluate_duplicates(DUPLICATE_CASES, _jev(jev), LABELS_YML)
    triage_dup = evaluate_duplicates(DUPLICATE_CASES, _triage(triage_false), LABELS_YML)
    return [ModelScores("triage", triage_dup, labels), ModelScores("jev", jev_dup, labels)]


def _triage(false_duplicates: int) -> FakeModel:
    """An triage model that folds `false_duplicates` of the cases that are new items."""
    new_items = [case for case in DUPLICATE_CASES if not case.duplicate][:false_duplicates]
    duplicates = {case.candidate.title: case.item.title for case in new_items}
    duplicates |= {
        case.candidate.title: case.item.title for case in DUPLICATE_CASES if case.duplicate
    }
    return FakeModel(duplicates=duplicates)


def test_the_report_puts_the_false_duplicates_first_and_gives_the_verdict(jev: JevFake) -> None:
    scores = _scores(triage_false=0, jev_false=0, jev=jev)

    report = render_comparison(scores, duplicate_cases=16, label_cases=25, spend="Spent.")
    lines = report.splitlines()

    assert lines[0] == TEXTS.jev_compare_title.format(duplicates=16, labels=25)
    assert lines[3] == TEXTS.jev_compare_duplicates_title
    assert lines[4].startswith("- triage: 0 false duplicate(s)")
    assert TEXTS.jev_compare_verdict_ok.format(jev=0, triage=0) in lines
    assert jev_has_no_more_false_duplicates(scores)


def test_a_jev_with_more_false_duplicates_than_the_triage_model_keeps_the_setting_off(
    jev: JevFake,
) -> None:
    scores = _scores(triage_false=0, jev_false=1, jev=jev)

    report = render_comparison(scores, duplicate_cases=16, label_cases=25, spend="Spent.")

    assert not jev_has_no_more_false_duplicates(scores)
    assert TEXTS.jev_compare_verdict_worse.format(jev=13, triage=0) in report.splitlines()


def test_a_run_makes_two_calls_for_each_case() -> None:
    assert planned_calls(16, 25) == 82


def test_a_jev_that_left_a_duplicate_case_to_the_fallback_makes_an_incomplete_comparison(
    jev: JevFake,
) -> None:
    jev.fail(503)
    jev_dup = evaluate_duplicates(DUPLICATE_CASES, _jev(jev), LABELS_YML)
    labels = LabelScore(cases=1, agreed={"type": 1, "priority": 1, "value": 1, "effort": 1})
    triage_dup = evaluate_duplicates(DUPLICATE_CASES, _triage(0), LABELS_YML)
    scores = [ModelScores("triage", triage_dup, labels), ModelScores("jev", jev_dup, labels)]

    report = render_comparison(scores, duplicate_cases=16, label_cases=1, spend="Spent.")

    assert not jev_has_no_more_false_duplicates(scores)
    assert TEXTS.jev_compare_verdict_incomplete.format(left=16) in report.splitlines()


def test_a_least_confidence_of_zero_takes_every_answer_of_jev(jev: JevFake) -> None:
    jev.confidence = 0.4
    model = JevIntakeModel(FakeModel(), jev.model, fall_back=False, min_confidence=0.0)

    score = evaluate_labels(LABEL_CASES[:2], model, LABELS_YML)

    assert score.failed == ()
