"""Unit tests for the review stages the orchestrator runs: adversarial debate."""

from __future__ import annotations

from devops_cli.ai.review.stages.adversarial_debate import run_adversarial_debate_stage
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding


def test_adversarial_debate_stage() -> None:
    f_disabled = run_adversarial_debate_stage([], enabled=False)
    assert f_disabled == 0

    f_spec = SavedFinding(
        id="f1",
        title="Hallucinated CVE",
        severity="HIGH",
        location="src/app.py:10",
        description="httpx2 has unknown CVE alert",
        status="UNVERIFIED",
        persona="devsecops",
    )
    f_style = SavedFinding(
        id="f2",
        title="unverified stylistic issue",
        severity="LOW",
        location="src/app.py:15",
        description="unverified stylistic nitpick",
        status="UNVERIFIED",
        persona="devsecops",
    )
    f_valid = SavedFinding(
        id="f3",
        title="Hardcoded token",
        severity="CRITICAL",
        location="src/app.py:20",
        description="Plaintext token in code",
        status="UNVERIFIED",
        persona="devsecops",
    )
    payload = FileReviewPayload(
        file_path="src/app.py",
        file_hash="12345",
        findings=[f_spec, f_style, f_valid],
    )
    inval_count = run_adversarial_debate_stage([payload], enabled=True)
    assert inval_count == 2
    assert f_spec.status == "INVALIDATED"
    assert f_style.status == "INVALIDATED"
    assert f_valid.status == "UNVERIFIED"
