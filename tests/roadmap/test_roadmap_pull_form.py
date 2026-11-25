"""The form of the title and the body of a pull request (#3198).

`roadmap/pull_form.py` holds the rules and cuts no text. `devops pr describe` builds with them
(`tests/commands/test_pr_describe.py`), and `devops pr create` checks with them
(`tests/commands/test_pr_form_check.py`).
"""

from __future__ import annotations

import re
from typing import Literal

import pytest
from pydantic import BaseModel
from pydantic import ValidationError as ModelValidationError

from devops_cli.exceptions import ValidationError
from devops_cli.github.client import PullRequestFile
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import grounding, plan_check, pull_form
from devops_cli.roadmap.pull_form import (
    BODY_MAX_CHARS,
    PLACEHOLDER_ERROR_TYPE,
    SUMMARY_MAX_CHARS,
    ReplyText,
    body_problems,
    build_body,
    build_plan_body,
    build_title,
    is_placeholder,
    plan_body_problems,
    plan_body_room,
    summary_length,
    title_problems,
)

DECLARED = ("type/bug", "type/feature", "scope/pr", "scope/roadmap")
CHANGE = "openspec/changes/archive/2026-11-02-3198-pull-request-form-check"
WHY = "A title or a body that breaks the form of the project reads as broken after the merge."
GOOD_BODY = f"{WHY}\n\nCloses #3198\n\nChange: `{CHANGE}/`"
ATTRIBUTION = (
    "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>",
    "Claude-Session: https://claude.ai/code/session_example",
)


# ── The title ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "title",
    [
        "feat(pr): build and check the title of a pull request",
        "fix(roadmap): keep a label",
        "docs: explain the form",
        f"feat(pr): {'a' * SUMMARY_MAX_CHARS}",
        "chore(main): release 0.44.0",
    ],
)
def test_a_title_in_the_form_has_no_problem(title: str) -> None:
    assert title_problems(title, DECLARED) == []


def test_the_summary_limit_counts_utf16_units_like_the_title_check_of_the_workflow() -> None:
    """`^.{1,60}$` in JavaScript counts UTF-16 units: an emoji is two, so 31 emoji are 62 units
    and the check `Semantic PR title` refuses a title that has only 31 code points (#3249)."""
    fits = f"feat(pr): {chr(0x1F600) * (SUMMARY_MAX_CHARS // 2)}"
    long = f"feat(pr): {chr(0x20000) * (SUMMARY_MAX_CHARS // 2 + 1)}"

    assert title_problems(fits, DECLARED) == []
    (problem,) = title_problems(long, DECLARED)
    assert f"The summary has {SUMMARY_MAX_CHARS + 2} characters" in problem
    assert "an emoji counts as two" in problem


def test_a_lone_surrogate_counts_as_one_unit_and_the_form_check_does_not_crash() -> None:
    """A byte that is no UTF-8 reaches argv as a lone surrogate, and JavaScript counts it as one
    unit. `devops pr create` must print the form report for it, not a traceback (#3249)."""
    assert (summary_length("a\udcff"), summary_length("\ud83d")) == (2, 1)
    assert title_problems("feat(pr): bad \udcff byte", DECLARED) == []


@pytest.mark.parametrize(
    ("title", "fragment"),
    [
        ("A plain title", "is not in the form"),
        ("feat(pr) build it", "is not in the form"),
        ("Feat(pr): build it", "is not in the form"),
        ("feat(): build it", "is not in the form"),
        ("feat(pr): build it\nand more", "more than one line"),
        ("feat(pr): build it\rand more", "more than one line"),
        ("feat(pr): build it\u2028and more", "more than one line"),
        ("feat(pr): build it\u2029and more", "more than one line"),
        ("wip(pr): build it", "not a type of the project"),
        ("feat(pr)!: build it", "Before 1.0.0"),
        ("feat(zzz-unknown): build it", "`scope/zzz-unknown`"),
        (f"feat(pr): {'a' * (SUMMARY_MAX_CHARS + 1)}", f"The limit is {SUMMARY_MAX_CHARS}"),
        ("feat(pr): build the whole thing and...", "ends with `...`"),
        ("feat(pr): build the whole thing and…", "ends with `...`"),
        ("feat(pr): x", "is a placeholder"),
        ("fix: Placeholder.", "is a placeholder"),
        ("fix: ", "is not in the form"),
        ("fix:   ", "is not in the form"),
    ],
)
def test_a_title_that_breaks_the_form_names_the_problem(title: str, fragment: str) -> None:
    problems = title_problems(title, DECLARED)
    assert len(problems) == 1
    assert fragment in problems[0]


