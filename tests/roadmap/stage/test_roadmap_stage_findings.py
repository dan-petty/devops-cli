"""The findings of the stage gates: the gate, the code and the path of each problem, the counts of
a return, and the seed fix rate of each code (#4846)."""

from __future__ import annotations

import dataclasses
import json
import string
from typing import Any

import pytest

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage_change import ProposalGate, joined_problems
from devops_cli.roadmap.stage.stage_findings import (
    UNCODED,
    FixClass,
    FixCount,
    ReturnCounts,
    StageFinding,
    finding_classes,
    fix_class,
    fix_counts,
    gate_findings,
    load_finding_classes,
    return_counts,
    stage_finding,
    wilson_lower,
)
from tests.support.paths import FIXTURES

GATE_PREFIX = "stage_problem_"
MISSING_TEST = MESSAGES.roadmap.stage_problem_missing_test_file.format(
    path="tests/test_old.py", hint=MESSAGES.roadmap.stage_path_no_same_name
)
CALLER = MESSAGES.roadmap.stage_problem_missing_caller.format(
    function="read_comments", path="src/devops_cli/sample.py"
)
TRACE = MESSAGES.roadmap.stage_problem_trace_path.format(path="docs/README.md")


def _sample(template: str) -> str:
    """`template` with each field filled with its own value."""
    return "".join(
        literal + (f"value-{index}" if field is not None else "")
        for index, (literal, field, _, _) in enumerate(string.Formatter().parse(template))
    )


def _gate_keys() -> list[str]:
    """The keys of the gate problems of `MESSAGES.roadmap`."""
    return [
        item.name
        for item in dataclasses.fields(MESSAGES.roadmap)
        if item.name.startswith(GATE_PREFIX)
        and isinstance(getattr(MESSAGES.roadmap, item.name), str)
    ]


def _plans() -> list[list[list[StageFinding]]]:
    """The findings of the replies of each saved plan of the fixture."""
    saved: dict[str, Any] = json.loads(
        (FIXTURES / "roadmap" / "stage_refused_findings.json").read_text(encoding="utf-8")
    )
    return [
        [[stage_finding(gate, text) for gate, text in reply] for reply in plan["replies"]]
        for plan in saved["plans"]
    ]


# ── The code of a problem ─────────────────────────────────────────────────────


@pytest.mark.parametrize("key", _gate_keys())
def test_each_gate_message_gives_its_own_key_as_its_code(key: str) -> None:
    """A gate message with no code, or with the code of another message, fails here."""
    finding = stage_finding("paths", _sample(getattr(MESSAGES.roadmap, key)))

    assert finding.code == key


def test_a_text_that_no_gate_message_makes_has_the_code_uncoded() -> None:
    assert stage_finding("paths", "The plan is wrong.").code == UNCODED


def test_a_message_with_a_hint_gives_the_code_and_the_path_of_its_template() -> None:
    finding = stage_finding("paths", MISSING_TEST)

    assert (finding.gate, finding.code, finding.path, finding.text) == (
        "paths",
        "stage_problem_missing_test_file",
        "tests/test_old.py",
        MISSING_TEST,
    )


def test_a_message_with_no_path_field_gives_no_path() -> None:
    text = MESSAGES.roadmap.stage_problem_no_quote

    assert stage_finding("content", text).path is None


def test_a_reply_refused_by_two_gates_gives_two_findings_in_the_order_of_the_gates() -> None:
    found = {ProposalGate.PATHS: [CALLER], ProposalGate.TRACE: [TRACE]}

    findings = gate_findings(found)

    assert [(f.gate, f.code, f.path) for f in findings] == [
        ("paths", "stage_problem_missing_caller", "src/devops_cli/sample.py"),
        ("trace", "stage_problem_trace_path", "docs/README.md"),
    ]


def test_the_prompt_text_of_the_findings_is_the_joined_text_of_the_gates() -> None:
    """The model gets the same problem text as before the findings: the problems of the gates in
    order, joined by one space."""
    found = {ProposalGate.PATHS: [MISSING_TEST, CALLER], ProposalGate.TRACE: [TRACE]}

    joined = " ".join(f.text for f in gate_findings(found))

    assert joined == " ".join(joined_problems(found))


