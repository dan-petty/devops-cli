"""Tests for verdict writers, invariant assertions, citation checks, and executed verdict finality."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp.server import review_findings
from devops_cli.ai.review.review_environment import execute_finding_criteria
from devops_cli.ai.review.stages.adversarial_debate import run_adversarial_debate_stage
from devops_cli.ai.review.verdicts import (
    VerifiedBy,
    apply_verdict,
    assert_verdict_invariants,
)
from devops_cli.ai.review.verification import (
    _apply_single_finding_verification,
    _validate_segment_findings,
)
from devops_cli.ai.review_schema import (
    FileReviewPayload,
    Finding,
    ReviewResult,
    ReviewSessionPayload,
    SavedFinding,
    VerificationCriterion,
    compute_verdict_distributions,
)
from devops_cli.commands.review import app

runner = CliRunner()

_ALL_WRITERS: list[tuple[str, VerifiedBy | None]] = [
    ("criteria", "criteria"),
    ("llm", "llm"),
    ("debate", "debate"),
    ("human", "human"),
    ("syntax_error", "deterministic:syntax_error"),
    ("missing_symbol", "deterministic:missing_symbol"),
    ("missing_header", "deterministic:missing_header"),
    ("pathlib_resolve", "deterministic:pathlib_resolve"),
    ("scanned_clean", "deterministic:scanned_clean_dependency"),
    ("placeholder", "deterministic:placeholder_advisory"),
    ("unsupported_runtime", "deterministic:unsupported_runtime"),
    ("operational_protocol", "deterministic:operational_protocol"),
    ("fixture_cred", "deterministic:test_fixture_credential"),
    ("uninit_var", "deterministic:uninitialized_variable"),
    ("monologue", "deterministic:conversational_monologue"),
    ("compliment", "deterministic:benign_compliment"),
    ("masked_syntax", "deterministic:masked_placeholder_syntax_error"),
    ("none_deref", "deterministic:none_dereference"),
    ("catalog", "deterministic:catalog_hallucination"),
    ("polarity", "deterministic:verdict_polarity"),
    ("construct_loc", "deterministic:construct_location"),
    ("line_bounds", "deterministic:line_boundaries"),
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


def test_criteria_execution_verdict_finality(tmp_path: Path) -> None:
    """Findings verified by criteria are not re-sent to the model or overwritten."""
    py_file = tmp_path / "app.py"
    py_file.write_text("def test_func():\n    pass\n", encoding="utf-8")

    crit = VerificationCriterion(
        description="Check function exists",
        command="python -c 'print(1)'",
        executable=True,
    )
    f_crit = Finding(
        title="Missing function",
        location=f"{py_file.name}:1",
        verification_criteria=[crit],
    )

    res_finding = execute_finding_criteria(f_crit, repo_root=tmp_path)
    assert (res_finding.status, res_finding.verified, res_finding.verified_by) == (
        "VERIFIED",
        True,
        "criteria",
    )

    mock_client = MagicMock()
    mock_client.chat.return_value = json.dumps(
        [
            {
                "finding_id": 1,
                "status": "INVALIDATED",
                "reason": "Overwriting claim",
            }
        ]
    )

    rev_res = ReviewResult(findings=[res_finding])
    validated_res, _, _ = _validate_segment_findings(
        result=rev_res,
        all_segments=["def test_func(): pass"],
        client=mock_client,
        repo_root=tmp_path,
    )

    final_f = validated_res.findings[0]
    assert (final_f.status, final_f.verified, final_f.verified_by) == (
        "VERIFIED",
        True,
        "criteria",
    )
    mock_client.chat.assert_not_called()


def test_adversarial_debate_verdict_invariants() -> None:
    """Debate invalidation produces findings satisfying invariants."""
    f = SavedFinding(
        id=1,
        persona="devsecops",
        title="Unverified stylistic bikeshedding",
        description="Stylistic issue with whitespace",
        location="a.py:1",
    )

    payload = FileReviewPayload(file_path="a.py", findings=[f])
    invalidated_count = run_adversarial_debate_stage([payload])

    assert (invalidated_count, f.status, f.reportable, f.verified, f.verified_by) == (
        1,
        "INVALIDATED",
        False,
        False,
        "debate",
    )
    assert_verdict_invariants([f])


def test_citation_line_validation_downgrade(tmp_path: Path) -> None:
    """Refutations missing or with out-of-range cited lines downgrade to UNVERIFIED."""
    code_file = tmp_path / "service.py"
    code_file.write_text("x = 10\ny = 20\ndef calculate():\n    return x + y\n", encoding="utf-8")

    f = Finding(
        title="Undefined function `calculate`",
        description="Function `calculate` is not defined",
        location=f"{code_file}:3",
        severity="HIGH",
    )

    # Case 1: Missing citation line
    item_no_line = {"status": "INVALIDATED", "reason": "Function exists"}
    res_no_line = _apply_single_finding_verification(
        f, item_no_line, "2026-09-24T00:00:00", repo_root=tmp_path
    )
    assert (
        res_no_line.status,
        res_no_line.reportable,
        res_no_line.verified,
        res_no_line.verified_by,
        "missing cited line" in (res_no_line.verification_note or ""),
    ) == ("UNVERIFIED", True, False, None, True)

    # Case 2: Out-of-range negative/zero line
    item_zero = {"status": "INVALIDATED", "citation_line": 0, "reason": "Check at line 0"}
    res_zero = _apply_single_finding_verification(
        f, item_zero, "2026-09-24T00:00:00", repo_root=tmp_path
    )
    assert (res_zero.status, "out of range" in (res_zero.verification_note or "")) == (
        "UNVERIFIED",
        True,
    )

    # Case 3: Exceeds file length
    item_exceeds = {"status": "INVALIDATED", "citation_line": 999, "reason": "At line 999"}
    res_exceeds = _apply_single_finding_verification(
        f, item_exceeds, "2026-09-24T00:00:00", repo_root=tmp_path
    )
    assert (res_exceeds.status, "exceeds file length" in (res_exceeds.verification_note or "")) == (
        "UNVERIFIED",
        True,
    )

    # Case 4: Cited line does not contain construct tokens
    item_wrong_line = {
        "status": "INVALIDATED",
        "citation_line": 1,
        "reason": "Check at line 1",
    }
    res_wrong_line = _apply_single_finding_verification(
        f, item_wrong_line, "2026-09-24T00:00:00", repo_root=tmp_path
    )
    assert (
        res_wrong_line.status,
        "does not contain cited construct tokens" in (res_wrong_line.verification_note or ""),
    ) == ("UNVERIFIED", True)

    # Case 5: Valid citation line matching tokens
    item_valid = {
        "status": "INVALIDATED",
        "citation_line": 3,
        "reason": "Not undefined; function calculate is defined at line 3",
    }

    res_valid = _apply_single_finding_verification(
        f, item_valid, "2026-09-24T00:00:00", repo_root=tmp_path
    )
    assert (
        res_valid.status,
        res_valid.reportable,
        res_valid.verified,
        res_valid.verified_by,
        res_valid.citation_line,
    ) == ("INVALIDATED", False, False, "llm", 3)


def test_mitigating_mechanism_annotation() -> None:
    """Mitigated verdicts without mechanism degrade to UNVERIFIED with notes."""
    f = Finding(title="Unbounded queue", location="q.py:10", severity="MEDIUM")

    item_no_mech = {"status": "MITIGATED", "reason": "Bounded elsewhere"}
    res_no_mech = _apply_single_finding_verification(f, item_no_mech, "now")
    assert (
        res_no_mech.status,
        res_no_mech.reportable,
        res_no_mech.mitigated,
        "without specified mitigating mechanism" in (res_no_mech.verification_note or ""),
    ) == ("UNVERIFIED", False, False, True)

    item_with_mech = {
        "status": "MITIGATED",
        "mitigating_mechanism": "BoundedSemaphore(10)",
        "perimeter_files": ["q.py"],
        "citation_line": 15,
        "reason": "Bounded by semaphore",
    }
    res_with_mech = _apply_single_finding_verification(f, item_with_mech, "now")
    assert (
        res_with_mech.status,
        res_with_mech.reportable,
        res_with_mech.mitigated,
        res_with_mech.mitigating_mechanism,
        res_with_mech.citation_line,
    ) == ("MITIGATED", True, True, "BoundedSemaphore(10)", 15)


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
        True,
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