def test_a_title_with_two_faults_names_both() -> None:
    problems = title_problems(f"feat(zzz)!: {'a' * 61}", DECLARED)
    assert [
        ("Before 1.0.0" in p, "`scope/zzz`" in p, "The limit is 60" in p) for p in problems
    ] == [
        (True, False, False),
        (False, True, False),
        (False, False, True),
    ]


def test_title_problems_uses_custom_labels_source_when_given() -> None:
    """`title_problems` names `labels_source` when provided and keeps `.github/labels.yml` otherwise (#6469)."""
    default_problem = title_problems("feat(tools): build", DECLARED)[0]
    scoped_problem = title_problems(
        "feat(tools): build", DECLARED, labels_source=".github/labels.yml on `main` or `fix/1`"
    )[0]
    assert ".github/labels.yml does not declare `scope/tools`" in default_problem
    assert (
        ".github/labels.yml on `main` or `fix/1` does not declare `scope/tools`" in scoped_problem
    )


@pytest.mark.parametrize(
    ("title", "fragment"),
    [
        (
            "docs(spec): plan #2950 plan alternatives coverage telemetry",
            "repeats the word `plan`",
        ),
        ("docs(spec): plan #2950 Plan alternatives coverage", "repeats the word `plan`"),
        ("docs(spec): plan #2950 Add coverage for #2950", "repeats the issue number `#2950`"),
        ("fix(pr): fix #12 fix the title", "repeats the word `fix`"),
        ('docs(spec): plan #2950 "plan" x', "repeats the word `plan`"),
        ("docs(spec): plan #2950 (plan) x", "repeats the word `plan`"),
        ("docs(spec): plan #2950: plan x", "repeats the word `plan`"),
        ("docs(spec): plan  #2950 plan x", "repeats the word `plan`"),
        ("docs(spec): fix plan #2950 plan x", "repeats the word `plan`"),
        ("docs(spec): re-plan #3 re-plan x", "repeats the word `re-plan`"),
        ("docs(spec): plan #2950 - plan x", "repeats the word `plan`"),
        ("docs(spec): plan #2950 plan", "repeats the word `plan`"),
        ("docs(spec): plan #2950 add #2950", "repeats the issue number `#2950`"),
    ],
)
def test_a_title_that_repeats_a_word_or_the_issue_number_names_the_repeat(
    title: str, fragment: str
) -> None:
    (problem,) = title_problems(title, None)

    assert fragment in problem


@pytest.mark.parametrize(
    "title",
    [
        "docs(spec): plan #2950 Add alternatives coverage telemetry",
        "docs(spec): plan #3200 Refuse placeholder and cut plan text",
        "docs(spec): plan #3344 Refuse a plan that reads an absent model field",
        "docs(spec): plan #2950 Plans #2951 and the next",
        "fix(pr): handle #12 and #13 together",
        "docs(spec): plan #2950 add #29501",
        "docs(spec): plan #2950 add #295",
        "docs(spec): plan #\u0663 Add coverage",
        "docs(spec): plan #\u0663 plan coverage",
        "docs(spec): plan #2950",
    ],
)
def test_a_title_with_a_later_plan_word_or_another_number_has_no_problem(title: str) -> None:
    assert title_problems(title, None) == []


def test_without_the_labels_the_scope_is_not_checked() -> None:
    assert title_problems("feat(zzz-unknown): build it", None) == []


