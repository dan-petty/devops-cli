"""The form of the title and the body of a pull request (#3198).

`roadmap/pull_form.py` holds the rules and cuts no text. `devops pr describe` builds with them
(`tests/commands/test_pr_describe.py`), and `devops pr create` checks with them
(`tests/commands/test_pr_form_check.py`).
"""

from __future__ import annotations

import pytest

from devops_cli.exceptions import ValidationError
from devops_cli.roadmap.pull_form import (
    BODY_MAX_CHARS,
    SUMMARY_MAX_CHARS,
    body_problems,
    build_body,
    build_title,
    is_placeholder,
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


@pytest.mark.parametrize(
    ("title", "fragment"),
    [
        ("A plain title", "is not in the form"),
        ("feat(pr) build it", "is not in the form"),
        ("Feat(pr): build it", "is not in the form"),
        ("feat(): build it", "is not in the form"),
        ("feat(pr): build it\nand more", "more than one line"),
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


@pytest.mark.parametrize("text", ["x", " X. ", "placeholder", "`TBD`", "N/A", "Lorem ipsum"])
def test_a_stand_in_text_is_a_placeholder(text: str) -> None:
    assert is_placeholder(text)


@pytest.mark.parametrize("text", ["keep a label", "x-ray the cache", "a title"])
def test_a_real_text_is_no_placeholder(text: str) -> None:
    assert not is_placeholder(text)


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


def test_a_placeholder_why_is_refused() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        build_body(why="placeholder", issue=3198, change=CHANGE)


def test_a_why_that_closes_another_issue_is_refused() -> None:
    with pytest.raises(ValidationError, match="closes 2 issues"):
        build_body(why=f"{WHY} This fixes #1.", issue=3198, change=CHANGE)
