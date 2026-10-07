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
    CriterionExecutionResult,
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


@pytest.mark.bwrap
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


def test_mitigating_mechanism_annotation(tmp_path: Path) -> None:
    """Mitigated verdicts without mechanism degrade to UNVERIFIED with notes."""
    (tmp_path / "q.py").write_text("LIMIT = BoundedSemaphore(10)\n", encoding="utf-8")
    f = Finding(title="Unbounded queue", location="q.py:10", severity="MEDIUM")

    item_no_mech = {"status": "MITIGATED", "reason": "Bounded elsewhere"}
    res_no_mech = _apply_single_finding_verification(f, item_no_mech, "now", repo_root=tmp_path)
    assert (
        res_no_mech.status,
        res_no_mech.reportable,
        res_no_mech.mitigated,
        res_no_mech.verification_note,
    ) == ("UNVERIFIED", True, False, "mitigation-unproven: no mitigating mechanism named")

    item_with_mech = {
        "status": "MITIGATED",
        "mitigating_mechanism": "`BoundedSemaphore(10)`",
        "perimeter_files": ["q.py"],
        "citation_line": 15,
        "reason": "Bounded by semaphore",
    }
    res_with_mech = _apply_single_finding_verification(f, item_with_mech, "now", repo_root=tmp_path)
    assert (
        res_with_mech.status,
        res_with_mech.reportable,
        res_with_mech.mitigated,
        res_with_mech.mitigating_mechanism,
        res_with_mech.citation_line,
    ) == ("MITIGATED", True, True, "`BoundedSemaphore(10)`", 15)


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


# ── Verdicts point at evidence the reviewed tree holds (#845) ────────────────────────────────

# The probe of #845: a four-line file whose command injection a verifier called mitigated by a
# wrapper in a file that does not exist, citing line 999.
_SHELL_SOURCE = "import os\n\ndef run(cmd):\n    os.system(cmd)\n"
_SAFE_EXEC_SOURCE = (
    "import shlex\n\n\ndef safe_exec(argv):\n    return ' '.join(shlex.quote(a) for a in argv)\n"
)


@pytest.fixture
def reviewed_tree(tmp_path: Path) -> Path:
    """A reviewed tree: the finding's file, a real wrapper, a conventions file and a workflow,
    with a file beside the tree that a `../` path reaches."""
    root = tmp_path / "project"
    for rel, source in {
        "app/shell.py": _SHELL_SOURCE,
        "app/safe.py": _SAFE_EXEC_SOURCE,
        ".devops/review.md": "Commands go through `safe_exec`.\n",
        ".github/workflows/ci.yml": "permissions:\n  contents: read\n",
    }.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(source, encoding="utf-8")
    (tmp_path / "outside.py").write_text(_SAFE_EXEC_SOURCE, encoding="utf-8")
    return root


def _injection() -> Finding:
    return Finding(
        title="Command injection via os.system",
        description="`run` passes `cmd` to `os.system` unquoted.",
        location="app/shell.py:4",
        severity="HIGH",
    )


def _mitigation(mechanism: str, *perimeter: str) -> dict[str, object]:
    return {
        "status": "MITIGATED",
        "mitigated": True,
        "reason": "Every command goes through a quoting wrapper.",
        "mitigating_mechanism": mechanism,
        "perimeter_files": list(perimeter),
        "citation_line": 4,
    }


# A model's confirmation of `_injection`, citing the line that holds the defect.
_CONFIRMATION: dict[str, object] = {
    "status": "VERIFIED",
    "verified": True,
    "reason": "Line 4 passes the unquoted `cmd` argument to os.system.",
    "citation_line": 4,
}


def _judged(
    verdict: dict[str, object], root: Path | None, finding: Finding | None = None
) -> Finding:
    judged = _apply_single_finding_verification(
        finding or _injection(), verdict, "2026-10-03T00:00:00", repo_root=root
    )
    assert_verdict_invariants([judged])
    return judged


def _note_kind(f: Finding) -> str:
    return (f.verification_note or "").split(":", 1)[0]