# ── The counts of a return ────────────────────────────────────────────────────


def _finding(gate: str, text: str) -> StageFinding:
    return stage_finding(gate, text)


def test_a_return_counts_the_findings_gone_stuck_and_new() -> None:
    before = [_finding("paths", MISSING_TEST), _finding("paths", CALLER)]
    after = [_finding("paths", MISSING_TEST), _finding("trace", TRACE)]

    assert return_counts(before, after) == ReturnCounts(before=2, gone=1, stuck=1, new=1)


def test_a_finding_that_moves_to_another_group_number_is_stuck() -> None:
    first = MESSAGES.roadmap.stage_problem_missing_module_test.format(
        group=1, path="src/devops_cli/sample.py", test="tests/test_sample.py"
    )
    moved = first.replace("Group 1", "Group 2")

    assert return_counts([_finding("paths", first)], [_finding("paths", moved)]) == ReturnCounts(
        before=1, gone=0, stuck=1, new=0
    )


def test_the_same_text_under_another_gate_is_not_stuck() -> None:
    assert return_counts([_finding("paths", TRACE)], [_finding("trace", TRACE)]) == ReturnCounts(
        before=1, gone=1, stuck=0, new=1
    )


def test_a_pass_after_a_return_counts_each_finding_gone() -> None:
    assert return_counts([_finding("paths", CALLER)], []) == ReturnCounts(1, 1, 0, 0)


def test_the_fix_counts_of_a_plan_count_each_reply_that_has_a_next_one() -> None:
    replies = [
        [_finding("paths", MISSING_TEST), _finding("paths", CALLER)],
        [_finding("paths", MISSING_TEST)],
        [_finding("trace", TRACE)],
    ]

    assert fix_counts(replies) == {
        "stage_problem_missing_caller": FixCount(fixed=1, n=1),
        "stage_problem_missing_test_file": FixCount(fixed=1, n=2),
    }


# ── The fix class of a code ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("code", "count", "expected"),
    [
        ("stage_problem_missing_module_test", FixCount(0, 20), FixClass.MECHANICAL),
        ("stage_problem_path", FixCount(0, 4), FixClass.MODEL_FIXABLE),
        ("stage_problem_missing_test_file", FixCount(0, 17), FixClass.NEVER),
        ("stage_problem_missing_caller", FixCount(11, 28), FixClass.LOW_SHARE),
        ("stage_problem_citation_stale", FixCount(46, 46), FixClass.MODEL_FIXABLE),
    ],
)
def test_the_fix_class_of_a_code_follows_its_seed(
    code: str, count: FixCount, expected: FixClass
) -> None:
    assert fix_class(code, count, wilson_lower(count)) is expected


def test_the_wilson_lower_bound_of_three_fixes_in_three_is_under_one_half() -> None:
    assert (wilson_lower(FixCount(3, 3)), wilson_lower(FixCount(0, 17))) == (0.439, 0.0)


# ── The saved refused replies and the seed file ───────────────────────────────


def test_each_problem_of_the_saved_refused_replies_has_a_code() -> None:
    uncoded = [
        f.text[:80] for plan in _plans() for reply in plan for f in reply if f.code == UNCODED
    ]

    assert uncoded == []


def test_the_saved_refused_replies_give_the_seed_of_each_code_of_the_data_file() -> None:
    assert finding_classes(_plans()) == load_finding_classes()


def test_the_seed_of_the_saved_replies_holds_the_measured_rates() -> None:
    """The fix rates that the study of the stage drought measured on the same records."""
    codes = load_finding_classes().codes

    assert [
        (code, codes[code].fixed, codes[code].n, codes[code].fix_class)
        for code in (
            "stage_problem_missing_test_file",
            "stage_problem_missing_caller",
            "stage_problem_citation_stale",
        )
    ] == [
        ("stage_problem_missing_test_file", 0, 17, FixClass.NEVER),
        ("stage_problem_missing_caller", 11, 28, FixClass.LOW_SHARE),
        ("stage_problem_citation_stale", 46, 46, FixClass.MODEL_FIXABLE),
    ]