def test_the_summary_limit_is_the_one_the_workflow_holds() -> None:
    assert SUMMARY_MAX_CHARS == 60


# ── The body ──────────────────────────────────────────────────────────────────


def test_a_body_in_the_form_has_no_problem() -> None:
    assert body_problems(GOOD_BODY) == []


def test_the_attribution_lines_after_the_change_line_are_allowed() -> None:
    assert body_problems(f"{GOOD_BODY}\n\n" + "\n".join(ATTRIBUTION)) == []


def test_an_active_change_folder_is_allowed_in_the_change_line() -> None:
    body = f"{WHY}\n\nCloses #3198\n\nChange: `openspec/changes/3198-pull-request-form-check/`"
    assert body_problems(body) == []


def test_a_body_with_no_closes_line_is_refused() -> None:
    body = f"{WHY}\n\nChange: `{CHANGE}/`"
    assert [("no line `Closes" in p) for p in body_problems(body)] == [True]


def test_a_body_with_no_change_line_is_refused() -> None:
    body = f"{WHY}\n\nCloses #3198"
    assert [("no line `Change:`" in p) for p in body_problems(body)] == [True]


def test_a_change_line_in_another_form_is_refused() -> None:
    body = f"{WHY}\n\nCloses #3198\n\nChange: {CHANGE}/"
    assert [("no line `Change:`" in p) for p in body_problems(body)] == [True]


def test_a_body_that_closes_two_issues_is_refused() -> None:
    body = f"{WHY} It also fixes #12.\n\nCloses #3198\n\nChange: `{CHANGE}/`"
    assert [("closes 2 issues" in p) for p in body_problems(body)] == [True]


def test_a_closes_line_and_a_change_line_for_two_issues_are_refused() -> None:
    body = f"{WHY}\n\nCloses #3199\n\nChange: `{CHANGE}/`"
    assert [("issue 3199" in p and "issue 3198" in p) for p in body_problems(body)] == [True]


def test_closes_after_the_change_line_is_refused() -> None:
    body = f"{WHY}\n\nChange: `{CHANGE}/`\n\nCloses #3198"
    assert [("must come before" in p) for p in body_problems(body)] == [True]


def test_attribution_lines_before_closes_are_refused() -> None:
    body = f"{WHY}\n\n{ATTRIBUTION[0]}\n\nCloses #3198\n\nChange: `{CHANGE}/`"
    assert [("attribution lines" in p) for p in body_problems(body)] == [True]


@pytest.mark.parametrize("text", ["x", "placeholder", "TBD.", "ok", "fix it"])
def test_a_body_text_that_is_a_placeholder_or_too_short_is_refused(text: str) -> None:
    body = f"{text}\n\nCloses #3198\n\nChange: `{CHANGE}/`"
    assert len(body_problems(body)) == 1


def test_a_body_that_keeps_the_template_comment_is_refused() -> None:
    body = f"<!-- Delete this comment. -->\n\n{GOOD_BODY}"
    assert ["template" in p for p in body_problems(body)] == [True]


def test_a_change_line_that_keeps_the_names_of_the_template_is_refused() -> None:
    body = f"{WHY}\n\nCloses #3198\n\nChange: `openspec/changes/archive/<date>-<issue>-<slug>/`"
    assert [("no line `Change:`" in p) for p in body_problems(body)] == [True]


def test_a_text_may_name_the_closes_line_in_a_code_span() -> None:
    body = f"{WHY} It ends the body with `Closes #<issue>`.\n\nCloses #3198\n\nChange: `{CHANGE}/`"
    assert body_problems(body) == []


def test_a_breaking_change_footer_is_refused() -> None:
    body = f"{GOOD_BODY}\n\nBREAKING CHANGE: the old path is gone."
    assert ["BREAKING CHANGE" in p for p in body_problems(body)] == [True]