def test_the_probe_fabricated_mitigation_stays_in_the_report(reviewed_tree: Path) -> None:
    """The #845 probe gave MITIGATED, verified_by=llm, no note and APPROVE."""
    from devops_cli.ai.review_schema import derive_recommendation

    verdict = _mitigation("shlex.quote wrapper in safe_exec", "src/does/not/exist.py")
    judged = _judged({**verdict, "citation_line": 999}, reviewed_tree)

    assert (
        judged.status,
        judged.reportable,
        judged.verified_by,
        judged.mitigated,
        judged.citation_line,
        _note_kind(judged),
        "src/does/not/exist.py" in (judged.verification_note or ""),
        derive_recommendation([judged]),
    ) == ("UNVERIFIED", True, None, False, None, "mitigation-unproven", True, "REQUEST CHANGES")


@pytest.mark.parametrize(
    ("mechanism", "perimeter"),
    [
        ("shlex.quote wrapper in safe_exec", "app/safe.py"),
        # The identifier may sit in the finding's own file rather than the perimeter.
        ("`cmd` comes from a fixed allowlist", "app/safe.py"),
        # A `.github/...` perimeter keeps its leading dot and resolves to itself.
        ("The workflow sets `contents: read`", ".github/workflows/ci.yml"),
    ],
    ids=["in-perimeter", "in-finding-file", "dot-github"],
)
def test_a_mitigation_whose_perimeter_exists_and_holds_the_mechanism_stays_mitigated(
    mechanism: str, perimeter: str, reviewed_tree: Path
) -> None:
    """A mitigation that points at code the tree holds is MITIGATED, reported and not verified."""
    judged = _judged(_mitigation(mechanism, perimeter), reviewed_tree)

    assert (
        judged.status,
        judged.reportable,
        judged.mitigated,
        judged.verified,
        judged.verified_by,
        judged.perimeter_files,
        judged.verification_note,
    ) == ("MITIGATED", True, True, False, "llm", [perimeter], None)


@pytest.mark.parametrize(
    "perimeter",
    ["absolute", "../outside.py", "/etc/hostname", "app/missing.py", "app"],
    ids=["absolute-inside-tree", "dot-dot-escape", "absolute-outside", "missing", "directory"],
)
def test_a_perimeter_that_does_not_resolve_inside_the_reviewed_tree_is_unresolved(
    perimeter: str, reviewed_tree: Path
) -> None:
    """An absolute path, even to a file in the tree, or a `../` escape names no perimeter."""
    named = str(reviewed_tree / "app/safe.py") if perimeter == "absolute" else perimeter
    judged = _judged(_mitigation("shlex.quote wrapper in safe_exec", named), reviewed_tree)

    assert (
        judged.status,
        judged.reportable,
        _note_kind(judged),
        f"`{named}` does not resolve inside the reviewed tree" in (judged.verification_note or ""),
    ) == ("UNVERIFIED", True, "mitigation-unproven", True)


# Five mechanisms of session 20261001-224227 that describe the defect rather than a mitigation.
# The perimeter holds each one's identifiers, so only the self-negation can fail.
_SELF_NEGATING_MECHANISMS = (
    "The error is caught but not logged or re-raised",
    "Rich library's escape_text function is used for title and location but not for severity label",
    "The function already attempts to balance brackets but does not fully sanitize nested or "
    "malformed bracket sequences.",
    "_check_path_traversal function is expected to handle path traversal checks",
    "The test is intended to verify that private IP resolution raises an error, but the mock "
    "implementation is too permissive",
)


@pytest.mark.parametrize("mechanism", _SELF_NEGATING_MECHANISMS)
def test_a_mechanism_that_describes_the_defect_is_no_mitigation(
    mechanism: str, reviewed_tree: Path
) -> None:
    """Five of session 20261001-224227's 28 mitigations described the defect itself."""
    (reviewed_tree / "app/guard.py").write_text(
        "def escape_text(s): ...\ndef _check_path_traversal(p): ...\n", encoding="utf-8"
    )
    judged = _judged(_mitigation(mechanism, "app/guard.py"), reviewed_tree)

    assert (
        judged.status,
        judged.reportable,
        _note_kind(judged),
        "describes the defect" in (judged.verification_note or ""),
    ) == ("UNVERIFIED", True, "mitigation-unproven", True)


