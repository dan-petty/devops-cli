"""Tests for verdict writers, invariant assertions, citation checks, and executed verdict finality."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp.server import review_findings
from devops_cli.ai.review.verdicts import (
    VerifiedBy,
    apply_verdict,
    assert_verdict_invariants,
)
from devops_cli.ai.review_schema import (
    CriterionExecutionResult,
    Finding,
    ReviewSessionPayload,
    SavedFinding,
    _merge_two_findings,
    compute_verdict_distributions,
)
from devops_cli.commands.review import app

runner = CliRunner()

_ALL_WRITERS: list[tuple[str, VerifiedBy | None]] = [
    ("human", "human"),
    ("vulnerable_dependency", "deterministic:vulnerable_dependency"),
    ("dry_run", "deterministic:dry_run"),
]


@pytest.mark.parametrize(("name", "by"), _ALL_WRITERS)
def test_all_verdict_writers_produce_valid_invariants(name: str, by: VerifiedBy | None) -> None:
    """Every verdict writer produces findings that satisfy verdict invariants."""
    f_inv = Finding(title=f"Finding for {name}", location="main.py:1")
    f_inv = apply_verdict(f_inv, "INVALIDATED", by=by, reason="Deterministic check triggered")

    assert (f_inv.status, f_inv.reportable, f_inv.verified, f_inv.mitigated, f_inv.verified_by) == (
        "INVALIDATED",
        False,
        False,
        False,
        by,
    )
    assert_verdict_invariants([f_inv])


def test_verdict_invariants_enforcement_raises() -> None:
    """assert_verdict_invariants raises on invariant breaches."""
    bad_inv_rep = Finding(title="f1", location="a.py:1", status="INVALIDATED", reportable=True)
    with pytest.raises(AssertionError, match="neither reportable nor verified"):
        assert_verdict_invariants([bad_inv_rep])

    bad_inv_ver = Finding(
        title="f2", location="a.py:1", status="INVALIDATED", reportable=False, verified=True
    )
    with pytest.raises(AssertionError, match="neither reportable nor verified"):
        assert_verdict_invariants([bad_inv_ver])

    bad_ver_noby = Finding(title="f3", location="a.py:1", status="VERIFIED", verified=True)
    with pytest.raises(AssertionError, match="requires non-empty verified_by"):
        assert_verdict_invariants([bad_ver_noby])

    bad_ver_false = Finding(
        title="f4", location="a.py:1", status="VERIFIED", verified=False, verified_by="llm"
    )
    with pytest.raises(AssertionError, match="must have verified=True"):
        assert_verdict_invariants([bad_ver_false])

    bad_unver_ver = Finding(title="f5", location="a.py:1", status="UNVERIFIED", verified=True)
    with pytest.raises(AssertionError, match="must have verified=False"):
        assert_verdict_invariants([bad_unver_ver])

    bad_unver_by = Finding(
        title="f6", location="a.py:1", status="UNVERIFIED", verified=False, verified_by="llm"
    )
    with pytest.raises(AssertionError, match="must have verified_by=None"):
        assert_verdict_invariants([bad_unver_by])

    bad_mit_rep = Finding(title="f7", location="a.py:1", status="MITIGATED", reportable=False)
    with pytest.raises(AssertionError, match="must stay reportable"):
        assert_verdict_invariants([bad_mit_rep])


@pytest.mark.parametrize(
    ("base", "other", "verified_by"),
    [
        (("VERIFIED", "llm"), ("VERIFIED", "human"), "llm"),
        (("UNVERIFIED", None), ("VERIFIED", "llm"), "llm"),
        (("INVALIDATED", "deterministic:syntax_error"), ("VERIFIED", "llm"), "llm"),
        (("VERIFIED", None), ("VERIFIED", None), None),
    ],
    ids=["both-verified", "one-verified", "verified-over-invalidated", "no-adjudicator"],
)
def test_a_merge_keeps_the_adjudicator_of_the_verified_input(
    base: tuple[str, str | None], other: tuple[str, str | None], verified_by: str | None
) -> None:
    """Merging duplicates into a VERIFIED finding keeps the adjudicator of a verified input. It
    never names `criteria`, which settles no VERIFIED verdict, nor the adjudicator of an input
    that was not verified (#1043)."""

    def finding(status: str, by: str | None) -> Finding:
        return Finding(
            title="Shell command built from input",
            location="app.py:2",
            status=status,
            verified=status == "VERIFIED",
            reportable=status != "INVALIDATED",
            verified_by=by,
        )

    merged = _merge_two_findings(finding(*base), finding(*other))

    assert (merged.status, merged.verified_by) == ("VERIFIED", verified_by)


def test_compute_verdict_distributions_citation_rates() -> None:
    """compute_verdict_distributions computes per-adjudicator citation rates."""
    f1 = SavedFinding(
        id=1,
        title="F1",
        location="a.py:1",
        status="INVALIDATED",
        reportable=False,
        verified=False,
        verified_by="llm",
        citation_line=10,
    )
    f2 = SavedFinding(
        id=2,
        title="F2",
        location="a.py:2",
        status="INVALIDATED",
        reportable=False,
        verified=False,
        verified_by="llm",
        citation_line=None,
    )
    f3 = SavedFinding(
        id=3,
        title="F3",
        location="a.py:3",
        status="VERIFIED",
        reportable=True,
        verified=True,
        verified_by="criteria",
        citation_line=5,
    )

    dists = compute_verdict_distributions([f1, f2, f3])
    assert dists["citation_rates"] == {
        "llm": 0.5,
        "criteria": 1.0,
    }


def test_review_verify_cli_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """devops review verify enforces invariants across all 4 target statuses."""
    reviews_dir = tmp_path / "reviews"
    session_dir = reviews_dir / "test-session"
    session_dir.mkdir(parents=True)

    findings_file = session_dir / "findings.json"
    initial_findings = [
        SavedFinding(
            id=1,
            title="Finding 1",
            location="main.py:10",
            status="UNVERIFIED",
            reportable=True,
            verified=False,
        )
    ]
    payload = ReviewSessionPayload(
        generated_at="2026-09-24T00:00:00",
        personas=["devsecops"],
        findings=initial_findings,
    )
    findings_file.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

    monkeypatch.setattr(
        "devops_cli.commands.review._find_session_dir",
        lambda _: session_dir,
    )

    # 1. verify --status UNVERIFIED
    res = runner.invoke(app, ["verify", "test-session", "-i", "1", "--status", "UNVERIFIED"])
    assert res.exit_code == 0
    p_unver = ReviewSessionPayload.model_validate_json(findings_file.read_text(encoding="utf-8"))
    f_unver = p_unver.findings[0]
    assert (f_unver.status, f_unver.reportable, f_unver.verified, f_unver.verified_by) == (
        "UNVERIFIED",
        True,
        False,
        None,
    )

    # 2. verify --status VERIFIED
    res = runner.invoke(app, ["verify", "test-session", "-i", "1", "--status", "VERIFIED"])
    assert res.exit_code == 0
    p_ver = ReviewSessionPayload.model_validate_json(findings_file.read_text(encoding="utf-8"))
    f_ver = p_ver.findings[0]
    assert (f_ver.status, f_ver.reportable, f_ver.verified, f_ver.verified_by) == (
        "VERIFIED",
        True,
        True,
        "human",
    )

    # 3. verify --status INVALIDATED
    res = runner.invoke(
        app,
        ["verify", "test-session", "-i", "1", "--status", "INVALIDATED", "-r", "False alarm"],
    )
    assert res.exit_code == 0
    p_inv = ReviewSessionPayload.model_validate_json(findings_file.read_text(encoding="utf-8"))
    f_inv = p_inv.findings[0]
    assert (f_inv.status, f_inv.reportable, f_inv.verified, f_inv.verified_by) == (
        "INVALIDATED",
        False,
        False,
        "human",
    )

    # 4. verify --status MITIGATED
    res = runner.invoke(
        app,
        ["verify", "test-session", "-i", "1", "--status", "MITIGATED", "-r", "Bounded upstream"],
    )
    assert res.exit_code == 0
    p_mit = ReviewSessionPayload.model_validate_json(findings_file.read_text(encoding="utf-8"))
    f_mit = p_mit.findings[0]
    assert (f_mit.status, f_mit.reportable, f_mit.verified, f_mit.mitigated, f_mit.verified_by) == (
        "MITIGATED",
        True,
        False,
        True,
        "human",
    )


def test_mcp_review_findings_passes_status_for_all_four_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MCP review_findings passes --status for all four states."""
    invocations: list[list[str]] = []

    def mock_run_mcp_cmd(cmd: list[str], timeout: int = 15) -> str:
        invocations.append(cmd)
        return "OK"

    monkeypatch.setattr("devops_cli.ai.mcp.server._run_mcp_cmd", mock_run_mcp_cmd)

    for st in ("VERIFIED", "UNVERIFIED", "INVALIDATED", "MITIGATED"):
        res = review_findings(session_id="sess-1", status=st)
        assert res == "OK"

    assert [cmd[-2:] for cmd in invocations] == [
        ["--status", "VERIFIED"],
        ["--status", "UNVERIFIED"],
        ["--status", "INVALIDATED"],
        ["--status", "MITIGATED"],
    ]


def test_reset_clears_every_verdict_field_a_reviewer_could_write() -> None:
    """A reviewer's reply cannot carry its own confidence, citation, mitigation or criteria results."""
    from devops_cli.ai.review_schema import reset_verification_state

    written = Finding(
        title="Self-judged",
        location="a.py:1",
        confidence_score=2.0,
        citation_line=1,
        mitigating_mechanism="A guard upstream",
        perimeter_files=["b.py"],
        regression_test="tests/test_a.py",
        criteria_execution_results=[CriterionExecutionResult(command="true", passed=True)],
    )

    cleared = reset_verification_state(written)

    assert (
        cleared.confidence_score,
        cleared.citation_line,
        cleared.mitigating_mechanism,
        cleared.perimeter_files,
        cleared.regression_test,
        cleared.criteria_execution_results,
    ) == (None, None, None, [], None, [])


@pytest.mark.parametrize(("given", "stored"), [(2.0, 1.0), (-0.5, 0.0), (0.4, 0.4)])
def test_a_verdict_stores_confidence_within_zero_and_one(given: float, stored: float) -> None:
    """Three findings in session 20261001-224227 carried a confidence of 2.0."""
    judged = apply_verdict(
        Finding(title="t", location="a.py:1"), "VERIFIED", by="human", confidence_score=given
    )

    assert judged.confidence_score == stored


@pytest.mark.parametrize("by", ["human", "deterministic:dry_run"])
def test_a_mitigated_finding_is_not_a_verified_one(by: str) -> None:
    """Eleven of session 20261001-224227's mitigations carried verified=True."""
    judged = apply_verdict(
        Finding(title="t", location="a.py:1"),
        "MITIGATED",
        by=by,
        reason="r",
        mitigating_mechanism="m",
        perimeter_files=["a.py"],
    )

    assert (judged.status, judged.verified, judged.mitigated, judged.reportable) == (
        "MITIGATED",
        False,
        True,
        True,
    )


def test_unverified_note_counts_includes_contradiction() -> None:
    """Verify _unverified_note_counts tallies verifier-contradiction both standalone and with details."""
    from devops_cli.ai.review_schema import _unverified_note_counts
    from devops_cli.config.constants import CONST_VERIFIER_CONTRADICTION

    findings = [
        Finding(
            title="f1",
            location="a.py:1",
            status="UNVERIFIED",
            verification_note=CONST_VERIFIER_CONTRADICTION,
        ),
        Finding(
            title="f2",
            location="b.py:2",
            status="UNVERIFIED",
            verification_note=f"{CONST_VERIFIER_CONTRADICTION}: reason denies claim",
        ),
        Finding(title="f3", location="c.py:3", status="VERIFIED", verified=True, verified_by="llm"),
    ]
    counts = _unverified_note_counts(findings)
    assert counts == {CONST_VERIFIER_CONTRADICTION: 2}


def test_invalidated_cannot_have_mitigated_true() -> None:
    f = Finding(
        title="Hallucinated issue",
        location="src/mod.py:1",
        severity="LOW",
        status="INVALIDATED",
        verified=False,
        reportable=False,
        mitigated=True,
    )
    with pytest.raises(AssertionError, match="cannot have mitigated=True"):
        assert_verdict_invariants([f])


def test_apply_verdict_mitigated_fields() -> None:
    f = Finding(
        title="Flaky timeout",
        location="src/client.py:100",
        severity="MEDIUM",
        status="UNVERIFIED",
    )
    updated = apply_verdict(
        f,
        "MITIGATED",
        by="human",
        reason="Exponential backoff added",
        mitigating_mechanism="ExponentialBackoff",
    )

    assert (
        updated.status,
        updated.reportable,
        updated.mitigated,
        updated.verified_by,
        updated.mitigating_mechanism,
    ) == ("MITIGATED", True, True, "human", "ExponentialBackoff")
