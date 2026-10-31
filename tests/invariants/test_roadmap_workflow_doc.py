"""`docs/ROADMAP_WORKFLOW.md` is the one page that names the steps of an issue's life, and it stays
true to the labels file and to the code (#2909, ADR 0016).

The page must name each `status/*` and `owner/*` label of `.github/labels.yml`, each Status and
Owner value of the code, and each key of the job record. It must not name a label or a key that
does not exist. A label or a key counts as named when a code span of the page holds exactly that
text. The page also holds the eight steps, the three gates, a table of the transitions and one
diagram.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from markdown_it import MarkdownIt
from markdown_it.token import Token

from devops_cli.config.constants import (
    CONST_ROADMAP_OWNER_VALUES,
    CONST_ROADMAP_STATUS_VALUES,
)
from devops_cli.roadmap.store import (
    AlternativesRecordKey,
    ImplementRecordKey,
    ItemField,
    RefineRecordKey,
    StageRecordKey,
    field_label,
)
from devops_cli.roadmap.title_labels import declared_label_names
from tests.support.paths import REPO_ROOT

DOCUMENT = REPO_ROOT / "docs" / "ROADMAP_WORKFLOW.md"
LABELS_FILE = REPO_ROOT / ".github" / "labels.yml"
STEPS = (
    "Capture",
    "Refine",
    "Plan",
    "Claim",
    "Implement",
    "Verify",
    "Review and merge",
    "Release and learn",
)
GATES = ("G1", "G2", "G3")
TRANSITION_COLUMNS = ("From state", "Event", "To state", "Actor")
LABEL_FAMILIES = ("status/", "owner/")
RECORD_KEYS = frozenset(
    key.value
    for keys in (RefineRecordKey, AlternativesRecordKey, StageRecordKey, ImplementRecordKey)
    for key in keys
)
RECORD_PREFIXES = frozenset(key.partition(".")[0] for key in RECORD_KEYS)


def _tokens(text: str) -> list[Token]:
    """The CommonMark tokens of `text`, with tables."""
    return MarkdownIt("commonmark").enable("table").parse(text)


def _code_spans(tokens: list[Token]) -> set[str]:
    """The text of each inline code span, in prose, lists and tables."""
    return {
        child.content
        for token in tokens
        if token.type == "inline"
        for child in token.children or []
        if child.type == "code_inline"
    }


def _table_headers(tokens: list[Token]) -> Iterator[tuple[str, ...]]:
    """The header cells of each table."""
    header: list[str] = []
    in_header = False
    for index, token in enumerate(tokens):
        if token.type == "thead_open":
            header, in_header = [], True
        elif token.type == "thead_close":
            yield tuple(header)
            in_header = False
        elif in_header and token.type == "th_open":
            header.append(tokens[index + 1].content.strip())


def _table_rows(tokens: list[Token], header: tuple[str, ...]) -> list[tuple[str, ...]]:
    """The body rows of the table whose header cells are `header`; the cell text keeps its code
    marks."""
    rows: list[tuple[str, ...]] = []
    current: list[str] | None = None
    matched = False
    for index, token in enumerate(tokens):
        if token.type == "thead_open":
            matched = False
        elif token.type == "th_open":
            matched = matched or tokens[index + 1].content.strip() == header[0]
        elif token.type == "tr_open" and matched:
            current = []
        elif token.type == "td_open" and current is not None:
            current.append(tokens[index + 1].content.strip())
        elif token.type == "tr_close" and current:
            rows.append(tuple(current))
            current = None
    return [row for row in rows if len(row) == len(header)]


def _fence_languages(tokens: list[Token]) -> set[str]:
    """The info string of each fenced code block."""
    return {token.info.strip() for token in tokens if token.type == "fence"}


def _text_of(tokens: list[Token]) -> str:
    """The prose of the document: inline text and code spans, fences left out."""
    return "\n".join(token.content for token in tokens if token.type == "inline")


def _code_labels() -> set[str]:
    """The Status and Owner labels that the code gives."""
    return {
        *(field_label(ItemField.STATUS, value) for value in CONST_ROADMAP_STATUS_VALUES),
        *(field_label(ItemField.OWNER, value) for value in CONST_ROADMAP_OWNER_VALUES),
    }


def _declared_labels() -> set[str]:
    """The Status and Owner labels that `.github/labels.yml` declares."""
    names = declared_label_names(LABELS_FILE.read_text(encoding="utf-8"))
    return {name for name in names if name.startswith(LABEL_FAMILIES)}


def _is_record_key(span: str) -> bool:
    """Whether a code span has the form of a record key, such as `implement.job`."""
    prefix, _, name = span.partition(".")
    return prefix in RECORD_PREFIXES and name.isidentifier()


def workflow_problems(text: str) -> list[str]:
    """Why the document `text` is out of step with the labels file and the code; empty when it
    is in step."""
    tokens = _tokens(text)
    spans = _code_spans(tokens)
    declared = _declared_labels()
    required = declared | _code_labels()
    # A span such as `status/*` names a family, not a label.
    named_labels = {
        span for span in spans if span.startswith(LABEL_FAMILIES) and not span.endswith("*")
    }
    named_keys = {span for span in spans if _is_record_key(span)}
    prose = _text_of(tokens)
    problems = [f"label {label} is missing" for label in sorted(required - named_labels)]
    problems += [f"label {label} does not exist" for label in sorted(named_labels - declared)]
    problems += [f"record key {key} is missing" for key in sorted(RECORD_KEYS - named_keys)]
    problems += [f"record key {key} does not exist" for key in sorted(named_keys - RECORD_KEYS)]
    problems += [f"step {step} is missing" for step in STEPS if step not in prose]
    problems += [f"gate {gate} is missing" for gate in GATES if gate not in prose]
    if TRANSITION_COLUMNS not in set(_table_headers(tokens)):
        problems.append("the transition table is missing")
    if "mermaid" not in _fence_languages(tokens):
        problems.append("the diagram is missing")
    problems += _retry_problems(tokens)
    return problems


def _retry_problems(tokens: list[Token]) -> list[str]:
    """The retry comment is read on a stopped Item. A stop sets Ready, so a row of the retry
    comment must not start from In progress and must name the record key of the stop."""
    retry_rows = [
        row for row in _table_rows(tokens, TRANSITION_COLUMNS) if "implement: retry" in row[1]
    ]
    if not retry_rows:
        return ["the retry transition is missing"]
    return [
        f"the retry transition starts from {row[0]}"
        for row in retry_rows
        if "`status/in-progress`" in row[0] or "`implement.stopped`" not in row[0]
    ]


def _document() -> str:
    """The text of the workflow document."""
    return DOCUMENT.read_text(encoding="utf-8")


def test_labels_file_declares_the_status_and_owner_values_of_the_code() -> None:
    assert _declared_labels() == _code_labels()


def test_workflow_document_matches_the_labels_and_the_code() -> None:
    assert workflow_problems(_document()) == []


@pytest.mark.parametrize("label", sorted(_code_labels()))
def test_document_without_a_label_fails(label: str) -> None:
    removed = _document().replace(f"`{label}`", "")
    assert f"label {label} is missing" in workflow_problems(removed)


def test_document_with_a_label_that_does_not_exist_fails() -> None:
    assert "label status/done does not exist" in workflow_problems(
        _document() + "\n`status/done`\n"
    )


@pytest.mark.parametrize("key", sorted(RECORD_KEYS))
def test_document_without_a_record_key_fails(key: str) -> None:
    removed = _document().replace(f"`{key}`", "")
    assert f"record key {key} is missing" in workflow_problems(removed)


def test_document_with_a_record_key_that_does_not_exist_fails() -> None:
    problems = workflow_problems(_document() + "\n`implement.nothing`\n")
    assert "record key implement.nothing does not exist" in problems


@pytest.mark.parametrize("name", [*STEPS, *GATES])
def test_document_without_a_step_or_a_gate_fails(name: str) -> None:
    kind = "gate" if name in GATES else "step"
    assert f"{kind} {name} is missing" in workflow_problems(_document().replace(name, "xx"))


def test_document_without_the_transition_table_fails() -> None:
    removed = _document().replace("| From state |", "| State |")
    assert "the transition table is missing" in workflow_problems(removed)


def test_document_without_the_diagram_fails() -> None:
    removed = _document().replace("```mermaid", "```text")
    assert "the diagram is missing" in workflow_problems(removed)


def test_document_with_a_retry_from_in_progress_fails() -> None:
    wrong = _document().replace(
        "| `status/ready` or `status/planned`, with `implement.stopped` |",
        "| `status/in-progress` |",
    )
    assert wrong != _document()
    assert any(p.startswith("the retry transition starts from") for p in workflow_problems(wrong))


def test_document_without_the_retry_transition_fails() -> None:
    removed = _document().replace("implement: retry", "implement: again")
    assert "the retry transition is missing" in workflow_problems(removed)
