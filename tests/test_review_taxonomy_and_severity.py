"""One defect taxonomy for every finding, and severities calibrated to the evidence (#948).

Session `20261001-224227` carried 148 distinct free-text category strings, so neither the report
nor the category metrics could group findings. 54% of its candidates were HIGH, the value in both
prompt examples; the verifier could raise a severity, and 25 of 27 reported test findings were
CRITICAL or HIGH.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import get_args

import pytest

from devops_cli.ai.review.calibration import calibrate_severity
from devops_cli.ai.review.category_metrics import compute_category_metrics, resolve_finding_category
from devops_cli.ai.review.history import HistoryFinding
from devops_cli.ai.review.verdicts import VerifiedBy
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


_CAPS = [
    # CRITICAL requires VERIFIED.
    ("src/app.py:1", "SQL injection in the report query", "UNVERIFIED", None, "CRITICAL", "HIGH"),
    (
        "src/app.py:1",
        "SQL injection in the report query",
        "VERIFIED",
        "llm",
        "CRITICAL",
        "CRITICAL",
    ),
    # A hedged title is MEDIUM at most, whoever verified it.
    ("src/app.py:1", "Potential SSRF in the webhook fetcher", "VERIFIED", "llm", "HIGH", "MEDIUM"),
    # Calibration runs when the report is written, before any person's verdict.
    (
        "src/app.py:1",
        "Potential SSRF in the webhook fetcher",
        "VERIFIED",
        "human",
        "HIGH",
        "MEDIUM",
    ),
    ("src/app.py:1", "Token may leak into the logs", "UNVERIFIED", None, "CRITICAL", "MEDIUM"),
    ("src/app.py:1", "Retries could exhaust the pool", "UNVERIFIED", None, "LOW", "LOW"),
    # Tests and docs are LOW at most unless they concern a verified secret.
    ("tests/test_app.py:3", "Mock hides a failed upload", "VERIFIED", "llm", "HIGH", "LOW"),
    ("docs/guide.md:3", "Guide shows an insecure flag", "UNVERIFIED", None, "MEDIUM", "LOW"),
    ("tests/conftest.py:3", "Hardcoded API key in a fixture", "VERIFIED", "llm", "HIGH", "HIGH"),
    ("tests/conftest.py:3", "Hardcoded API key in a fixture", "UNVERIFIED", None, "HIGH", "LOW"),
    # A secret scanner's match is the secret's evidence, in a document as anywhere.
    (
        "changelog.d/1.md:3",
        "[GITLEAKS] Secret detected: OpenAI API Key",
        "UNVERIFIED",
        None,
        "CRITICAL",
        "HIGH",
    ),
    ("docs/guide.md:3", "[SECRET] AWS Access Key ID", "UNVERIFIED", None, "HIGH", "HIGH"),
    # No rule raises a severity.
    ("src/app.py:1", "Missing docstring", "UNVERIFIED", None, "INFO", "INFO"),
]


@pytest.mark.parametrize(
    ("location", "title", "status", "verified_by", "severity", "capped"), _CAPS
)
def test_severity_caps(
    location: str, title: str, status: str, verified_by: str | None, severity: str, capped: str
) -> None:
    """Verify each cap, and that a capped finding keeps the severity it was given."""
    finding = calibrate_severity(
        SavedFinding(
            title=title,
            location=location,
            severity=severity,
            status=status,
            verified=status == "VERIFIED",
            verified_by=verified_by,
        )
    )

    assert (finding.severity, finding.severity_raw) == (
        capped,
        None if capped == severity else severity,
    )


@pytest.mark.parametrize("verified_by", get_args(VerifiedBy))
def test_no_adjudicator_lifts_the_hedge_cap(verified_by: str) -> None:
    """Verify a hedged title VERIFIED by any adjudicator is MEDIUM at most. A passing criterion
    can check the opposite of the claim, and none of the verifier's 19 confirmations in sessions
    `20261003-005122` and `20261003-012555` was strictly valid, so neither is evidence enough to
    lift the cap (#1043)."""
    finding = calibrate_severity(
        SavedFinding(
            title="Potential SSRF in the webhook fetcher",
            location="src/app.py:1",
            severity="HIGH",
            status="VERIFIED",
            verified=True,
            verified_by=verified_by,
        )
    )

    assert (finding.severity, finding.severity_raw) == ("MEDIUM", "HIGH")


def test_a_capped_severity_keeps_the_first_raw_value() -> None:
    """Verify a finding the verifier already lowered keeps the persona's severity as raw."""
    finding = SavedFinding(
        title="Mock hides a failed upload",
        location="tests/test_app.py:3",
        severity="MEDIUM",
        severity_raw="CRITICAL",
    )

    assert (calibrate_severity(finding).severity, finding.severity_raw) == ("LOW", "CRITICAL")