def test_a_body_over_the_limit_before_its_trailers_is_refused() -> None:
    why = "A reason that is long. " * 50
    problems = body_problems(f"{why.strip()}\n\nCloses #3198\n\nChange: `{CHANGE}/`")
    assert [f"The limit is {BODY_MAX_CHARS}" in p for p in problems] == [True]


def _body_above_closes(text: str) -> str:
    """A delivery body whose text above `Closes` is `text`, and whose `Closes` and `Change:` lines
    add 120 characters (#6633)."""
    change = f"openspec/changes/3198-{'a' * 71}"
    body = f"{text}\n\nCloses #3198\n\nChange: `{change}/`"
    assert len(body) - len(text) == 120
    return body


def test_a_body_over_the_limit_above_closes_is_refused() -> None:
    """The limit measures the text above `Closes`: the `Closes` and `Change:` lines add 120
    characters, and they do not count (#6633)."""
    problems = body_problems(_body_above_closes("a" * (BODY_MAX_CHARS + 1)))

    (problem,) = problems
    assert f"has {BODY_MAX_CHARS + 1} characters" in problem
    assert "Closes" in problem


def test_a_body_at_the_limit_above_closes_has_no_problem() -> None:
    assert body_problems(_body_above_closes("a" * BODY_MAX_CHARS)) == []


def _lengths(problems: list[str]) -> list[str]:
    """The lengths that the problems of the body limit name, as texts."""
    return [n for p in problems for n in re.findall(r"has (\d+) characters\.", p)]


@pytest.mark.parametrize(("length", "problems"), [(1000, []), (1001, ["1001"])])
def test_a_body_that_starts_with_a_blank_line_gets_one_measure(
    length: int, problems: list[str]
) -> None:
    """The open step and the ready check measure one text: the text above `Closes`, with the
    whitespace at its two ends removed, so a leading blank line counts at neither (#6735)."""
    text = "a" * length
    body = f"\n{text}\n\nCloses #5020\n\nChange: `openspec/changes/5020-one-measure/`"

    assert pull_form.measured_body_text(body, "Closes") == text
    assert _lengths(pull_form.open_body_problems(body, issue=5020, plan=False)) == problems
    assert _lengths(pull_form.body_problems(body)) == problems


def test_a_line_that_the_form_takes_as_no_closes_line_stays_in_the_measured_text() -> None:
    """The text ends at the line that the form takes as `Closes`, at open and at ready, and not at
    a line such as `Closes #abc` above it (#6735)."""
    text = f"{'a' * 995}\nCloses #abc"
    body = f"{text}\n\nCloses #5020\n\nChange: `openspec/changes/5020-one-measure/`"

    assert pull_form.measured_body_text(body, "Closes") == text
    assert _lengths(pull_form.open_body_problems(body, issue=5020, plan=False)) == ["1007"]
    assert _lengths(pull_form.body_problems(body)) == ["1007"]


@pytest.mark.parametrize("closes", ["Closes #5020 ", " Closes #5020", "\tCloses #5020\t"])
def test_a_marker_line_with_whitespace_at_its_ends_is_the_marker_line(closes: str) -> None:
    """The form check takes a `Closes` or `Plans` line with whitespace at its ends as the line, by
    the rule that ends the measured text, so a text at the limit has no problem (#6735)."""
    text = "a" * BODY_MAX_CHARS
    body = f"{text}\n\n{closes}\n\nChange: `openspec/changes/5020-one-measure/`"
    plan = f"{text}\n\n{closes.replace('Closes', 'Plans')}\n\nChange: `openspec/changes/5020-x/`"

    assert pull_form.measured_body_text(body, "Closes") == text
    assert pull_form.measured_body_text(plan, "Plans") == text
    assert pull_form.open_body_problems(body, issue=5020, plan=False) == []
    assert pull_form.body_problems(body) == []
    assert pull_form.plan_body_problems(plan, 5020) == []