@pytest.mark.parametrize(
    ("mechanism", "perimeter", "check"),
    [
        # 18 of the session's 28 mechanisms named no code identifier.
        ("Input validation and sanitization", "app/safe.py", "names no code identifier"),
        # 2 of its perimeters were the conventions file; it holds `safe_exec` here.
        ("shlex.quote wrapper in safe_exec", ".devops/review.md", "is documentation"),
        ("`quote_all` wrapper", "app/safe.py", "none of its identifiers"),
    ],
    ids=["no-identifier", "conventions-file", "identifier-absent"],
)
def test_a_mitigation_pointing_at_no_code_that_enforces_it_is_unproven(
    mechanism: str, perimeter: str, check: str, reviewed_tree: Path
) -> None:
    """The note names the check that failed."""
    judged = _judged(_mitigation(mechanism, perimeter), reviewed_tree)

    assert (
        judged.status,
        judged.reportable,
        _note_kind(judged),
        check in (judged.verification_note or ""),
    ) == ("UNVERIFIED", True, "mitigation-unproven", True)


@pytest.mark.parametrize(
    ("citation", "expected"),
    [
        (999, ("UNVERIFIED", None, "citation-out-of-range", True)),
        (0, ("UNVERIFIED", None, "citation-out-of-range", True)),
        (4, ("VERIFIED", "llm", "", True)),
        (None, ("VERIFIED", "llm", "", True)),
    ],
    ids=["past-the-end", "line-zero", "in-range", "no-citation"],
)
def test_a_confirmation_citing_a_line_outside_the_file_is_unverified(
    citation: int | None, expected: tuple[str, str | None, str, bool], reviewed_tree: Path
) -> None:
    """A model VERIFIED verdict citing line 999 of a four-line file passed unchecked."""
    verdict = {"status": "VERIFIED", "verified": True, "reason": "os.system(cmd) on line 4."}
    judged = _judged({**verdict, "citation_line": citation}, reviewed_tree)

    assert (
        judged.status,
        judged.verified_by,
        _note_kind(judged),
        judged.reportable,
    ) == expected


@pytest.mark.parametrize(
    ("located", "verdict", "expected"),
    [
        (
            "in-tree",
            {**_CONFIRMATION, "citation_line": 999},
            ("UNVERIFIED", None, "citation-out-of-range: line 999 of `{path}` (4 lines)"),
        ),
        (
            "in-tree",
            _mitigation("`cmd` comes from a fixed allowlist", "app/safe.py"),
            ("MITIGATED", 4, None),
        ),
        # A file outside the reviewed tree is not read: the confirmation is left as it was.
        ("outside", {**_CONFIRMATION, "citation_line": 999}, ("VERIFIED", 999, None)),
    ],
    ids=["past-the-end", "identifier-in-finding-file", "outside-the-tree"],
)
def test_a_finding_located_by_an_absolute_path_is_read_from_the_reviewed_tree(
    located: str,
    verdict: dict[str, object],
    expected: tuple[str, int | None, str | None],
    reviewed_tree: Path,
) -> None:
    """A scanner writes its finding's location absolute; the checks read that file as they read a
    relative one, and refuse only a file outside the tree."""
    path = (
        reviewed_tree / "app/shell.py"
        if located == "in-tree"
        else reviewed_tree.parent / "outside.py"
    ).resolve()
    finding = _injection().model_copy(update={"location": f"{path}:4"})

    judged = _judged(verdict, reviewed_tree, finding)

    status, citation, note = expected
    assert (judged.status, judged.citation_line, judged.verification_note) == (
        status,
        citation,
        note.format(path=path) if note else None,
    )


# Reasons that deny the claim they confirm or mitigate: the session 20261003-012555 confirmation
# of a Semgrep finding (cache llm_6818ef36), and the same denial of `_injection`'s claim.
_IMPORT_CLAIM = Finding(
    title="[python.lang.security.audit.non-literal-import.non-literal-import] Untrusted user "
    "input in `importlib.import_module()` function allows an attacker",
    location="app/shell.py:4",
    severity="MEDIUM",
)


