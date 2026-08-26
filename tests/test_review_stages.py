"""Unit tests for modular review pipeline stages."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.review.stages.adversarial_debate import run_adversarial_debate_stage
from devops_cli.ai.review.stages.persona_review import run_persona_review_stage
from devops_cli.ai.review.stages.pre_analysis import run_pre_analysis_stage
from devops_cli.ai.review.stages.reporting import run_reporting_stage
from devops_cli.ai.review.stages.reranking import run_reranking_stage
from devops_cli.ai.review.stages.static_scan import run_static_scan_stage
from devops_cli.ai.review.stages.verification import run_verification_stage
from devops_cli.ai.review_schema import (
    FileReviewPayload,
    SavedFinding,
)


def test_pre_analysis_stage(tmp_path: Path) -> None:
    test_file = tmp_path / "app.py"
    test_file.write_text("def hello(): pass\n")
    cached_meta, meta_dict = run_pre_analysis_stage(tmp_path, "local", "path")
    assert len(meta_dict) >= 1


def test_static_scan_stage(tmp_path: Path) -> None:
    test_py = tmp_path / "app.py"
    test_py.write_text("import subprocess\nsubprocess.run(['ls'])\n")

    test_yaml = tmp_path / "deploy.yaml"
    test_yaml.write_text("apiVersion: apps/v1\nkind: Deployment\n")

    findings, deps, nets = run_static_scan_stage([str(test_py), str(test_yaml)], tmp_path, {})
    assert str(test_py) in findings
    assert str(test_yaml) in findings
    assert isinstance(deps, list)
    assert isinstance(nets, list)


def test_persona_review_stage(tmp_path: Path) -> None:
    payload = FileReviewPayload(
        file_path="src/app.py",
        file_hash="12345",
        findings=[],
    )
    run_persona_review_stage([payload], {"src/app.py": "def test(): pass"})
    assert payload.file_path == "src/app.py"


def test_verification_stage() -> None:
    finding = SavedFinding(
        id="f1",
        title="Test Finding",
        severity="HIGH",
        location="src/app.py:10",
        description="A potential flaw",
        status="UNVERIFIED",
        persona="devsecops",
    )
    payload = FileReviewPayload(
        file_path="src/app.py",
        file_hash="12345",
        findings=[finding],
    )
    run_verification_stage([payload])
    assert len(payload.findings) == 1


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


def test_reranking_stage() -> None:
    f1 = SavedFinding(
        id="f1",
        title="Low issue",
        severity="LOW",
        location="src/b.py:10",
        description="Minor style",
        status="UNVERIFIED",
        persona="devsecops",
    )
    f2 = SavedFinding(
        id="f2",
        title="Critical vuln",
        severity="CRITICAL",
        location="src/a.py:5",
        description="Major RCE",
        status="UNVERIFIED",
        persona="devsecops",
    )
    reranked = run_reranking_stage([f1, f2, f1])
    assert len(reranked) == 2
    assert reranked[0].severity == "CRITICAL"
    assert reranked[1].severity == "LOW"


def test_reporting_stage(tmp_path: Path) -> None:
    finding = SavedFinding(
        id="f1",
        title="Critical vuln",
        severity="CRITICAL",
        location="src/a.py:5",
        description="Major RCE",
        status="UNVERIFIED",
        persona="devsecops",
    )
    session_dir = tmp_path / "reviews" / "test-session"
    report_path = run_reporting_stage(
        session_id="test-session",
        session_dir=session_dir,
        reportable_findings=[finding],
        all_deps=[],
        all_nets=[],
        n_files=1,
    )
    assert report_path.exists()
    assert (session_dir / "findings.json").exists()