@pytest.mark.parametrize("line", ["Closes", "Plans"])
def test_a_padded_marker_line_above_the_marker_line_is_a_second_marker_line(
    line: Literal["Closes", "Plans"],
) -> None:
    """A padded `Plans` or `Closes` line ends the measured text, so the form check counts it as a
    line too, and the text below it cannot pass the limit unmeasured (#6735)."""
    change = "Change: `openspec/changes/5020-one-measure/`"
    body = f"{'a' * 58}\n{line} #5020 \n{'b' * 2000}\n\n{line} #5020\n\n{change}"
    problems = (
        pull_form.plan_body_problems(body, 5020)
        if line == "Plans"
        else pull_form.body_problems(body)
    )

    assert len(pull_form.measured_body_text(body, line)) == 58
    assert problems == [
        MESSAGES.pr.form_plans_missing.format(issue=5020)
        if line == "Plans"
        else MESSAGES.pr.form_closes_many.format(count=2)
    ]


def test_the_docstring_of_the_body_check_names_the_text_above_closes() -> None:
    documented = body_problems.__doc__ or ""

    assert (
        "above the line `Closes`" in documented,
        "the whitespace at its start and at its end removed" in documented,
    ) == (True, True)


def test_the_trailers_do_not_count_toward_the_limit_of_the_body() -> None:
    body = f"{GOOD_BODY}\n\n" + "\n".join(ATTRIBUTION)
    assert len(body) > len(GOOD_BODY)
    assert body_problems(body) == []


def test_trailers_over_their_limit_are_refused() -> None:
    body = f"{GOOD_BODY}\n\n{'More text. ' * 60}"
    assert ["after `Change:`" in p for p in body_problems(body)] == [True]


def test_the_body_limit_is_the_limit_of_the_implement_job() -> None:
    from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS

    assert BODY_MAX_CHARS == CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS


# ── Placeholders ──────────────────────────────────────────────────────────────


FILLER_REFUSAL = "Not yet: I need to inspect the repository first."


@pytest.mark.parametrize(
    "text",
    [
        "x",
        " X. ",
        "y",
        "placeholder",
        "`TBD`",
        "N/A",
        "Lorem ipsum",
        "none",
        "probe",
        "__PROBE__",
        FILLER_REFUSAL,
        "not yet:",
        # The stub texts that the census of 2026-11-11 found in refine sections (#4799).
        "ignore",
        "Pending",
        "draft",
        "temporary",
        "Placeholder not final.",
    ],
)
def test_a_stand_in_text_is_a_placeholder(text: str) -> None:
    assert is_placeholder(text)


@pytest.mark.parametrize(
    "text",
    [
        "keep a label",
        "x-ray the cache",
        "a title",
        "The probe shows the path",
        "Not yet released",
        "Draft the release notes",
        "Ignore the pending items",
        "The placeholder is not final",
    ],
)
def test_a_real_text_is_no_placeholder(text: str) -> None:
    assert not is_placeholder(text)


class _Reply(BaseModel):
    answer: ReplyText


@pytest.mark.parametrize("text", ["x", "probe", "__PROBE__", FILLER_REFUSAL])
def test_reply_text_refuses_a_placeholder_with_its_error_type(text: str) -> None:
    with pytest.raises(ModelValidationError) as raised:
        _Reply(answer=text)
    assert [error["type"] for error in raised.value.errors()] == [PLACEHOLDER_ERROR_TYPE]


@pytest.mark.parametrize("text", ["", "Pydantic covers the schema check."])
def test_reply_text_keeps_a_blank_text_and_a_real_sentence(text: str) -> None:
    assert _Reply(answer=text).answer == text


# ── The builders ──────────────────────────────────────────────────────────────


def test_the_title_takes_the_type_and_the_scope_of_the_issue() -> None:
    title = build_title("feat(pr): build and check the title and body", "build the form", DECLARED)
    assert title == "feat(pr): build the form"


def test_the_title_of_an_issue_with_no_scope_has_none() -> None:
    assert build_title("docs: explain it", "explain the form", DECLARED) == "docs: explain the form"


