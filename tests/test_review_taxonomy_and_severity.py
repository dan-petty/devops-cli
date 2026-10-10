"""One defect taxonomy for every finding (#948).

Session `20261001-224227` carried 148 distinct free-text category strings, so neither the report
nor the category metrics could group findings.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from devops_cli.ai.review.category_metrics import compute_category_metrics, resolve_finding_category
from devops_cli.ai.review.history import HistoryFinding
from devops_cli.ai.review_schema import DefectClass, Finding, SavedFinding
from devops_cli.config.constants import (
    CONST_REVIEW_CWE_DEFECT_CLASSES,
    CONST_REVIEW_DEFECT_KEYWORDS,
)

_SESSION_CATEGORIES: list[str | None] = json.loads(
    (
        Path(__file__).parent / "fixtures" / "review" / "candidate-categories-20261001-224227.json"
    ).read_text(encoding="utf-8")
)
_CWE = re.compile(r"CWE-\d+")
_CLASSES = {member.value for member in DefectClass}


def _finding(category: str | None, title: str = "Finding", **fields: object) -> Finding:
    return Finding(title=title, location="app.py:1", category=category, **fields)


def test_the_session_had_148_category_strings() -> None:
    """Verify the fixture holds the session's 148 distinct strings, one of them no category."""
    assert (
        len(_SESSION_CATEGORIES),
        len(set(_SESSION_CATEGORIES)),
        None in _SESSION_CATEGORIES,
    ) == (
        148,
        148,
        True,
    )


@pytest.mark.parametrize("raw", _SESSION_CATEGORIES)
def test_every_session_category_maps_into_the_taxonomy(raw: str | None) -> None:
    """Verify each string becomes a CWE or a defect class, keeps its original as `category_raw`,
    and has a defect class as its theme."""
    finding = _finding(raw)

    assert (
        finding.category is not None
        and (_CWE.fullmatch(finding.category) is not None or finding.category in _CLASSES),
        finding.category_raw == (raw if raw != finding.category else None),
        resolve_finding_category(finding) in _CLASSES,
    ) == (True, True, True)


def test_the_session_categories_fall_into_about_thirty_classes() -> None:
    """Verify the 148 strings give at most 30 themes, almost none of them `other`."""
    themes = Counter(resolve_finding_category(_finding(raw)) for raw in _SESSION_CATEGORIES)

    assert (len(themes) <= 30, themes[DefectClass.OTHER.value] <= 3) == (True, True)


def test_a_cwe_in_the_category_or_the_references_becomes_the_category() -> None:
    """Verify a CWE named in the category wins, then one in the references, then a defect class
    from the category's words or, with no category, the title's."""
    named = _finding("CWE-22: Improper Limitation of a Pathname to a Restricted Directory")
    referenced = _finding(None, references=["OWASP A10", "CWE-918: Server-Side Request Forgery"])
    worded = _finding("Path Traversal", references=["https://example.com/advisory"])
    untitled = _finding(None, title="Potential SSRF in the webhook fetcher")

    assert [(f.category, f.category_raw) for f in (named, referenced, worded, untitled)] == [
        ("CWE-22", "CWE-22: Improper Limitation of a Pathname to a Restricted Directory"),
        ("CWE-918", None),
        ("path_traversal", "Path Traversal"),
        ("ssrf", None),
    ]


def test_categorizing_a_finding_twice_changes_nothing() -> None:
    """Verify a saved finding read back keeps its category and its raw category."""
    finding = _finding("Command Injection")
    again = SavedFinding(**finding.model_dump())

    assert (again.category, again.category_raw) == ("injection", "Command Injection")


def test_one_theme_serves_the_metrics_and_history() -> None:
    """Verify the category metrics group by the theme, so a finding raised before the taxonomy
    existed, read back from history with its free-text category, joins the same row."""
    current = SavedFinding(title="Escape", location="a.py:1", references=["CWE-22"])
    historical = HistoryFinding(title="Escape", category="CWE-22 Path Traversal")

    assert list(compute_category_metrics([current, historical])) == ["path_traversal"]


def test_every_table_entry_names_a_defect_class() -> None:
    """Verify the keyword and CWE tables in the constants name only members of the enum."""
    named = {cls for _, cls in CONST_REVIEW_DEFECT_KEYWORDS} | set(
        CONST_REVIEW_CWE_DEFECT_CLASSES.values()
    )

    assert named - _CLASSES == set()
