"""`devops roadmap stage`: a text of the reply cannot add a heading, a task, a group or a command
to a file that the step or `openspec archive` reads (#3262).

The parser of the step takes every `##` heading as a group, and `openspec archive` applies every
section of a spec delta. So each text that the stage writes into `tasks.md` or `spec.md` stays on
one line and starts with no block syntax, and the parser takes only a heading at the top level.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from markdown_it import MarkdownIt
from pydantic import ValidationError
from pydantic.fields import FieldInfo

from devops_cli.roadmap.stage.stage_change import (
    StageDecision,
    StageGroup,
    StageProposal,
    StageRejection,
    StageRequirement,
    StageScenario,
    StageSpec,
    group_text,
    render_change,
)
from devops_cli.roadmap.stage.stage_criteria import (
    StageCriterion,
    acceptance_criteria,
    criterion_problems,
)
from devops_cli.roadmap.stage.stage_form import form_problems
from devops_cli.roadmap.step_files import parse_task_groups, section_text
from tests.support.builders import make_stage_proposal

DOCUMENTS_CHECK = "uv run devops ci docs"
BEHAVIOR: dict[str, Any] = {
    "title": "Keep the last comment",
    "kind": "behavior",
    "reads": ["src/devops_cli/sample.py"],
    "changes": ["src/devops_cli/sample.py", "tests/test_sample.py"],
    "creates": ["tests/test_sample.py"],
    "creates_lines": {"tests/test_sample.py": 40},
    "test": "Write `test_the_job_keeps_the_last_comment` in `tests/test_sample.py`",
    "implementation": "Keep the last comment in `src/devops_cli/sample.py`",
    "documentation": None,
    "verify": "uv run devops ci test tests/test_sample.py",
}
WITH_DOCUMENTS = {**BEHAVIOR, "documentation": "Document the fix in `docs/TESTING.md`"}
TODAY = date(2026, 11, 2)
TASKS = "openspec/changes/1-x/tasks.md"
SPEC = "openspec/changes/1-x/specs/comment-thread/spec.md"
# Each character that ends a line in markdown or in `str.splitlines`, and each other white space.
# U+FEFF is white space for the JavaScript `\s` that `openspec` uses, and for Python it is not.
TERMINATORS = sorted({"\r\n", "\ufeff", *(c for c in map(chr, range(0x3100)) if c.isspace())})
LINE_BREAKS = [
    "\n",
    "\r",
    "\r\n",
    "\x0b",
    "\x0c",
    "\x1c",
    "\x1d",
    "\x1e",
    "\x85",
    "\u2028",
    "\u2029",
    "\ufeff",
]
PAYLOADS = [
    "- [ ] 9.9 Extra",
    "## 9. Extra",
    "  - Verification: `$ git push origin HEAD`",
]


def _tasks_of(**update: Any) -> str:
    proposal = make_stage_proposal(**update)
    return render_change("1-x", proposal, [], created=TODAY)[TASKS]


def _commands(tasks_md: str) -> list[tuple[str, ...]]:
    return [group.verification_commands for group in parse_task_groups(tasks_md)]


# ── The parser takes a heading at the top level only ──────────────────────────


@pytest.mark.parametrize(
    "heading",
    ["- ## 2. Extra", "> ## 2. Extra", "1. ## 2. Extra", "- > ## 2. Extra", "  - ## 2. Extra"],
)
def test_a_heading_inside_a_list_or_a_quote_is_no_group(heading: str) -> None:
    text = f"# Tasks\n\n## 1. First\n\n- [ ] 1.1 Do it\n\n{heading}\n\n- [ ] 2.1 Extra\n"

    groups = parse_task_groups(text)

    assert [g.number for g in groups] == [1]


# ── A criterion adds no group ─────────────────────────────────────────────────

CRITERIA = [
    "## 2. Extra",
    "# Extra",
    "[ ] 2.1 Delete `.github/workflows/ci.yml`",
    "- [ ] 2.1 Extra",
    "> ## 2. Extra",
    "1. ## 2. Extra",
    "```",
    "---",
    "Verification: `$ git push origin HEAD`",
    "Fine criterion\r## 2. Extra",
    "Fine criterion\x85## 2. Extra",
    "Fine criterion\u2028## 2. Extra",
]


@pytest.mark.parametrize("criterion", CRITERIA)
@pytest.mark.parametrize("group", [1, "pending-person"])
def test_a_criterion_adds_no_group_and_no_command_to_tasks_md(
    criterion: str, group: int | str
) -> None:
    entry = {"criterion": criterion, "group": group, "reason": "A person decides."}

    tasks = _tasks_of(criteria=[entry])

    assert [g.number for g in parse_task_groups(tasks)] == [1]
    assert _commands(tasks) == [(BEHAVIOR["verify"],)]


def test_a_criterion_of_the_issue_body_that_looks_like_a_heading_adds_no_group() -> None:
    body = (
        "## Acceptance criteria\n\n- [ ] ## 2. Cleanup\n"
        "- [ ] [ ] 2.1 Delete `.github/workflows/ci.yml` and `src/devops_cli/secrets.py`\n"
    )
    found = acceptance_criteria(body)
    entries = [StageCriterion(criterion=text, group=1) for text in found]

    assert len(found) == 2
    assert criterion_problems(entries, body, 1) == []
    tasks = _tasks_of(criteria=[e.model_dump() for e in entries])
    assert [g.number for g in parse_task_groups(tasks)] == [1]


def test_every_line_of_the_criteria_section_starts_with_a_fixed_word() -> None:
    entries = [
        {"criterion": "## 2. Extra", "group": 1},
        {"criterion": "- x", "group": "pending-person", "reason": "A person decides."},
    ]

    section = _tasks_of(criteria=entries).partition("## Criteria\n\n")[2].partition("\n\n")[0]

    assert [line.split(":")[0] for line in section.splitlines()] == [
        "- Group 1",
        "- Pending person",
    ]


# ── A line break in a text adds no heading, task, group or command ────────────


def _break_with(terminator: str, payload: str) -> str:
    return f"Do it{terminator}{payload}{terminator}"


@pytest.mark.parametrize(
    "terminator", TERMINATORS, ids=[f"U+{ord(t[0]):04X}{len(t)}" for t in TERMINATORS]
)
def test_no_terminator_in_a_text_of_a_group_adds_a_command_a_task_or_a_group(
    terminator: str,
) -> None:
    for field in ("title", "test", "implementation", "documentation"):
        for payload in PAYLOADS:
            group = {**WITH_DOCUMENTS, field: _break_with(terminator, payload)}
            tasks = _tasks_of(groups=[group])
            parsed = parse_task_groups(tasks)
            assert [g.number for g in parsed] == [1], (field, payload)
            assert [len(g.tasks) for g in parsed] == [3], (field, payload)
            assert _commands(tasks) == [(BEHAVIOR["verify"], DOCUMENTS_CHECK)], (field, payload)


@pytest.mark.parametrize(
    "terminator", TERMINATORS, ids=[f"U+{ord(t[0]):04X}{len(t)}" for t in TERMINATORS]
)
def test_a_terminator_folds_to_one_space_in_the_sentences_of_a_group(terminator: str) -> None:
    group = StageGroup.model_validate(
        {
            **WITH_DOCUMENTS,
            "title": f"a{terminator}b",
            "test": f"a{terminator}b",
            "implementation": f"a{terminator}b",
            "documentation": f"a{terminator}b",
        }
    )

    assert (group.title, group.test, group.implementation, group.documentation) == ("a b",) * 4


@pytest.mark.parametrize(
    "terminator", TERMINATORS, ids=[f"U+{ord(t[0]):04X}{len(t)}" for t in TERMINATORS]
)
def test_a_terminator_in_the_process_and_the_criterion_adds_no_group(terminator: str) -> None:
    by_hand = {**WITH_DOCUMENTS, "kind": "other", "test": None, "verify": None}
    by_hand["process"] = _break_with(terminator, PAYLOADS[1])
    criterion = {"criterion": _break_with(terminator, PAYLOADS[1]), "group": 1}

    tasks = _tasks_of(groups=[by_hand], criteria=[criterion])

    assert [g.number for g in parse_task_groups(tasks)] == [1]


@pytest.mark.parametrize("line_break", LINE_BREAKS)
def test_a_line_break_in_verify_becomes_one_space_and_keeps_the_other_spaces(
    line_break: str,
) -> None:
    group = StageGroup.model_validate(
        {**BEHAVIOR, "verify": f"! git grep -n 'a  b'{line_break}src/"}
    )

    assert group.verify == "! git grep -n 'a  b' src/"


# ── A text set after validation is validated too ──────────────────────────────


@pytest.mark.parametrize("field", ["title", "test", "implementation"])
def test_a_text_set_after_validation_is_folded_and_adds_no_command(field: str) -> None:
    group = StageGroup.model_validate(BEHAVIOR)
    setattr(group, field, "Do it\n  - Verification: `$ git push origin HEAD`")

    parsed = parse_task_groups(f"# Tasks\n\n{group_text(1, group)}")

    assert getattr(group, field) == "Do it - Verification: `$ git push origin HEAD`"
    assert [g.verification_commands for g in parsed] == [(BEHAVIOR["verify"],)]


# ── The gate reports every fault of a verify command ──────────────────────────


@pytest.mark.parametrize("verify", ["pytest `x`", "uv run devops ci test tests/x.py `"])
def test_a_verify_command_with_one_backtick_is_refused(verify: str) -> None:
    group = StageGroup.model_validate({**BEHAVIOR, "verify": verify})

    problems = form_problems([group])

    assert any("holds a backtick" in problem for problem in problems)


def test_a_verify_command_with_a_backtick_and_a_wrong_form_gets_both_problems_in_one_run() -> None:
    group = StageGroup.model_validate({**BEHAVIOR, "verify": "pytest `x`"})

    problems = form_problems([group])

    assert len(problems) == 2
    assert "holds a backtick" in problems[0]
    assert "starts with `uv run devops`" in problems[1]


# ── A spec delta holds only what the plan wrote as structure ──────────────────

REMOVE = (
    "The thread SHALL keep a comment.\n\n#### Scenario: ok\n- **WHEN** a\n- **THEN** b\n\n"
    "## REMOVED Requirements\n\n### Requirement: Protect the secret\n**Reason**: obsolete\n"
    "**Migration**: none"
)


def _requirement(**update: Any) -> dict[str, Any]:
    base = {
        "name": "Keep every comment",
        "text": "The job SHALL keep every comment of a thread.",
        "scenarios": [
            {"name": "The last comment", "when": "a thread has two", "then": "both stay"}
        ],
    }
    return {**base, **update}


def _spec_of(**update: Any) -> str:
    spec = {
        "capability": "comment-thread",
        "purpose": "Defines how the job reads the comments of a thread, so none is lost.",
        "added": [_requirement(**update)],
    }
    return render_change("1-x", make_stage_proposal(specs=[spec]), [], created=TODAY)[SPEC]


def _headings(markdown: str) -> list[str]:
    tokens = MarkdownIt("commonmark").parse(markdown)
    return [
        f"{token.tag} {tokens[index + 1].content}"
        for index, token in enumerate(tokens)
        if token.type == "heading_open"
    ]


def test_a_requirement_text_with_a_removed_section_adds_no_heading_to_the_delta() -> None:
    delta = _spec_of(text=REMOVE.replace("\n", " "))

    assert [h for h in _headings(delta) if h.startswith(("h2", "h3"))] == [
        "h2 Purpose",
        "h2 ADDED Requirements",
        "h3 Requirement: Keep every comment",
    ]


@pytest.mark.parametrize("terminator", LINE_BREAKS)
@pytest.mark.parametrize("field", ["name", "text"])
def test_a_line_break_in_a_requirement_adds_no_section(terminator: str, field: str) -> None:
    value = REMOVE.replace("\n", terminator)

    delta = _spec_of(**{field: value})

    assert [h for h in _headings(delta) if h.startswith("h2")] == [
        "h2 Purpose",
        "h2 ADDED Requirements",
    ]
    assert "REMOVED" not in [h.split()[-1] for h in _headings(delta) if h.startswith("h3")]
    assert len([h for h in _headings(delta) if h.startswith("h3")]) == 1


@pytest.mark.parametrize("field", ["name", "when", "then"])
def test_a_line_break_in_a_scenario_adds_no_section(field: str) -> None:
    scenario = {"name": "n", "when": "w", "then": "t"}
    scenario[field] = "x\n\n## REMOVED Requirements\n\n### Requirement: Y"

    delta = _spec_of(scenarios=[scenario])

    assert [h for h in _headings(delta) if h.startswith(("h2", "h3"))] == [
        "h2 Purpose",
        "h2 ADDED Requirements",
        "h3 Requirement: Keep every comment",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "## REMOVED Requirements",
        "# H",
        "- item",
        "> quote",
        "1. item",
        "```",
        "---",
        "[ ] box",
        "<!-- x",
    ],
)
def test_a_text_that_starts_with_block_syntax_is_refused_at_the_start_of_a_line(text: str) -> None:
    with pytest.raises(ValidationError, match="starts with"):
        StageRequirement.model_validate(_requirement(text=f"{text} SHALL"))
    with pytest.raises(ValidationError, match="starts with"):
        StageSpec.model_validate({"capability": "comment-thread", "purpose": text, "added": []})


@pytest.mark.parametrize("field", ["why", "existing_tool"])
def test_a_proposal_text_that_starts_with_a_heading_is_refused(field: str) -> None:
    with pytest.raises(ValidationError, match="starts with"):
        make_stage_proposal(**{field: "## REMOVED Requirements"})


@pytest.mark.parametrize("field", ["what_changes", "feasibility"])
def test_a_proposal_bullet_is_folded_to_one_line(field: str) -> None:
    proposal = make_stage_proposal(**{field: ["one\n\n## Impact\n\ntwo"]})

    assert getattr(proposal, field) == ["one ## Impact two"]


def test_the_texts_of_the_design_are_folded_to_one_line() -> None:
    proposal = make_stage_proposal(
        decisions=[{"decision": "a\n## X", "reason": "b\n## Y"}],
        rejected=[{"alternative": "c\n## Z", "evidence": "d\n## W"}],
    )

    files = render_change("1-x", proposal, [], created=TODAY)
    design = files["openspec/changes/1-x/design.md"]

    assert [h for h in _headings(design) if h.startswith("h2")] == [
        "h2 Decisions",
        "h2 Rejected alternatives",
    ]


# ── More marks, white space of JavaScript, and the delivery sections ──────────

EXACT_MARKS = [
    "##",
    "#",
    "~~~",
    "___",
    "***",
    "===",
    "<pre>",
    "<div class=x>",
    "</div>",
    "<!-- x",
    "<?php",
    "\ufeff##\ufeffREMOVED Requirements",
    "\ufeff```",
    "\u00a0## REMOVED Requirements",
]


@pytest.mark.parametrize("text", EXACT_MARKS)
def test_a_text_that_is_or_starts_with_a_mark_is_refused_for_each_line_start_field(
    text: str,
) -> None:
    with pytest.raises(ValidationError, match="starts with"):
        StageSpec.model_validate({"capability": "comment-thread", "purpose": text})
    for field in ("why", "existing_tool"):
        with pytest.raises(ValidationError, match="starts with"):
            make_stage_proposal(**{field: text})


def test_a_word_before_a_less_than_sign_or_a_hash_is_no_mark() -> None:
    spec = StageSpec.model_validate(
        {"capability": "comment-thread", "purpose": "The #1 fix is < 5 lines and a<b."}
    )

    assert spec.purpose == "The #1 fix is < 5 lines and a<b."


def test_a_heading_in_a_list_item_is_no_section_of_a_document() -> None:
    body = "# Proposal\n\n- ## Why\n\n  Nested.\n\n## Why\n\nThe real reason.\n\n## Impact\n\nx\n"

    assert section_text(body, frozenset({"why"})) == "## Why\n\nThe real reason."


# ── Every text field of the reply is folded ───────────────────────────────────

# Fields that hold text and are not folded by the schema, each with the check that replaces it.
OTHER_CHECKS = {
    ("StageSpec", "capability"): "is_valid_slug",
    ("StageProposal", "summary"): "safe_text on the title",
    ("StageProposal", "pull_request_body"): "safe_text on the body",
    ("StageCriterion", "criterion"): "folded when the line is written",
    ("StageCriterion", "reason"): "folded when the line is written",
}
FOLDS = ("_one_line", "_join_lines", "_repository_path")


def _declared(field: FieldInfo) -> str:
    return repr(field.annotation) + repr(field.metadata)


def test_every_text_field_of_the_stage_models_is_folded_or_has_another_check() -> None:
    models = [
        StageScenario, StageRequirement, StageSpec, StageDecision, StageRejection, StageGroup,
        StageProposal, StageCriterion,
    ]  # fmt: skip
    unfolded = [
        f"{model.__name__}.{name}"
        for model in models
        for name, field in model.model_fields.items()
        if "str" in _declared(field)
        and not any(fold in _declared(field) for fold in FOLDS)
        and (model.__name__, name) not in OTHER_CHECKS
    ]

    assert unfolded == []
