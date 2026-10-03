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
    _merge_two_findings,
    compute_verdict_distributions,
)
from devops_cli.commands.review import app

runner = CliRunner()

_ALL_WRITERS: list[tuple[str, VerifiedBy | None]] = [
    ("criteria", "criteria"),
    ("llm", "llm"),
    ("debate", "debate"),
    ("human", "human"),
    ("agent", "agent"),
    ("syntax_error", "deterministic:syntax_error"),
    ("missing_symbol", "deterministic:missing_symbol"),
    ("missing_header", "deterministic:missing_header"),
    ("pathlib_resolve", "deterministic:pathlib_resolve"),
    ("scanned_clean", "deterministic:scanned_clean_dependency"),
    ("placeholder", "deterministic:placeholder_advisory"),
    ("unbacked_advisory", "deterministic:unbacked_advisory"),
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


def test_criteria_execution_verdict_finality(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A finding a passing verification criterion supports is not final: the verifier is shown
    it and its verdict applies, with the criterion still recorded as matched (#1043). Only a
    criteria INVALIDATED verdict is final."""
    monkeypatch.setattr(
        "devops_cli.ai.review.verification._collect_rag_verification_blocks", lambda _: []
    )
    py_file = tmp_path / "app.py"
    py_file.write_text("def test_func():\n    pass\n", encoding="utf-8")

    command = "python -c 'from app import test_func; assert test_func() is None'"
    crit = VerificationCriterion(
        description="test_func returns nothing", command=command, executable=True
    )
    f_crit = Finding(
        title="test_func returns None instead of a result",
        location=f"{py_file.name}:1",
        verification_criteria=[crit],
    )

    res_finding = execute_finding_criteria(f_crit, repo_root=tmp_path)
    assert (
        res_finding.status,
        res_finding.verified_by,
        res_finding.confidence_score,
        res_finding.verified_criteria_matched,
    ) == ("UNVERIFIED", None, None, [command])

    mock_client = MagicMock()
    mock_client.chat.return_value = json.dumps(
        [
            {
                "finding_id": 1,
                "status": "VERIFIED",
                "verified": True,
                "confidence_score": 0.8,
                "reason": "test_func at line 1 has no return statement, so it returns None.",
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
    assert (
        mock_client.chat.call_count,
        f_crit.title in mock_client.chat.call_args.kwargs["user"],
        (final_f.status, final_f.verified, final_f.verified_by, final_f.confidence_score),
        final_f.verified_criteria_matched,
    ) == (1, True, ("VERIFIED", True, "llm", 0.8), [command])


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
    ) == ("UNVERIFIED", True, False, True)

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


def test_reset_clears_every_verdict_field_a_reviewer_could_write() -> None:
    """A reviewer's reply cannot carry its own confidence, citation, mitigation or criteria results."""
    from devops_cli.ai.review_schema import CriterionExecutionResult, reset_verification_state

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
        Finding(title="t", location="a.py:1"), "VERIFIED", by="criteria", confidence_score=given
    )

    assert judged.confidence_score == stored


def test_verdict_fields_hold_every_field_a_verdict_writes() -> None:
    """`VERDICT_FIELDS` names each field `apply_verdict` writes, whatever the status."""
    from devops_cli.ai.review.verdicts import VERDICT_FIELDS

    written: set[str] = set()
    for status in ("VERIFIED", "INVALIDATED", "MITIGATED", "UNVERIFIED"):
        before = Finding(title="t", location="a.py:1", status="INVALIDATED", reportable=False)
        after = apply_verdict(
            before.model_copy(),
            status,
            by="llm",
            reason="r",
            citation_line=1,
            mitigating_mechanism="m",
            perimeter_files=["a.py"],
            regression_test="tests/test_a.py",
            verification_note="n",
            confidence_score=0.5,
        )
        written |= {
            name for name in Finding.model_fields if getattr(after, name) != getattr(before, name)
        }

    assert (
        sorted(written - set(VERDICT_FIELDS)),
        len(VERDICT_FIELDS) == len(set(VERDICT_FIELDS)),
    ) == (
        [],
        True,
    )


def test_the_verification_copy_back_keeps_everything_the_verifier_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The saved finding takes the verifier's severity, location and verdict, not only its status."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator

    def fake_validate(
        result: ReviewResult, all_segments: list[str], client: object, **_: object
    ) -> object:
        judged = apply_verdict(
            result.findings[0],
            "VERIFIED",
            by="llm",
            citation_line=4,
            confidence_score=0.7,
            severity="LOW",
            location="src/app.py:4",
            relocated_from="src/app.py:3",
        )
        return result.model_copy(update={"findings": [judged]}), 0.1, "backend"

    monkeypatch.setattr("devops_cli.ai.review.pipeline._validate_segment_findings", fake_validate)
    orchestrator = ReviewPipelineOrchestrator(
        session_dir=tmp_path / "session",
        target_dir=tmp_path,
        llm_client=MagicMock(),
        verification_client=MagicMock(),
    )
    payload = FileReviewPayload(
        file_path="src/app.py",
        findings=[
            SavedFinding(
                severity="HIGH",
                location="src/app.py:3",
                title="Unchecked input",
                persona="devsecops",
            )
        ],
    )

    orchestrator._verify_single_file_payload(1, 1, payload, "server")
    saved = payload.findings[0]

    assert (
        saved.status,
        saved.severity,
        saved.location,
        saved.relocated_from,
        saved.citation_line,
        saved.confidence_score,
        saved.verified_by,
        saved.persona,
    ) == ("VERIFIED", "LOW", "src/app.py:4", "src/app.py:3", 4, 0.7, "llm", "devsecops")


def _raise_sandbox_unavailable(*_: object, **__: object) -> None:
    raise OSError("sandbox unavailable")


@pytest.mark.parametrize(
    ("patched", "parallel"),
    [
        (
            "devops_cli.ai.review.verification._run_deterministic_pre_verification_on_findings",
            False,
        ),
        (
            "devops_cli.ai.review.pipeline.ReviewPipelineOrchestrator._safe_verify_file_payload",
            False,
        ),
        (
            "devops_cli.ai.review.pipeline.ReviewPipelineOrchestrator._safe_verify_file_payload",
            True,
        ),
    ],
    ids=["verification-raised", "serial-worker-raised", "parallel-worker-raised"],
)
def test_a_file_whose_verification_raised_says_why_its_findings_have_no_verdict(
    patched: str, parallel: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The findings of an errored file are still reported, so each unverified one says why; a
    note or verdict verification already wrote stays."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator

    monkeypatch.setattr(patched, _raise_sandbox_unavailable)
    orchestrator = ReviewPipelineOrchestrator(
        session_dir=tmp_path / "session",
        target_dir=tmp_path,
        llm_client=MagicMock(),
        verification_client=MagicMock(),
        concurrency=2,
        parallel=parallel,
    )
    payloads = [
        FileReviewPayload(
            file_path=path,
            findings=[
                SavedFinding(severity="HIGH", location=f"{path}:3", title="Unchecked input"),
                SavedFinding(
                    severity="HIGH",
                    location=f"{path}:5",
                    title="Unbounded read",
                    verification_note="verifier-no-verdict",
                ),
                apply_verdict(
                    SavedFinding(severity="LOW", location=f"{path}:7", title="Weak hash"),
                    "VERIFIED",
                    by="llm",
                    confidence_score=0.8,
                ),
            ],
        )
        for path in ("src/a.py", "src/b.py")
    ]

    orchestrator.execute_finding_verification(payloads)
    reported = orchestrator._collect_and_deduplicate_findings(payloads)

    assert (
        sorted(orchestrator.errored_files),
        [(f.status, f.verification_note) for p in payloads for f in p.findings],
        len(reported),
        compute_verdict_distributions(reported)["verification_note"],
    ) == (
        ["src/a.py", "src/b.py"],
        [
            ("UNVERIFIED", "verification-unavailable: OSError"),
            ("UNVERIFIED", "verifier-no-verdict"),
            ("VERIFIED", None),
        ]
        * 2,
        6,
        {"verification-unavailable": 2, "verifier-no-verdict": 2},
    )