@pytest.mark.parametrize(
    ("finding", "verdict", "denial"),
    [
        (
            _IMPORT_CLAIM,
            {
                **_CONFIRMATION,
                "reason": "The mapping is hardcoded. No user input reaches this point.",
            },
            "no user input",
        ),
        (
            _IMPORT_CLAIM,
            {**_CONFIRMATION, "reason": "These are not derived from untrusted user input."},
            "not derived from untrusted user input",
        ),
        # A mitigation whose perimeter holds its mechanism, but whose reason argues the defect
        # away.
        (
            None,
            {
                **_mitigation("shlex.quote wrapper in safe_exec", "app/safe.py"),
                "reason": "No command injection is possible: every command goes through safe_exec.",
            },
            "no command injection",
        ),
    ],
    ids=["verified-no-user-input", "verified-not-derived-from", "mitigated-provable"],
)
def test_a_verdict_whose_reason_denies_the_claim_is_not_applied(
    finding: Finding | None, verdict: dict[str, object], denial: str, reviewed_tree: Path
) -> None:
    """The mirror of a self-refutation: a confirmation or mitigation whose own reason denies the
    claim leaves the finding unverified and reported, with the denial in its note."""
    judged = _judged(verdict, reviewed_tree, finding)

    assert (
        judged.status,
        judged.reportable,
        judged.verified_by,
        judged.citation_line,
        judged.mitigated,
        _note_kind(judged),
        f"denies the claim ('{denial}')" in (judged.verification_note or ""),
    ) == ("UNVERIFIED", True, None, None, False, "verifier-contradiction", True)


def _criterion_run(passed: bool) -> CriterionExecutionResult:
    return CriterionExecutionResult(
        command="python -c 'import app.shell'",
        executable=True,
        exit_code=0 if passed else 1,
        passed=passed,
    )


@pytest.mark.parametrize(
    ("runs", "expected"),
    [
        ([False], ("UNVERIFIED", None, "verifier-contradiction")),
        # A criterion that passed, or none run, leaves the reason's claim standing.
        ([True], ("VERIFIED", "llm", "")),
        ([False, True], ("VERIFIED", "llm", "")),
        ([], ("VERIFIED", "llm", "")),
    ],
    ids=["failed", "passed", "one-passed", "none-run"],
)
def test_a_confirmation_saying_a_failed_criterion_passed_is_not_applied(
    runs: list[bool], expected: tuple[str, str | None, str], reviewed_tree: Path
) -> None:
    """Session 20261003-005122 confirmed a finding "by the test execution which passes" when that
    criterion had failed with `No module named 'pytest'` (cache llm_4617de34)."""
    finding = _injection().model_copy(
        update={"criteria_execution_results": [_criterion_run(passed) for passed in runs]}
    )
    reason = "Line 4 calls os.system, verified by the test execution which passes, confirming it."

    judged = _judged({**_CONFIRMATION, "reason": reason}, reviewed_tree, finding)

    assert (judged.status, judged.verified_by, _note_kind(judged)) == expected


@pytest.mark.parametrize(
    ("title", "reason"),
    [
        (
            "Command injection via os.system",
            "Line 4 passes the unquoted `cmd` argument to os.system; no shlex.quote or allowlist "
            "guards it.",
        ),
        # A negated verb: the plain mirror of the self-refutation guard (claim overlap of 0.6 and
        # any negation) set aside 318 of 778 cached confirmations and mitigations, this one too
        # (cache llm_7b99d901).
        (
            "Path Traversal Vulnerability in Custom Persona Loading",
            "`Path(persona_name).name` extracts a filename, but this does not prevent path "
            "traversal attempts like '../evil.md'.",
        ),
        # The claim negates the words the reason negates.
        (
            "Missing input validation in run",
            "run passes cmd to os.system with no input validation.",
        ),
        (
            "TLS verification disabled in the HTTP client",
            "Line 4 sets verify=False, so there is no TLS verification.",
        ),
        (
            "Command injection via os.system",
            "os.system(cmd) runs it without any quoting, and the verification command passes the "
            "shell metacharacters through.",
        ),
    ],
    ids=[
        "no-negation",
        "negated-verb",
        "claim-says-missing",
        "claim-says-disabled",
        "passes-as-a-verb",
    ],
)
def test_a_confirmation_whose_reason_supports_the_claim_is_still_applied(
    title: str, reason: str, reviewed_tree: Path
) -> None:
    """A supporting confirmation stays VERIFIED, even when its reason negates a guard; a
    criterion that failed does not make "passes the ... through" a claim that it passed."""
    finding = _injection().model_copy(
        update={"title": title, "criteria_execution_results": [_criterion_run(False)]}
    )

    judged = _judged({**_CONFIRMATION, "reason": reason}, reviewed_tree, finding)

    assert (judged.status, judged.verified_by, judged.citation_line, judged.verification_note) == (
        "VERIFIED",
        "llm",
        4,
        None,
    )


