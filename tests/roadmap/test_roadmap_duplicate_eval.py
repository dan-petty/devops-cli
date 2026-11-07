"""`devops roadmap eval intake` scores intake's duplicate judgement against the evaluation set
(#1989): each case runs through intake with the model fake, and pydantic-evals scores it."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.exceptions.git import GitHubFileNotFoundError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.duplicate_eval import SeededRoadmap, Verdict, load_cases
from devops_cli.roadmap.stores.store import ItemField, field_label
from tests.support.fakes.model import ModelFake

CASES = load_cases()
# A reply's type, priority, Value and Effort, as the intake tests give them.
PROPOSAL: dict[str, Any] = {
    "type": "type/feature",
    "type_reason": "it adds a capability.",
    "priority": "P2-Medium",
    "priority_reason": "useful, not urgent.",
    "value": "Medium",
    "value_reason": "it helps maintainers.",
    "effort": "Low",
    "effort_reason": "one module.",
}
# The case that the fake folds although a person judged it a new item.
FOLDED = next(case for case in CASES if not case.duplicate)
TEXTS = MESSAGES.roadmap


def _reply(*, original: bool, shared_change: str = "the same change") -> str:
    """A reply that names the case's item, its roadmap's only issue #1, as the original, or one
    that names no original."""
    if not original:
        return json.dumps(PROPOSAL)
    judgement = {"duplicate_of": 1, "duplicate_reason": "both ask for it."}
    return json.dumps(
        PROPOSAL | judgement | ({"shared_change": shared_change} if shared_change else {})
    )


def _answer(
    model_fake: ModelFake, *, folded: str | None = None, failing: str | None = None
) -> None:
    """Answer each case's call by its candidate's title: an original for each duplicate and for
    `folded`, none for the others, and a failed call for `failing`."""
    for case in CASES:
        pattern = _in_request(case.candidate.title)
        if case.name == failing:
            model_fake.route_error(pattern, ConnectionError("the gateway did not answer"))
        else:
            model_fake.route(pattern, _reply(original=case.duplicate or case.name == folded))


def _in_request(title: str) -> Callable[[str], bool]:
    """Whether a request is the one for the candidate with `title`. An item's title can be another
    case's candidate title, so the match reads the request's own title, not the shortlist's."""
    return lambda prompt: json.loads(prompt).get("title") == title


def _lines(result: Any) -> list[str]:
    return result.output.splitlines()


def test_the_evaluation_set_holds_named_cases_of_both_verdicts() -> None:
    names = [case.name for case in CASES]
    assert (
        len(CASES),
        len(set(names)),
        sum(case.duplicate for case in CASES),
        {case.expected for case in CASES},
    ) == (16, 16, 3, {Verdict.DUPLICATE, Verdict.NEW_ITEM})


def test_a_run_that_folds_one_related_item_reports_one_false_duplicate(
    cli: Callable[..., Any], model_fake: ModelFake, keyring_store: Any
) -> None:
    _answer(model_fake, folded=FOLDED.name)
    result = cli("roadmap", "eval", "intake")
    lines = _lines(result)
    agree = TEXTS.intake_eval_agreed.format(agreed=15, cases=16)
    score = TEXTS.intake_eval_score.format(
        true=3, said=4, precision="75%", expected=3, recall="100%", false=1
    )
    assert (
        result.exit_code,
        agree in lines,
        score in lines,
        sum(line.startswith(f"- DISAGREE: {FOLDED.name}:") for line in lines),
        sum(line.startswith("- agree: ") for line in lines),
        len(model_fake.calls),
    ) == (0, True, True, 1, 15, 16)


def test_a_run_that_agrees_with_every_case_reports_no_false_duplicate(
    cli: Callable[..., Any], model_fake: ModelFake, keyring_store: Any
) -> None:
    _answer(model_fake)
    result = cli("roadmap", "eval", "intake")
    score = TEXTS.intake_eval_score.format(
        true=3, said=3, precision="100%", expected=3, recall="100%", false=0
    )
    assert (
        result.exit_code,
        TEXTS.intake_eval_agreed.format(agreed=16, cases=16) in _lines(result),
        score in _lines(result),
    ) == (0, True, True)


def test_a_reply_that_names_the_item_with_no_shared_change_is_a_new_item(
    cli: Callable[..., Any], model_fake: ModelFake, keyring_store: Any
) -> None:
    """Intake's own reading of the reply decides the verdict: an original named with no shared
    change is a related item, so the case agrees with the person's `new item`."""
    for case in CASES:
        reply = _reply(original=True, shared_change="" if not case.duplicate else "one change")
        model_fake.route(_in_request(case.candidate.title), reply)
    result = cli("roadmap", "eval", "intake")
    assert (
        result.exit_code,
        TEXTS.intake_eval_agreed.format(agreed=16, cases=16) in _lines(result),
    ) == (
        0,
        True,
    )


def test_a_case_whose_call_fails_is_shown_with_its_error_and_the_run_exits_1(
    cli: Callable[..., Any], model_fake: ModelFake, keyring_store: Any
) -> None:
    failing = CASES[0].name
    _answer(model_fake, failing=failing)
    result = cli("roadmap", "eval", "intake")
    lines = _lines(result)
    assert (
        result.exit_code,
        sum(line.startswith(f"- ERROR: {failing}: ") for line in lines),
        TEXTS.intake_eval_agreed.format(agreed=15, cases=16) in lines,
        len(model_fake.calls),
    ) == (1, 1, True, 16)


def test_a_checkout_with_no_labels_file_stops_before_any_model_call(
    cli: Callable[..., Any], model_fake: ModelFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    _answer(model_fake)
    result = cli("roadmap", "eval", "intake")
    assert (result.exit_code, ".github/labels.yml" in result.output, model_fake.calls) == (
        1,
        True,
        [],
    )


def test_the_dry_run_lists_each_case_and_its_call_and_makes_none(
    cli: Callable[..., Any], model_fake: ModelFake, keyring_store: Any
) -> None:
    result = cli("roadmap", "eval", "intake", "--dry-run")
    lines = _lines(result)
    assert (
        result.exit_code,
        [line for line in lines if line.startswith("- ")] == [f"- {case.name}" for case in CASES],
        TEXTS.intake_eval_dry_run_calls.format(calls=16) in lines,
        model_fake.calls,
    ) == (0, True, True, [])


def test_a_seeded_roadmap_holds_the_case_item_and_the_labels_file_and_nothing_else() -> None:
    case = CASES[0]
    roadmap = SeededRoadmap(item=case.item, labels="- name: type/feature\n")
    issues = roadmap.issues()
    assert (
        [(issue.number, issue.title, issue.body) for issue in issues],
        field_label(ItemField.PRIORITY, "P3-Low") in issues[0].labels,
        roadmap.repository_file(CONST_ROADMAP_LABELS_PATH),
        roadmap.closures(1),
        roadmap.comments_on(1),
    ) == (
        [(1, case.item.title, case.item.body)],
        True,
        "- name: type/feature\n",
        [],
        [],
    )


_WRITE_VERBS = ("create_", "set_", "label_", "unlabel_", "write_", "close", "add_", "edit_")


def test_a_seeded_roadmap_has_no_other_file_and_offers_no_write() -> None:
    roadmap = SeededRoadmap(item=CASES[0].item, labels="")
    writes = [name for name in dir(roadmap) if name.startswith(_WRITE_VERBS) or name == "comment"]
    with pytest.raises(GitHubFileNotFoundError, match="pyproject\\.toml"):
        roadmap.repository_file("pyproject.toml")
    assert writes == []
