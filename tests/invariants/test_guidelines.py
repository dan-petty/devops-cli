"""The guidelines of `docs/guidelines/` apply with no change to each managed project (#5444).

A guideline holds no fact of one environment: no issue number, no date, no path of the
environment tree and no node. The README of the environment tree holds the decisions of one
environment, a GitHub tracker holds its gaps, and a dashboard, a command or the project review
gives its measured values. A word that dates a value (`today`, `currently`) and the id of a
state row or a query row (`S<n>`, `Q<n>`) mark a measured value, so a guideline holds none of
them. The index page of the folder has one line for each guideline, so the route to the folder
names no guideline and does not change when a guideline is added.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest
from markdown_it import MarkdownIt

from tests.support.paths import REPO_ROOT

GUIDELINES: Final = REPO_ROOT / "docs" / "guidelines"
INDEX: Final = GUIDELINES / "index.md"

# Each pattern names one kind of environment fact. An issue number is `#<n>`, `<owner>/<repo>#<n>`
# or the URL of a GitHub issue or pull request; an anchor such as `#6-sre` is not one, and
# neither is an HTML character reference such as `&#8722;`.
_ENVIRONMENT_FACTS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("issue number", re.compile(r"(?<!&)#\d+(?![\w-])")),
    ("issue number", re.compile(r"github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/\d+")),
    ("date", re.compile(r"\b\d{4}-\d{2}-\d{2}\b")),
    ("environment tree path", re.compile(r"(?<![\w-])k8s/")),
    ("node", re.compile(r"<[\w-]*node[\w-]*>")),
    ("word that dates a value", re.compile(r"\b(?:today|currently)\b", re.IGNORECASE)),
    ("state or query row id", re.compile(r"\b[SQ]\d+\b")),
)

# S3 is the name of an object storage API, not the id of a state row.
_NOT_ROW_IDS: Final[frozenset[str]] = frozenset({"S3"})


def environment_facts(text: str) -> list[str]:
    """Each environment fact of `text`, as `<kind>: <match>`, in the order of the patterns."""
    return [
        f"{kind}: {match.group()}"
        for kind, pattern in _ENVIRONMENT_FACTS
        for match in pattern.finditer(text)
        if not (kind == "state or query row id" and match.group() in _NOT_ROW_IDS)
    ]


def _guideline_files() -> list[Path]:
    """Each Markdown file of the folder, the index included."""
    return sorted(GUIDELINES.glob("*.md"))


def _index_targets() -> set[Path]:
    """The resolved file of each relative link of the index page."""
    tokens = MarkdownIt("commonmark").parse(INDEX.read_text(encoding="utf-8"))
    hrefs = [
        str(child.attrs["href"])
        for token in tokens
        if token.type == "inline"
        for child in token.children or []
        if child.type == "link_open"
    ]
    return {(GUIDELINES / href.partition("#")[0]).resolve() for href in hrefs if "://" not in href}


@pytest.mark.parametrize(
    "text",
    [
        "Issue #5444 adds it.",
        "The infra repo issue example/infra#13 sets it.",
        "See https://github.com/example/infra/issues/13 for it.",
        "The owner decided on 2026-11-13.",
        "The README of `k8s/` holds it.",
        "The pod ran on `<control-plane-node>`.",
        "The node is cordoned today.",
        "The controller is currently idle.",
        "Row S4 gives the count.",
        "Query Q9 reads the pulls.",
    ],
)
def test_each_kind_of_environment_fact_is_found(text: str) -> None:
    """The check finds each kind of environment fact that a guideline must not hold."""
    assert environment_facts(text) != []


def test_a_rule_with_no_environment_fact_passes() -> None:
    """A link anchor, a character reference, a version, an S3 store and a node role are not facts
    of one environment."""
    text = (
        "Read [Nested Time Limits](https://example.com/ARCHITECTURE.md#6-sre-limits). "
        "Write &#8722;8.1 for a change. Pin kubernetes-mixin `version-1.5.6`. "
        "Back up to an S3-compatible store. A control-plane node runs the API server."
    )

    assert environment_facts(text) == []


@pytest.mark.parametrize("path", _guideline_files(), ids=lambda path: path.name)
def test_a_guideline_holds_no_environment_fact(path: Path) -> None:
    """Each managed project applies the guideline with no change, so it names no issue, date,
    environment tree path, node, dating word or state row of one environment."""
    assert environment_facts(path.read_text(encoding="utf-8")) == []


def test_the_index_lists_each_guideline() -> None:
    """The index page links each guideline of the folder, and each relative link of the index
    opens a file that exists."""
    targets = _index_targets()
    guidelines = {path.resolve() for path in _guideline_files() if path != INDEX}

    assert guidelines
    assert sorted(path.name for path in guidelines - targets) == []
    assert sorted(str(path) for path in targets if not path.is_file()) == []