def test_one_fabricated_verdict_leaves_the_rest_of_the_reply_as_it_was(
    reviewed_tree: Path,
) -> None:
    """Checks are per verdict: the reply is read once and its valid verdicts stand."""
    findings = [
        _injection(),
        _injection().model_copy(update={"title": "Unquoted shell argument in run"}),
        _injection().model_copy(update={"title": "os.system used instead of subprocess"}),
    ]
    client = MagicMock()
    client.chat.return_value = json.dumps(
        [
            {"finding_id": 1, **_mitigation("safe_exec", "src/does/not/exist.py")},
            {"finding_id": 2, **_mitigation("shlex.quote wrapper in safe_exec", "app/safe.py")},
            {"finding_id": 3, "status": "VERIFIED", "verified": True, "citation_line": 4},
        ]
    )

    result, _, _ = _validate_segment_findings(
        ReviewResult(findings=findings), [_SHELL_SOURCE], client, repo_root=reviewed_tree
    )
    assert_verdict_invariants(result.findings)

    assert (
        [(f.status, f.reportable, _note_kind(f)) for f in result.findings],
        client.chat.call_count,
    ) == (
        [
            ("UNVERIFIED", True, "mitigation-unproven"),
            ("MITIGATED", True, ""),
            ("VERIFIED", True, ""),
        ],
        1,
    )


def test_the_verdict_distributions_count_degraded_mitigations(reviewed_tree: Path) -> None:
    """profile.json counts mitigations that pointed at no evidence, those naming none, and
    verdicts whose reason contradicts them."""
    judged = [
        _judged(_mitigation("safe_exec", "src/does/not/exist.py"), reviewed_tree),
        _judged(_mitigation("Input validation and sanitization", "app/safe.py"), reviewed_tree),
        _judged({"status": "MITIGATED", "reason": "Bounded elsewhere"}, reviewed_tree),
        _judged(_mitigation("safe_exec", "app/safe.py"), reviewed_tree),
        _judged({**_CONFIRMATION, "reason": "No command injection reaches os.system."}, None),
    ]

    distributions = compute_verdict_distributions(judged)

    assert (distributions["verification_note"], distributions["status"]) == (
        {"mitigation-unproven": 3, "verifier-contradiction": 1},
        {"UNVERIFIED": 4, "MITIGATED": 1},
    )


@pytest.mark.parametrize("by", ["llm", "human", "agent"])
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


@pytest.mark.parametrize(
    ("perimeter", "changed", "matched"),
    [
        (".github/workflows/ci.yml", ".github/workflows/ci.yml", True),
        ("./.github/workflows/ci.yml", ".github/workflows/ci.yml", True),
        ("./src/app.py", "src/app.py", True),
        ("/etc/hostname", "/etc/hostname", True),
        # A scanner's absolute path inside the repository is its repository-relative file.
        ("{repo}/src/app.py", "src/app.py", True),
        ("{repo}/.github/workflows/ci.yml", ".github/workflows/ci.yml", True),
        (".github/workflows/ci.yml", "github/workflows/ci.yml", False),
        (".devops/review.md", "devops/review.md", False),
        # An absolute path outside the repository matches only itself.
        ("/etc/hostname", "etc/hostname", False),
        ("{elsewhere}/src/app.py", "src/app.py", False),
        ("etc/hostname", "/etc/hostname", False),
    ],
)
def test_a_perimeter_path_matches_itself_and_no_other_file(
    perimeter: str, changed: str, matched: bool, tmp_path: Path
) -> None:
    """`.lstrip("./")` cut the dot off `.github/...` and the root off an absolute path."""
    from devops_cli.ai.review.mitigations import (
        MitigatedFindingEntry,
        find_perimeter_changes,
        save_mitigated_findings,
    )

    repo = tmp_path / "repo"
    named = perimeter.format(repo=repo.resolve(), elsewhere=(tmp_path / "elsewhere").resolve())
    ledger = tmp_path / "mitigated_findings.json"
    save_mitigated_findings([MitigatedFindingEntry(title="t", perimeter_files=[named])], ledger)

    assert bool(find_perimeter_changes([changed], ledger, repo_root=repo)) is matched


