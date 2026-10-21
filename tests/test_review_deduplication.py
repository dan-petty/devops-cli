"""Unit tests for review finding deduplication by (fingerprint, location) and deleted modules (#1151)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from devops_cli.ai.review.adjudication import Verdict, judge_candidate
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import FileReviewPayload, ReviewSessionPayload, SavedFinding


def _sample_finding(
    *,
    fingerprint: str = "fp123",
    location: str = "src/main.py:10",
    title: str = "Hardcoded Secret",
    severity: str = "HIGH",
    status: str = "UNVERIFIED",
    producer: str = "gitleaks",
) -> SavedFinding:
    return SavedFinding(
        fingerprint=fingerprint,
        location=location,
        title=title,
        severity=severity,
        status=status,
        producer=producer,
        description="Finding description",
        fix="Remove secret",
        reportable=True,
    )


def test_two_payloads_holding_one_admitted_finding_give_one_row(tmp_path: Path) -> None:
    """Two payloads holding one admitted finding (same fingerprint and location) yield one row."""
    orchestrator = ReviewPipelineOrchestrator(target_dir=tmp_path)
    f1 = _sample_finding(fingerprint="fp_abc", location="src/config.py:15")
    f2 = _sample_finding(fingerprint="fp_abc", location="src/config.py:15")

    p1 = FileReviewPayload(file_path="src/config.py", findings=[f1])
    p2 = FileReviewPayload(file_path="src/config.py", findings=[f2])

    deduped = orchestrator._collect_and_deduplicate_findings([p1, p2])
    assert len(deduped) == 1
    assert deduped[0].fingerprint == "fp_abc"
    assert deduped[0].location == "src/config.py:15"


def test_two_findings_with_one_fingerprint_at_different_lines_give_two_rows(tmp_path: Path) -> None:
    """Two findings with the same fingerprint at different lines yield two distinct rows."""
    orchestrator = ReviewPipelineOrchestrator(target_dir=tmp_path)
    f1 = _sample_finding(fingerprint="fp_dup", location="src/handler.py:10")
    f2 = _sample_finding(fingerprint="fp_dup", location="src/handler.py:25")

    payload = FileReviewPayload(file_path="src/handler.py", findings=[f1, f2])

    deduped = orchestrator._collect_and_deduplicate_findings([payload])
    assert len(deduped) == 2
    assert {f.location for f in deduped} == {"src/handler.py:10", "src/handler.py:25"}
    assert all(f.fingerprint == "fp_dup" for f in deduped)


def test_verdict_on_raised_finding_is_mirrored_on_findings_json_copy_found_by_key() -> None:
    """A verdict recorded on a candidate finding is mirrored on its findings.json copy matched by (fingerprint, location)."""
    cand = _sample_finding(fingerprint="fp_sql", location="src/db.py:42", status="UNVERIFIED")
    rep = _sample_finding(fingerprint="fp_sql", location="src/db.py:42", status="UNVERIFIED")

    candidates = ReviewSessionPayload(findings=[cand])
    reported = ReviewSessionPayload(findings=[rep])

    moved = judge_candidate(
        candidates,
        reported,
        number=1,
        verdict=Verdict(status="VERIFIED", reason="Valid SQL injection vulnerability"),
    )

    assert moved is False
    assert candidates.findings[0].status == "VERIFIED"
    assert candidates.findings[0].verified is True
    assert reported.findings[0].status == "VERIFIED"
    assert reported.findings[0].verified is True


def test_classification_and_contract_grounding_modules_are_deleted() -> None:
    """Asserts that devops_cli.ai.review.classification and contract_grounding are deleted."""
    assert importlib.util.find_spec("devops_cli.ai.review.classification") is None
    assert importlib.util.find_spec("devops_cli.ai.review.contract_grounding") is None