def test_the_title_drops_the_mark_of_a_breaking_change_by_refusing_nothing() -> None:
    """The issue title may carry `!`; the title built never does."""
    assert (
        build_title("feat(pr)!: build it", "build the form", DECLARED) == "feat(pr): build the form"
    )


def test_a_summary_over_the_limit_is_refused_and_not_cut() -> None:
    summary = "build the form " * 6
    with pytest.raises(ValidationError, match="The limit is 60") as raised:
        build_title("feat(pr): build it", summary, DECLARED)
    assert "..." not in str(raised.value).replace("`...`", "")


def test_a_scope_with_no_label_is_refused_by_the_builder() -> None:
    with pytest.raises(ValidationError, match="scope/zzz"):
        build_title("feat(zzz): build it", "build the form", DECLARED)


def test_an_issue_title_with_no_type_is_refused() -> None:
    with pytest.raises(ValidationError, match="no Conventional Commit type"):
        build_title("Build the form", "build the form", DECLARED)


def test_the_body_is_the_text_closes_change_and_the_attribution() -> None:
    body = build_body(why=WHY, issue=3198, change=CHANGE, attribution=ATTRIBUTION)
    assert body == (
        f"{WHY}\n\nCloses #3198\n\nChange: `{CHANGE}/`\n\n{ATTRIBUTION[0]}\n\n{ATTRIBUTION[1]}"
    )


def test_the_body_built_passes_the_check() -> None:
    body = build_body(why=WHY, issue=3198, change=CHANGE, attribution=ATTRIBUTION)
    assert body_problems(body) == []


def test_a_why_over_the_limit_is_refused_and_not_cut() -> None:
    with pytest.raises(ValidationError, match="Shorten the text above `Closes`"):
        build_body(why="A reason that is long. " * 50, issue=3198, change=CHANGE)


@pytest.mark.parametrize("mark", ["...", "\u2026"])
def test_a_body_text_that_ends_with_a_cut_mark_is_refused(mark: str) -> None:
    why = f"{WHY} The change is not done{mark}"
    body = f"{why}\n\nCloses #3198\n\nChange: `{CHANGE}/`"

    assert ["ends with `...`" in problem for problem in body_problems(body)] == [True]
    with pytest.raises(ValidationError, match=r"ends with `\.\.\.`"):
        build_body(why=why, issue=3198, change=CHANGE)


def test_a_body_text_that_holds_a_cut_mark_inside_a_sentence_has_no_problem() -> None:
    body = f"{WHY} The text ... goes on.\n\nCloses #3198\n\nChange: `{CHANGE}/`"

    assert body_problems(body) == []


def test_a_placeholder_why_is_refused() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        build_body(why="placeholder", issue=3198, change=CHANGE)


def test_a_why_that_closes_another_issue_is_refused() -> None:
    with pytest.raises(ValidationError, match="closes 2 issues"):
        build_body(why=f"{WHY} This fixes #1.", issue=3198, change=CHANGE)


PLAN_CHANGE = "openspec/changes/3215-pull-form-in-jobs"


def test_the_plan_body_is_plans_the_text_and_change() -> None:
    body = build_plan_body(why=WHY, issue=3215, change=PLAN_CHANGE)

    assert body == f"{WHY}\n\nPlans #3215\n\nChange: `{PLAN_CHANGE}/`"
    assert plan_body_problems(body, 3215) == []


def test_the_plan_body_is_not_a_delivery_body() -> None:
    body = build_plan_body(why=WHY, issue=3215, change=PLAN_CHANGE)

    assert "The body has no line `Closes #<issue>`." in body_problems(body)


def test_a_placeholder_plan_text_is_refused() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        build_plan_body(why="placeholder", issue=3215, change=PLAN_CHANGE)


def test_a_short_plan_text_is_refused() -> None:
    with pytest.raises(ValidationError, match="characters"):
        build_plan_body(why="Short.", issue=3215, change=PLAN_CHANGE)


def test_a_plan_text_that_closes_an_issue_is_refused() -> None:
    with pytest.raises(ValidationError, match="closes no issue"):
        build_plan_body(why=f"{WHY} This closes #7.", issue=3215, change=PLAN_CHANGE)