def test_a_person_mitigating_a_scanner_finding_is_warned_when_its_file_changes(
    tmp_path: Path,
) -> None:
    """A person's MITIGATED verdict on a scanner finding records its absolute location as the
    perimeter, which a repository-relative changed file must still reach."""
    from devops_cli.ai.review.mitigations import find_perimeter_changes, record_mitigated_finding

    repo = (tmp_path / "repo").resolve()
    ledger = tmp_path / "mitigated_findings.json"
    scanner_finding = Finding(
        title="Untrusted user input in `importlib.import_module()`",
        location=f"{repo}/src/devops_cli/commands/workspace.py:43",
    )
    entry = record_mitigated_finding(scanner_finding, reason="fixed mapping", ledger_path=ledger)

    assert (
        entry.perimeter_files,
        [
            e.id
            for e, _ in find_perimeter_changes(
                ["src/devops_cli/commands/workspace.py"], ledger, repo_root=repo
            )
        ],
        find_perimeter_changes(["src/devops_cli/commands/other.py"], ledger, repo_root=repo),
    ) == ([f"{repo}/src/devops_cli/commands/workspace.py"], [entry.id], [])


def test_contradictory_verdict_llm_acc69d97_stays_unverified() -> None:
    """Offline golden test: a verdict confirming its finding while matching genuine invalidation
    criteria ends UNVERIFIED with verifier-contradiction, taking no verified_by, verified_at,
    or citation_line, even when its reason repeats the title (#1059).

    Covers session S10 cache llm_acc69d97 on finding :1221 (path traversal) and finding :1239
    (race condition), plus swapped-criteria fixture.
    """
    from devops_cli.config.constants import CONST_VERIFIER_CONTRADICTION

    finding_1221 = Finding(
        severity="HIGH",
        location="src/devops_cli/ai/review/verification.py:1221",
        title="Potential Path Traversal in Type Checking Probe",
        description="The _module_typechecks_clean function constructs a module path using absolute().",
        fix="module = str(Path(path_str).resolve())",
        verification_criteria=[
            VerificationCriterion(
                description="The module path is constructed using Path.resolve() which resolves symbolic links and normalizes the path",
                executable=False,
            )
        ],
        invalidation_criteria=[
            VerificationCriterion(
                description="Path.resolve() normalizes paths to prevent directory traversal",
                executable=False,
            )
        ],
    )
    verdict_1221 = {
        "finding_id": 1,
        "title": "Potential Path Traversal in Type Checking Probe",
        "verified": True,
        "mitigated": False,
        "invalidated": False,
        "status": "VERIFIED",
        "reportable": True,
        "location": "src/devops_cli/ai/review/verification.py:1221",
        "citation_line": 1221,
        "verified_criteria_matched": [
            "The module path is constructed using Path.resolve() which resolves symbolic links and normalizes the path"
        ],
        "invalidated_criteria_matched": [
            "Path.resolve() normalizes paths to prevent directory traversal"
        ],
        "reason": (
            "Line 1221 in src/devops_cli/ai/review/verification.py shows module = str(Path(path_str).absolute()). "
            "However, the code uses a cached directory path. Path(path_str).absolute() call is not directly used to "
            "construct the module path passed to mypy. Therefore, the vulnerability described is mitigated by isolation."
        ),
    }

    finding_1239 = Finding(
        severity="MEDIUM",
        location="src/devops_cli/ai/review/verification.py:1239",
        title="Potential Race Condition in Type Checking Probe Cache Directory Creation",
        description="No explicit check to ensure that the cache directory is protected from race conditions.",
        fix="Add explicit locking or atomic operations when creating and accessing the cache directory.",
        verification_criteria=[
            VerificationCriterion(
                description="Cache directory creation is protected by a lock to prevent race conditions",
                executable=False,
            )
        ],
        invalidation_criteria=[
            VerificationCriterion(
                description="The code does not implement explicit race condition protection for cache directory creation",
                executable=False,
            )
        ],
    )
    verdict_1239 = {
        "finding_id": 2,
        "title": "Potential Race Condition in Type Checking Probe Cache Directory Creation",
        "verified": True,
        "mitigated": False,
        "invalidated": False,
        "status": "VERIFIED",
        "reportable": True,
        "location": "src/devops_cli/ai/review/verification.py:1239",
        "citation_line": 1239,
        "verified_criteria_matched": [
            "Cache directory creation is protected by a lock to prevent race conditions"
        ],
        "invalidated_criteria_matched": [
            "The code does not implement explicit race condition protection for cache directory creation"
        ],
        "reason": (
            "Lines 1223-1246 show _TYPECHECK_PROBE_LOCK is used. The lock ensures only one thread can execute, "
            "preventing race conditions during concurrent access to the cache directory. This mitigates the "
            "potential race condition described in the finding."
        ),
    }

    finding_swapped_1239 = Finding(
        severity="MEDIUM",
        location="src/devops_cli/ai/review/verification.py:1239",
        title="Potential Race Condition in Type Checking Probe Cache Directory Creation",
        description="No explicit check to ensure that the cache directory is protected from race conditions.",
        fix="Add explicit locking or atomic operations when creating and accessing the cache directory.",
        verification_criteria=[
            VerificationCriterion(
                description="The code does not implement explicit race condition protection for cache directory creation",
                executable=False,
            )
        ],
        invalidation_criteria=[
            VerificationCriterion(
                description="Cache directory creation is protected by a lock to prevent race conditions",
                executable=False,
            )
        ],
    )
    swapped_verdict_1239 = {
        **verdict_1239,
        "verified_criteria_matched": [
            "The code does not implement explicit race condition protection for cache directory creation"
        ],
        "invalidated_criteria_matched": [
            "Cache directory creation is protected by a lock to prevent race conditions"
        ],
    }

    judged_1221 = _apply_single_finding_verification(
        finding_1221, verdict_1221, "2026-10-06T00:00:00Z"
    )
    judged_1239 = _apply_single_finding_verification(
        finding_1239, verdict_1239, "2026-10-06T00:00:00Z"
    )
    judged_swapped = _apply_single_finding_verification(
        finding_swapped_1239, swapped_verdict_1239, "2026-10-06T00:00:00Z"
    )

    assert_verdict_invariants([judged_1221, judged_1239, judged_swapped])

    expected_outcome = ("UNVERIFIED", True, None, None, None, CONST_VERIFIER_CONTRADICTION)
    assert (
        (
            judged_1221.status,
            judged_1221.reportable,
            judged_1221.verified_by,
            judged_1221.verified_at,
            judged_1221.citation_line,
            judged_1221.verification_note,
        ),
        (
            judged_1239.status,
            judged_1239.reportable,
            judged_1239.verified_by,
            judged_1239.verified_at,
            judged_1239.citation_line,
            judged_1239.verification_note,
        ),
        (
            judged_swapped.status,
            judged_swapped.reportable,
            judged_swapped.verified_by,
            judged_swapped.verified_at,
            judged_swapped.citation_line,
            judged_swapped.verification_note,
        ),
    ) == (expected_outcome, expected_outcome, expected_outcome)


