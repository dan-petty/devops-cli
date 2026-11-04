"""The form of the title and the body of a pull request (#3198).

One module holds the rules, and nothing else holds them. `devops pr describe` builds a title and
a body with them, and `devops pr create` checks a title and a body with them. The squash commit
takes the title as its subject and the body as its message (CONTRIBUTING.md, section 4), so a
title or a body that breaks the form reads as broken in `git log` and in the changelog.

The module never cuts a text. A text that breaks a rule is refused, and the caller writes a
shorter one. A cut text ends with `...` and reads as a mistake. The functions read no file and make
no request: the caller passes the labels that the repository declares.

The `Semantic PR title` workflow (`.github/workflows/pr-title.yml`) cannot read this module: an
action takes static inputs. `tests/invariants/test_workflow_contracts.py` holds its summary pattern
and its scope list equal to `SUMMARY_MAX_CHARS` and to the labels file.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from typing import Final

from devops_cli.config.constants import (
    CONST_BRANCH_TYPES,
    CONST_OPENSPEC_ARCHIVED_DIR_RE,
    CONST_OPENSPEC_CHANGE_DIR_RE,
    CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS,
    CONST_ROADMAP_LABELS_PATH,
    CONST_ROADMAP_SCOPE_LABEL_PREFIX,
)
from devops_cli.exceptions import ValidationError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.commit_title import commit_scope, commit_type

# The most characters of the summary of a title (CONTRIBUTING.md, Naming): the part after
# `<type>(<scope>): `, which the check `Semantic PR title` measures.
SUMMARY_MAX_CHARS: Final[int] = 60
# The characters that JavaScript `.` does not match, so that a title with one has no header.
_LINE_BREAKS: Final[tuple[str, ...]] = ("\n", "\r", "\u2028", "\u2029")


def summary_length(text: str) -> int:
    """The length of `text` as the check `Semantic PR title` counts it. Its pattern `^.{1,60}$`
    runs in JavaScript, where `.` is a UTF-16 code unit: a character outside the Basic
    Multilingual Plane, such as an emoji, counts as two (#3249). A lone surrogate, which a byte
    that is no UTF-8 gives in argv, counts as one, as it does in JavaScript."""
    return len(text) + sum(ord(char) > 0xFFFF for char in text)


# The most characters of a body before its trailers: the text, the `Closes` line and the `Change:`
# line, as the squash message takes them. It is the limit that the implement job already holds.
BODY_MAX_CHARS: Final[int] = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS
# The fewest characters of the text above `Closes`: what the change does, and why. A shorter text
# is a placeholder in all but name.
_BODY_TEXT_MIN_CHARS: Final[int] = 20
# The most characters after the `Change:` line: the attribution lines of the agent.
_TRAILER_MAX_CHARS: Final[int] = 400
# The scope of the pull request of release-please, which the workflow allows.
_RELEASE_SCOPE: Final[str] = "main"
_TITLE: Final[re.Pattern[str]] = re.compile(
    r"(?P<type>[a-z]+)(?:\((?P<scope>[^()\s]+)\))?(?P<bang>!?): (?P<summary>\S.*)"
)
# The first word and issue number of a summary, such as `plan #2950 Add coverage`: the word before
# the number, the number (ASCII digits), and the text after them. Words before the word, spaces
# before the number, a colon after it and a dash before the text do not hide the repeat (#3255).
_LEAD: Final[re.Pattern[str]] = re.compile(
    r"(?:\S+\s+)*?(?P<word>[^\W\d_][\w-]*)\s+#(?P<number>[0-9]+)(?![0-9])[\s:\u2013\u2014-]*"
    r"(?P<rest>.*)"
)
_CLOSES_LINE: Final[re.Pattern[str]] = re.compile(r"Closes #(?P<issue>\d+)")
_PLANS_LINE: Final[re.Pattern[str]] = re.compile(r"Plans #(?P<issue>\d+)")
# GitHub closes the issue that follows one of these words, with an optional colon.
_CLOSING_REFERENCE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?):?\s+(?:[\w.-]+/[\w.-]+)?#\d+", re.IGNORECASE
)
_CHANGE_LINES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(rf"Change: `{CONST_OPENSPEC_CHANGE_DIR_RE}/`"),
    re.compile(rf"Change: `{CONST_OPENSPEC_ARCHIVED_DIR_RE}/`"),
)
_ATTRIBUTION: Final[re.Pattern[str]] = re.compile(
    r"^(?:Co-Authored-By:|Claude-Session:|\W*Generated (?:with|by)\b)|claude\.ai/code/session",
    re.IGNORECASE | re.MULTILINE,
)
# What the pull request template leaves in a body that nobody edited: its comment. A name in angle
# brackets in the `Closes` line or the `Change:` line is no match of those two lines.
_TEMPLATE_COMMENT: Final[str] = "<!--"
# The texts that a model writes when it has nothing to write. A text is a placeholder when it is
# one of these, with no case and no punctuation around it.
_PLACEHOLDERS: Final[frozenset[str]] = frozenset(
    {
        "x",
        "xx",
        "xxx",
        "foo",
        "bar",
        "test",
        "tbd",
        "todo",
        "wip",
        "fixme",
        "placeholder",
        "lorem ipsum",
        "n/a",
        "na",
        "none",
        "nothing",
        "summary",
        "description",
        "title",
        "body",
        "why",
        "text",
    }
)
_PLACEHOLDER_EDGES: Final[str] = " \t\r\n.,:;!?-_*<>[]()`'\""


def is_placeholder(text: str) -> bool:
    """Whether `text` is a text that stands in for the real text, such as `x` or `placeholder`."""
    return text.strip(_PLACEHOLDER_EDGES).casefold() in _PLACEHOLDERS


def _declared_scopes(declared: Collection[str]) -> set[str]:
    """The scopes that the label names `declared` give, and the scope of a release."""
    prefix = CONST_ROADMAP_SCOPE_LABEL_PREFIX
    return {name.removeprefix(prefix) for name in declared if name.startswith(prefix)} | {
        _RELEASE_SCOPE
    }


def _repeat_problems(summary: str) -> list[str]:
    """What a summary that starts with `<word> #<number>` repeats: the word as the first word of
    the text after the number (`plan #2950 plan coverage`), or the number in that text. A later
    use of the word is not judged, because `plan #3200 Refuse a plan that ...` is a right title."""
    texts = MESSAGES.pr
    found = _LEAD.match(summary)
    if found is None:
        return []
    word, number, rest = found["word"], found["number"], found["rest"]
    problems = []
    first = rest.split(maxsplit=1)[0].strip(_PLACEHOLDER_EDGES) if rest else ""
    if first.casefold() == word.casefold():
        problems.append(texts.form_title_repeat_word.format(word=word, number=number))
    if re.search(rf"#{number}(?![0-9])", rest):
        problems.append(texts.form_title_repeat_number.format(number=number))
    return problems


def _summary_problems(summary: str) -> list[str]:
    texts = MESSAGES.pr
    if is_placeholder(summary):
        return [texts.form_placeholder.format(part="summary", text=summary.strip())]
    problems = []
    length = summary_length(summary)
    if length > SUMMARY_MAX_CHARS:
        problems.append(texts.form_summary_long.format(length=length, limit=SUMMARY_MAX_CHARS))
    if summary.rstrip().endswith(("...", "\u2026")):
        problems.append(texts.form_summary_cut)
    return [*problems, *_repeat_problems(summary)]


def title_problems(title: str, declared: Collection[str] | None = None) -> list[str]:
    """What breaks the form `<type>(<scope>): <summary>` in `title`, one text for each problem,
    and none when the title is right.

    The type is one of the Conventional Commit types, there is no `!`, and the summary has at most
    `SUMMARY_MAX_CHARS` characters (`summary_length`), ends with no `...` and is no placeholder.
    The title is on one line: the parser of the check `Semantic PR title` refuses a title that has
    a `\r`, a `\n`, a U+2028 or a U+2029. A scope must have its label in `declared`, the label
    names that `.github/labels.yml` holds. When `declared` is None the scope is not checked against
    the labels, as in a dry run that reads no file."""
    texts = MESSAGES.pr
    if any(mark in title.strip() for mark in _LINE_BREAKS):
        return [texts.form_title_lines]
    found = _TITLE.fullmatch(title.strip())
    if found is None:
        return [texts.form_title_shape.format(title=title.strip())]
    problems = []
    if found["type"] not in CONST_BRANCH_TYPES:
        problems.append(
            texts.form_title_type.format(type=found["type"], types=", ".join(CONST_BRANCH_TYPES))
        )
    if found["bang"]:
        problems.append(texts.form_title_breaking)
    scope = found["scope"]
    if scope is not None and declared is not None and scope not in _declared_scopes(declared):
        problems.append(
            texts.form_title_scope.format(
                scope=scope,
                path=CONST_ROADMAP_LABELS_PATH,
                label=f"{CONST_ROADMAP_SCOPE_LABEL_PREFIX}{scope}",
            )
        )
    return [*problems, *_summary_problems(found["summary"])]


def _closing_problems(body: str, lines: Sequence[str]) -> tuple[list[str], int | None, int | None]:
    """The problems of the `Closes` line, the issue it names and the index of its line."""
    texts = MESSAGES.pr
    closing = [(i, m) for i, line in enumerate(lines) if (m := _CLOSES_LINE.fullmatch(line))]
    references = len(_CLOSING_REFERENCE.findall(body))
    if not closing:
        return [texts.form_closes_missing], None, None
    if references != 1 or len(closing) != 1:
        return [texts.form_closes_many.format(count=max(references, len(closing)))], None, None
    index, match = closing[0]
    return [], int(match["issue"]), index


def _change_problems(lines: Sequence[str]) -> tuple[list[str], int | None, int | None]:
    """The problems of the `Change:` line, the issue its folder names and the index of its line."""
    texts = MESSAGES.pr
    found = [
        (i, m)
        for i, line in enumerate(lines)
        for pattern in _CHANGE_LINES
        if (m := pattern.fullmatch(line))
    ]
    if len(found) != 1:
        return [texts.form_change_missing], None, None
    index, match = found[0]
    return [], int(match["issue"]), index


def body_problems(body: str) -> list[str]:
    """What breaks the form of `body` in the sense of CONTRIBUTING.md, section 4, one text for each
    problem, and none when the body is right.

    The body is the text of what the change does and why, then the line `Closes #<issue>` for the
    one issue it closes, then the line `Change:` with the folder of the change in a code span, then,
    when given, the attribution lines. The text, the `Closes` line and the `Change:` line have at
    most `BODY_MAX_CHARS` characters. The text is no placeholder and keeps nothing of the pull
    request template."""
    texts = MESSAGES.pr
    lines = body.strip().splitlines()
    problems: list[str] = []
    closes_problems, closes_issue, closes_at = _closing_problems(body, lines)
    change_problems, change_issue, change_at = _change_problems(lines)
    problems += closes_problems + change_problems
    if closes_issue is not None and change_issue is not None and closes_issue != change_issue:
        problems.append(texts.form_issue_differs.format(closes=closes_issue, change=change_issue))
    if closes_at is not None and change_at is not None:
        if closes_at > change_at:
            problems.append(texts.form_order)
        else:
            problems += _text_problems(
                "\n".join(lines[:closes_at]), "\n".join(lines[: change_at + 1])
            )
            problems += _trailer_problems("\n".join(lines[change_at + 1 :]))
    if _TEMPLATE_COMMENT in body:
        problems.append(texts.form_template_text)
    if "BREAKING CHANGE" in body:
        problems.append(texts.form_body_breaking)
    return problems


def plan_body_problems(body: str, issue: int) -> list[str]:
    """What breaks the form of the body of a plan pull request for `issue` (#3314), one text for
    each problem, and none when the body is right.

    A plan delivers nothing, so its body has the line `Plans #<issue>` where a delivery has
    `Closes`, and it closes no issue. The rest is the form of a delivery: the text, the `Change:`
    line with the active folder of the same issue, and the length and trailer bounds.
    """
    texts = MESSAGES.pr
    lines = body.strip().splitlines()
    plans = [(i, m) for i, line in enumerate(lines) if (m := _PLANS_LINE.fullmatch(line))]
    problems: list[str] = []
    if len(plans) != 1 or int(plans[0][1]["issue"]) != issue:
        problems.append(texts.form_plans_missing.format(issue=issue))
    if _CLOSING_REFERENCE.search(body):
        problems.append(texts.form_plan_closes)
    change_problems, change_issue, change_at = _change_problems(lines)
    problems += change_problems
    if change_issue is not None and change_issue != issue:
        problems.append(texts.form_plan_change_differs.format(issue=issue, change=change_issue))
    if len(plans) == 1 and change_at is not None:
        plans_at = plans[0][0]
        if plans_at > change_at:
            problems.append(texts.form_plan_order)
        else:
            problems += _text_problems(
                "\n".join(lines[plans_at + 1 : change_at]), "\n".join(lines[: change_at + 1])
            )
            problems += _trailer_problems("\n".join(lines[change_at + 1 :]))
    if _TEMPLATE_COMMENT in body:
        problems.append(texts.form_template_text)
    if "BREAKING CHANGE" in body:
        problems.append(texts.form_body_breaking)
    return problems


def _text_problems(text: str, measured: str) -> list[str]:
    """The problems of the text above `Closes`, and of the length of `measured`: the body up to
    the `Change:` line."""
    texts = MESSAGES.pr
    problems = []
    if _ATTRIBUTION.search(text):
        problems.append(texts.form_attribution_first)
    elif is_placeholder(text):
        problems.append(texts.form_placeholder.format(part="body", text=text.strip()))
    elif len(text.strip()) < _BODY_TEXT_MIN_CHARS:
        problems.append(
            texts.form_body_short.format(length=len(text.strip()), minimum=_BODY_TEXT_MIN_CHARS)
        )
    if len(measured) > BODY_MAX_CHARS:
        problems.append(texts.form_body_long.format(length=len(measured), limit=BODY_MAX_CHARS))
    return problems


def _trailer_problems(trailer: str) -> list[str]:
    if len(trailer.strip()) > _TRAILER_MAX_CHARS:
        return [
            MESSAGES.pr.form_trailer_long.format(
                length=len(trailer.strip()), limit=_TRAILER_MAX_CHARS
            )
        ]
    return []


def _refuse(problems: Sequence[str], field: str) -> None:
    """Raise `ValidationError` with every problem when there is one."""
    if problems:
        raise ValidationError("\n".join(f"- {problem}" for problem in problems), field=field)


def build_title(issue_title: str, summary: str, declared: Collection[str] | None) -> str:
    """The title of the pull request that delivers the issue titled `issue_title`: its type and
    its scope, then `summary`. `declared` holds the label names of `.github/labels.yml`, or is None
    when the scope is not checked against them.

    Nothing is cut. A summary that breaks a rule, a scope without a label, or an issue title with
    no Conventional Commit type raises `ValidationError` that names every problem."""
    kind = commit_type(issue_title)
    if kind is None:
        raise ValidationError(
            MESSAGES.pr.form_issue_title_type.format(title=issue_title.strip()), field="title"
        )
    scope = commit_scope(issue_title)
    title = f"{kind}({scope}): {summary.strip()}" if scope else f"{kind}: {summary.strip()}"
    _refuse(title_problems(title, declared), "title")
    return title


def build_body(*, why: str, issue: int, change: str, attribution: Sequence[str] = ()) -> str:
    """The body of the pull request: `why`, the line `Closes #<issue>`, the line `Change:` with
    the folder `change` (a path under `openspec/changes/`, with no slash at its end), and each of
    `attribution` as a paragraph.

    Nothing is cut. A body that breaks a rule raises `ValidationError` that names every problem,
    and the caller writes a shorter `why`."""
    parts = [why.strip(), f"Closes #{issue}", f"Change: `{change}/`"]
    body = "\n\n".join(parts)
    trailer = "\n\n".join(line.strip() for line in attribution if line.strip())
    full = f"{body}\n\n{trailer}" if trailer else body
    _refuse(body_problems(full), "body")
    return full