def test_a_plan_text_over_the_limit_is_refused_and_not_cut() -> None:
    with pytest.raises(ValidationError, match="Shorten the text above `Plans`"):
        build_plan_body(why="A reason that is long. " * 50, issue=3215, change=PLAN_CHANGE)


def test_the_room_of_a_plan_text_is_the_body_limit() -> None:
    """`plan_body_room` is `BODY_MAX_CHARS`: the limit measures the text above `Plans`, so the
    `Plans` line and the `Change:` line leave the room of the text whole (#6633)."""
    assert plan_body_room(3215, PLAN_CHANGE) == BODY_MAX_CHARS
    at_limit = build_plan_body(why="a" * BODY_MAX_CHARS, issue=3215, change=PLAN_CHANGE)
    assert plan_body_problems(at_limit, issue=3215) == []

    with pytest.raises(ValidationError, match="Shorten the text above `Plans`"):
        build_plan_body(why="a" * (BODY_MAX_CHARS + 1), issue=3215, change=PLAN_CHANGE)


@pytest.mark.parametrize(("length", "problems"), [(1000, []), (1001, ["1001"])])
def test_a_plan_body_that_starts_with_a_blank_line_gets_one_measure(
    length: int, problems: list[str]
) -> None:
    """The plan form check and the plan check measure the text above `Plans`, with the whitespace
    at its two ends removed (#6735)."""
    text = "a" * length
    body = f"\n{text}\n\nPlans #3215\n\nChange: `{PLAN_CHANGE}/`"

    assert pull_form.measured_body_text(body, "Plans") == text
    assert _lengths(pull_form.plan_body_problems(body, 3215)) == problems


@pytest.mark.parametrize(
    ("plans", "taken"),
    [
        ("Plans #3215", True),
        ("Plans #3215 ", True),
        ("\tPlans #3215", True),
        ("Plans #\uff13\uff12\uff11\uff15", False),
        ("Plans #3215.", False),
    ],
)
def test_each_reader_of_a_plan_body_takes_the_plans_line_by_one_rule(
    plans: str, taken: bool
) -> None:
    """The plan form check, the plan check, the grounding of a plan and the measure take the
    `Plans` line by one rule, so they cannot disagree on the line of one body (#6735). A digit
    that is not ASCII names no issue: GitHub links no such reference."""
    text = "a" * 100
    body = f"{text}\n\n{plans}\n\nChange: `{PLAN_CHANGE}/`"
    files = [PullRequestFile(filename=f"{PLAN_CHANGE}/proposal.md", status="added")]
    changed = grounding.ChangedFilesRead(files, truncated=False)

    assert (
        MESSAGES.pr.form_plans_missing.format(issue=3215)
        not in pull_form.plan_body_problems(body, 3215),
        plan_check.issue_number(body) == 3215,
        grounding.plan_blockers(1, 3215, body, changed, "main") == [],
        pull_form.measured_body_text(body, "Plans") == text,
    ) == (taken, taken, taken, taken)


def test_a_short_plan_text_names_plans_and_where_the_text_goes() -> None:
    body = f"Short.\n\nPlans #3215\n\nChange: `{PLAN_CHANGE}/`"

    (problem,) = plan_body_problems(body, 3215)

    assert ("Plans" in problem, "above" in problem, "20" in problem) == (True, True, True)


def test_a_short_delivery_text_names_closes_and_not_plans() -> None:
    problems = body_problems(f"Short.\n\nCloses #1\n\nChange: `{CHANGE}/`")
    (problem,) = [text for text in problems if "characters" in text]

    assert ("Closes" in problem, "Plans" not in problem) == (True, True)


def test_the_eval_score_lines_after_the_change_line_are_allowed() -> None:
    """A prompt change records its live base and head scores in the body (#4005)."""
    body = f"{GOOD_BODY}\n\nBase eval score: 11\nHead eval score: 12"

    assert body_problems(body) == []