def test_unchanged_verification_behavior_s10_pricing_and_services() -> None:
    """Verify unchanged behavior for verdicts that only refute (self-refutation), verdicts that neither
    confirm nor refute (inconclusive), and confirmations whose invalidation criteria all restate the claim."""
    from devops_cli.config.constants import (
        CONST_VERIFIER_INCONCLUSIVE,
        CONST_VERIFIER_SELF_REFUTATION,
    )

    pricing_finding = Finding(
        severity="HIGH",
        location="src/devops_cli/ai/spend/pricing.py:55-56",
        title="Exception Handling in Settings Loading",
        description=(
            "The _load_settings_payload function catches all exceptions generically with except Exception: pass, "
            "which can mask critical configuration errors or unexpected system issues."
        ),
        fix="Log the exception or catch specific exceptions like (OSError, ValueError) and re-raise or handle them appropriately.",
        verification_criteria=[
            VerificationCriterion(
                description="Function should not catch all exceptions without logging or re-raising specific ones",
                executable=False,
            )
        ],
        invalidation_criteria=[
            VerificationCriterion(
                description="Function should raise an exception when settings loading fails",
                executable=False,
            )
        ],
    )
    pricing_verdict = {
        "finding_id": 1,
        "title": "Exception Handling in Settings Loading",
        "status": "INVALIDATED",
        "invalidated": True,
        "verified": False,
        "citation_line": 55,
        "invalidated_criteria_matched": [
            "Function should not catch all exceptions without logging or re-raising specific ones"
        ],
        "reason": (
            "Line 55 in src/devops_cli/ai/spend/pricing.py explicitly catches all exceptions with except Exception: pass "
            "and does not log or re-raise them. The verification criterion states that the function should not catch all "
            "exceptions without logging, which is violated by the implementation, confirming the finding is accurate."
        ),
    }
    judged_pricing = _apply_single_finding_verification(
        pricing_finding, pricing_verdict, "2026-10-06T00:00:00Z"
    )

    services_finding = Finding(
        severity="MEDIUM",
        location="k8s/llm/profiles/services.yaml:Service/ollama-128gib",
        title="Service exposes unauthenticated internal endpoint",
        description="The ollama service definition exposes port 11434 without auth.",
    )
    services_verdict = {
        "finding_id": 2,
        "status": "UNVERIFIED",
        "verified": False,
        "invalidated": False,
        "mitigated": False,
        "reason": "Cannot determine from yaml whether network policy enforces authorization.",
    }
    judged_services = _apply_single_finding_verification(
        services_finding, services_verdict, "2026-10-06T00:00:00Z"
    )

    restating_finding = Finding(
        severity="MEDIUM",
        location="Dockerfile:10",
        title="FROM directive still uses latest tag",
        description="The Dockerfile FROM directive specifies latest tag.",
        fix="Pin the image to a specific sha256 digest.",
        verification_criteria=[
            VerificationCriterion(
                description="The FROM directive still uses 'latest' as the image tag.",
                executable=False,
            )
        ],
        invalidation_criteria=[
            VerificationCriterion(
                description="The FROM directive pins the image to a specific sha256 digest.",
                executable=False,
            )
        ],
    )
    restating_verdict = {
        "finding_id": 3,
        "status": "VERIFIED",
        "verified": True,
        "citation_line": 10,
        "verified_criteria_matched": ["The FROM directive still uses 'latest' as the image tag."],
        "invalidated_criteria_matched": [
            "The FROM directive still uses 'latest' as the image tag."
        ],
        "reason": "Line 10 specifies python:latest, confirming the latest tag is used.",
    }
    judged_restating = _apply_single_finding_verification(
        restating_finding, restating_verdict, "2026-10-06T00:00:00Z"
    )

    assert_verdict_invariants([judged_pricing, judged_services, judged_restating])

    assert (
        (judged_pricing.status, judged_pricing.verification_note, judged_pricing.verified_by),
        (judged_services.status, judged_services.verification_note, judged_services.verified_by),
        (
            judged_restating.status,
            judged_restating.verification_note,
            judged_restating.verified_by,
            judged_restating.citation_line,
        ),
    ) == (
        ("UNVERIFIED", CONST_VERIFIER_SELF_REFUTATION, None),
        ("UNVERIFIED", CONST_VERIFIER_INCONCLUSIVE, None),
        ("VERIFIED", None, "llm", 10),
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
