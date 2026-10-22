"""Unit tests for the ReviewPipelineOrchestrator code review stages."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import FileAnalysisMeta


@pytest.fixture(autouse=True)
def mock_rag_investigator():
    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        yield


def _create_mock_review_llm() -> MagicMock:
    """Helper creating a mock LLM for review pipeline tests."""
    mock_llm = MagicMock()
    review_json = (
        '```json\n{"findings": [{"severity": "HIGH", "location": "src/dummy.py:1", '
        '"title": "Test Issue", "description": "Desc", "fix": "Fix", '
        '"confidence_score": 0.95}]}\n```'
    )
    verify_json = (
        '```json\n[{"location": "src/dummy.py:1", "severity": "HIGH", '
        '"verified": true, "mitigated": false, "confidence_score": 0.95, "reason": "Valid"}]\n```'
    )

    def _fake_chat(*args: object, **kwargs: object) -> str:
        content = str(args)
        if "Verify each finding" in content:
            return verify_json
        return review_json

    mock_llm.chat_messages.side_effect = _fake_chat
    mock_llm.chat_complete.side_effect = _fake_chat
    mock_llm.chat.side_effect = _fake_chat
    mock_llm.complete.side_effect = _fake_chat
    return mock_llm


def test_review_pipeline_stages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the staged review pipeline's initialization and execution."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    mock_llm = _create_mock_review_llm()
    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-session", llm_client=mock_llm, target_dir=tmp_path
    )

    # Stage 1: Pre-analysis refresh
    meta_dict = orchestrator.run_pre_analysis_refresh(tmp_path)
    assert isinstance(meta_dict, dict)

    # Stage 2: Per-file payload initialization
    fmeta = FileAnalysisMeta(path="src/dummy.py", key_symbols=["foo"], dependencies=["utils"])
    payloads = orchestrator.init_per_file_payloads(["src/dummy.py"], {"src/dummy.py": fmeta})
    assert len(payloads) == 1
    assert payloads[0].file_path == "src/dummy.py"

    file_json = orchestrator.files_dir / "src_dummy_py.json"
    assert file_json.exists()

    # Stage 3: Consolidated report generation
    data_out, report_md = orchestrator.generate_consolidated_report(payloads)
    assert isinstance(data_out, dict)
    assert "Code Review Report" in report_md
    assert (orchestrator.session_dir / "findings.json").exists()
    assert (orchestrator.session_dir / "review.md").exists()


def test_consolidated_report_keeps_every_candidate_with_its_verification_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify candidates.json keeps invalidated findings that findings.json leaves out."""
    import json

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    orchestrator = ReviewPipelineOrchestrator(
        session_id="candidates", llm_client=MagicMock(), target_dir=tmp_path
    )
    kept = SavedFinding(
        location="src/a.py:3",
        title="Kept",
        description="d",
        status="VERIFIED",
        verified=True,
        verified_by="criteria",
    )
    dropped = SavedFinding(
        location="src/a.py:9",
        title="Dropped",
        description="d",
        status="INVALIDATED",
        reportable=False,
    )
    payload = FileReviewPayload(file_path="src/a.py", findings=[kept, dropped])

    orchestrator.generate_consolidated_report([payload])

    def titles(name: str) -> list[tuple[str, str]]:
        data = json.loads((orchestrator.session_dir / name).read_text(encoding="utf-8"))
        return [(f["title"], f["status"]) for f in data["findings"]]

    assert (titles("findings.json"), titles("candidates.json")) == (
        [("Kept", "VERIFIED")],
        [("Kept", "VERIFIED"), ("Dropped", "INVALIDATED")],
    )


def test_get_server_info_formatting() -> None:
    """Test server info formatting under different LLM client configurations."""
    orchestrator = ReviewPipelineOrchestrator(session_id="test-info", target_dir=Path("."))

    # None or basic client
    info_default = orchestrator._get_server_info()
    assert isinstance(info_default, str)
    assert len(info_default) > 0

    mock_client = MagicMock()
    mock_client.backend_info = "ollama (localhost:11434)"
    mock_config = MagicMock()
    mock_config.model = "qwen2.5-coder:7b"
    mock_client._config = mock_config
    orchestrator.llm_client = mock_client

    info_formatted = orchestrator._get_server_info()
    assert info_formatted == "ollama (localhost:11434) [model: qwen2.5-coder:7b]"


def test_init_per_file_payloads_path_matching(tmp_path: Path, monkeypatch) -> None:
    """init_per_file_payloads matches metadata by exact and normalized suffix paths."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    orchestrator = ReviewPipelineOrchestrator(session_id="test-path-matching", target_dir=tmp_path)

    meta_full = FileAnalysisMeta(
        path="src/devops_cli/ai/agents/__init__.py",
        primary_purpose="Agents module init",
        key_symbols=["PydanticAgent"],
        dependencies=["pydantic"],
        quality_score=0.9,
    )
    metadata_by_path = {"src/devops_cli/ai/agents/__init__.py": meta_full}

    # Pass relative path suffix
    payloads = orchestrator.init_per_file_payloads(["agents/__init__.py"], metadata_by_path)

    assert len(payloads) == 1
    assert payloads[0].metadata.primary_purpose == "Agents module init"
    assert payloads[0].metadata.key_symbols == ["PydanticAgent"]
    assert payloads[0].metadata.quality_score == 0.9


def test_consolidated_report_findings_sorted_by_severity_and_confidence(
    tmp_path: Path, monkeypatch
) -> None:
    """Findings in report_md and findings.json must be sorted by severity and confidence."""
    from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    orchestrator = ReviewPipelineOrchestrator(session_id="sort-test-session", target_dir=tmp_path)

    f_low = SavedFinding(
        severity="LOW",
        title="Low Finding High Confidence",
        location="src/low.py:1",
        confidence_score=0.99,
        status="VERIFIED",
        verified=True,
        verified_by="criteria",
    )
    f_med_high_conf = SavedFinding(
        severity="MEDIUM",
        title="Medium Finding High Confidence",
        location="src/med1.py:1",
        confidence_score=0.95,
        status="VERIFIED",
        verified=True,
        verified_by="criteria",
    )
    f_med_low_conf = SavedFinding(
        severity="MEDIUM",
        title="Medium Finding Low Confidence",
        location="src/med2.py:1",
        confidence_score=0.70,
        status="VERIFIED",
        verified=True,
        verified_by="criteria",
    )
    f_crit_low_conf = SavedFinding(
        severity="CRITICAL",
        title="Critical Finding Lower Confidence",
        location="src/crit2.py:1",
        confidence_score=0.85,
        status="VERIFIED",
        verified=True,
        verified_by="criteria",
    )
    f_crit_high_conf = SavedFinding(
        severity="CRITICAL",
        title="Critical Finding Higher Confidence",
        location="src/crit1.py:1",
        confidence_score=0.98,
        status="VERIFIED",
        verified=True,
        verified_by="criteria",
    )
    f_high = SavedFinding(
        severity="HIGH",
        title="High Finding",
        location="src/high.py:1",
        confidence_score=0.90,
        status="VERIFIED",
        verified=True,
        verified_by="criteria",
    )

    payload = FileReviewPayload(
        file_path="src/dummy.py",
        findings=[
            f_low,
            f_med_low_conf,
            f_crit_low_conf,
            f_med_high_conf,
            f_crit_high_conf,
            f_high,
        ],
    )

    data_out, report_md = orchestrator.generate_consolidated_report([payload])

    sorted_titles = [f["title"] for f in data_out["findings"]]
    expected_titles = [
        "Critical Finding Higher Confidence",
        "Critical Finding Lower Confidence",
        "High Finding",
        "Medium Finding High Confidence",
        "Medium Finding Low Confidence",
        "Low Finding High Confidence",
    ]
    assert sorted_titles == expected_titles

    # Verify report_md ordering
    crit1_idx = report_md.index("Critical Finding Higher Confidence")
    crit2_idx = report_md.index("Critical Finding Lower Confidence")
    high_idx = report_md.index("High Finding")
    med1_idx = report_md.index("Medium Finding High Confidence")
    med2_idx = report_md.index("Medium Finding Low Confidence")
    low_idx = report_md.index("Low Finding High Confidence")

    assert crit1_idx < crit2_idx < high_idx < med1_idx < med2_idx < low_idx


def test_normalize_unicode_text_in_findings() -> None:
    """Findings must sanitize non-standard Unicode hyphens, spaces, and smart quotes."""
    from devops_cli.ai.review_schema import Finding, normalize_unicode_text

    raw_text = "NIST SP 800\u201153 Rev\u202f5 SI\u20112 and SOC\u202f2 Type\u202fII"
    normalized = normalize_unicode_text(raw_text)
    assert normalized == "NIST SP 800-53 Rev 5 SI-2 and SOC 2 Type II"

    finding = Finding(
        title="Title with \u2018smart quotes\u2019 and non\u2011breaking hyphen",
        description="Description with narrow\u202fno\u202fbreak\u202fspaces",
        references=["NIST SP 800\u201153 Rev\u202f5 SI\u20112"],
    )
    assert finding.title == "Title with 'smart quotes' and non-breaking hyphen"
    assert finding.description == "Description with narrow no break spaces"
    assert finding.references == ["NIST SP 800-53 Rev 5 SI-2"]


def test_criteria_based_verification_and_reportability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Findings define verification and invalidation criteria that determine
    reportability and confidence.
    """
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))

    orchestrator = ReviewPipelineOrchestrator(
        session_id="criteria-test", llm_client=MagicMock(), target_dir=tmp_path
    )

    f_reportable = SavedFinding(
        severity="HIGH",
        location="src/main.rs:10-20",
        title="Unchecked array access",
        description="Array indexing without bounds check",
        fix="Use .get() with error handling",
        verification_criteria=[
            "Indexing using raw integer slice",
            "Zero length check preceding indexing",
        ],
        invalidation_criteria=["Bounds check present upstream", "Bounded fixed-size array"],
        verified_criteria_matched=[
            "Indexing using raw integer slice",
            "Zero length check preceding indexing",
        ],
        invalidated_criteria_matched=[],
        status="VERIFIED",
        verified=True,
        verified_by="criteria",
        reportable=True,
        confidence_score=1.0,
        persona="qa",
        persona_title="Senior Test Engineer",
    )

    f_invalidated = SavedFinding(
        severity="MEDIUM",
        location="src/config.rs:5-10",
        title="Hardcoded credentials",
        description="Potential secret leak in config file",
        fix="Use environment variable or keyring",
        verification_criteria=["Plaintext secret key in active production code"],
        invalidation_criteria=[
            "Example template placeholder (.example.yaml)",
            "Masked marker <masked-*>",
        ],
        verified_criteria_matched=[],
        invalidated_criteria_matched=["Example template placeholder (.example.yaml)"],
        status="INVALIDATED",
        verified=False,
        reportable=False,
        confidence_score=0.0,
        persona="devsecops",
        persona_title="Principal DevSecOps Engineer",
    )

    payload = FileReviewPayload(
        file_path="src/main.rs",
        findings=[f_reportable, f_invalidated],
    )

    data_out, report_md = orchestrator.generate_consolidated_report([payload])

    # Only the reportable verified finding should be in the report
    assert len(data_out["findings"]) == 1
    assert data_out["findings"][0]["title"] == "Unchecked array access"
    assert data_out["findings"][0]["reportable"] is True
    assert data_out["findings"][0]["status"] == "VERIFIED"
    assert len(data_out["findings"][0]["verification_criteria"]) == 2
    assert "- **Status**: VERIFIED" in report_md
    assert "Unchecked array access" in report_md
    assert "Hardcoded credentials" not in report_md


def test_generate_consolidated_report_with_intelligence_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that dependencies and network references with security status are
    rendered in review report.
    """
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))

    from devops_cli.models.vulnerability import DependencySpec, NetworkReference

    orchestrator = ReviewPipelineOrchestrator(
        session_id="intel-tables-test",
        llm_client=MagicMock(),
        target_dir=tmp_path,
    )
    payload = FileReviewPayload(
        file_path="src/main.py",
        findings=[],
        external_dependencies=[
            DependencySpec(
                name="pydantic",
                version_range=">=2.10.0",
                ecosystem="PyPI",
                source_file="requirements.txt",
                severity="CLEAN",
                security_status="✓ Clean (0 CVEs)",
            ),
            DependencySpec(
                name="vulnerable-pkg",
                version_range="1.0.0",
                ecosystem="PyPI",
                source_file="requirements.txt",
                severity="HIGH",
                security_status="⚠️ 1 Known Vuln(s) [HIGH]",
            ),
        ],
        network_references=[
            NetworkReference(
                target="https://api.example-corp.com",
                reference_type="url",
                source_file="src/main.py",
                line_number=15,
                security_status="✓ Safe / Low Risk",
            ),
            NetworkReference(
                target="93.184.216.34",
                reference_type="ip",
                source_file="src/main.py",
                line_number=20,
                security_status="✓ Safe (Ports: 80, 443)",
            ),
        ],
    )

    data_out, report_md = orchestrator.generate_consolidated_report([payload])

    assert "## External Dependencies (OSV.dev)" in report_md
    assert (
        "| Severity | Dependency | Version Range | Ecosystem | "
        "Security Status | Location |" in report_md
    )
    assert (
        "| CLEAN | `pydantic` | `>=2.10.0` | PyPI | "
        "✓ Clean (0 CVEs) | `requirements.txt:1` |" in report_md
    )
    assert (
        "| **HIGH** | `vulnerable-pkg` | `1.0.0` | PyPI | "
        "⚠️ 1 Known Vuln(s) [HIGH] | `requirements.txt:1` |" in report_md
    )

    assert "## Network References & Endpoints (Shodan InternetDB & Cloudflare Radar)" in report_md
    assert (
        "| `https://api.example-corp.com` | url | External | ✓ Safe / Low Risk | `src/main.py:15` |"
        in report_md
    )
    assert (
        "| `93.184.216.34` | ip | External | ✓ Safe (Ports: 80, 443) | `src/main.py:20` |"
        in report_md
    )

    assert len(data_out["external_dependencies"]) == 2
    assert len(data_out["network_references"]) == 2


def test_empty_findings_filtered_and_field_aliasing() -> None:
    """Verify that blank/empty findings are discarded and alternate field names mapped."""
    from devops_cli.ai.review_schema import Finding, ReviewResult, parse_review_response

    # 1. Blank finding is empty
    blank = Finding(severity="MEDIUM", location="", title="", description="", fix="")
    assert blank.is_empty is True

    # 2. Finding with title/description is not empty
    valid_f = Finding(
        title="SQL Injection", description="Unsanitized user input", location="db.py:10"
    )
    assert valid_f.is_empty is False

    # 3. Field aliasing maps alternative keys
    aliased_data = {
        "issue": "SSRF vulnerability",
        "details": "User-controlled URL passed to requests.get",
        "file": "fetch.py:42",
        "remediation": "Validate target IP address",
    }
    f_aliased = Finding.model_validate(aliased_data)
    assert f_aliased.title == "SSRF vulnerability"
    assert f_aliased.description == "User-controlled URL passed to requests.get"
    assert f_aliased.location == "fetch.py:42"
    assert f_aliased.fix == "Validate target IP address"
    assert f_aliased.is_empty is False

    # 4. ReviewResult filters out empty findings and sets recommendation to APPROVE
    res = ReviewResult(
        findings=[blank, valid_f, Finding(title="", description="")],
        recommendation="REQUEST CHANGES",
    )
    assert len(res.findings) == 1
    assert res.findings[0].title == "SQL Injection"

    res_all_empty = ReviewResult(
        findings=[blank],
        recommendation="REQUEST CHANGES",
    )
    assert len(res_all_empty.findings) == 0
    assert res_all_empty.recommendation == "APPROVE"

    # 5. Parsing LLM outputs with empty finding structures
    raw_json = (
        '{"findings": [{"severity": "MEDIUM", "location": "", "title": "", '
        '"description": "", "fix": ""}], "recommendation": "REQUEST CHANGES"}'
    )
    parsed = parse_review_response(raw_json)
    assert parsed is not None
    assert len(parsed.findings) == 0
    assert parsed.recommendation == "APPROVE"


def test_generate_consolidated_report_prints_findings_and_review_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify that generate_consolidated_report renders both the Code Review Findings
    table and the Review Summary table to console on review completion.
    """
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))

    session_dir = tmp_path / ".data" / "reviews" / "summary-output-test"
    session_dir.mkdir(parents=True, exist_ok=True)
    orchestrator = ReviewPipelineOrchestrator(
        session_id="summary-output-test",
        session_dir=session_dir,
        llm_client=MagicMock(),
        target_dir=tmp_path,
    )
    finding = SavedFinding(
        severity="HIGH",
        location="src/auth.py:42",
        title="Hardcoded Credential",
        description="Found hardcoded secret key in auth module",
        status="VERIFIED",
        verified=True,
        verified_by="criteria",
        persona="devsecops",
        persona_title="Principal DevSecOps Engineer",
        reportable=True,
        confidence_score=0.95,
    )
    payload = FileReviewPayload(
        file_path="src/auth.py",
        findings=[finding],
        external_dependencies=[],
        network_references=[],
    )

    data_out, report_md = orchestrator.generate_consolidated_report([payload])
    captured = capsys.readouterr().out

    assert "Code Review Findings" in captured
    assert "src/auth.py:42" in captured
    assert "Hardcoded Credential" in captured
    assert "VERIFIED" in captured
    assert "Dependencies: none declared in the reviewed files." in captured
    assert "Network references: none in the reviewed files." in captured
    assert "Review Summary" in captured
    assert "Files Reviewed" in captured
    assert "Reportable Findings" in captured
    assert "1 High" in captured
    assert "1/1 verified (100%)" in captured
    assert "Consolidated review completed for session summary-output-test" in captured
    assert len(data_out["findings"]) == 1
    assert "## Summary of Reportable Findings" in report_md


def test_generate_consolidated_report_clean_review_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify clean review summary output when 0 reportable findings are generated."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))

    orchestrator = ReviewPipelineOrchestrator(
        session_id="clean-summary-test",
        llm_client=MagicMock(),
        target_dir=tmp_path,
    )
    payload = FileReviewPayload(
        file_path="src/clean_code.py",
        findings=[],
        external_dependencies=[],
        network_references=[],
    )

    data_out, report_md = orchestrator.generate_consolidated_report([payload])
    captured = capsys.readouterr().out

    assert "No reportable findings across reviewed files" in captured
    assert "Review Summary" in captured
    assert "0 findings (Clean)" in captured
    assert "✓ All clean" in captured
    assert "Consolidated review completed for session clean-summary-test" in captured
    assert len(data_out["findings"]) == 0
    assert "No critical issues found during review" in report_md


def test_review_pipeline_skips_and_lists_errored_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify that any errored files across review stages are skipped and listed in output."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))

    orchestrator = ReviewPipelineOrchestrator(
        session_id="error-skip-test", llm_client=MagicMock(), target_dir=tmp_path
    )
    orchestrator.errored_files["src/bad_syntax.py"] = (
        "Stage 3 (Review): SyntaxError: invalid syntax"
    )
    orchestrator.errored_files["src/missing_file.py"] = (
        "Stage 2 (Initialization): FileNotFoundError"
    )

    valid_payload = FileReviewPayload(
        file_path="src/good.py",
        findings=[
            SavedFinding(
                severity="MEDIUM",
                location="src/good.py:10",
                title="Input validation",
                description="Missing input validation",
                status="VERIFIED",
                verified=True,
                verified_by="criteria",
                persona="devsecops",
                persona_title="Principal DevSecOps Engineer",
                reportable=True,
            )
        ],
        external_dependencies=[],
        network_references=[],
    )

    _data_out, report_md = orchestrator.generate_consolidated_report([valid_payload])
    captured = capsys.readouterr().out

    # 1. Console outputs errored files table and summary metric
    assert "Skipped / Errored Files During Review" in captured
    assert "src/bad_syntax.py" in captured
    assert "src/missing_file.py" in captured
    assert "2 file(s) skipped" in captured

    # 2. Markdown report includes dedicated errored files table
    assert "## Skipped / Errored Files" in report_md
    assert "| `src/bad_syntax.py` | Stage 3 (Review): SyntaxError: invalid syntax |" in report_md
    assert "| `src/missing_file.py` | Stage 2 (Initialization): FileNotFoundError |" in report_md


def test_review_pipeline_dependency_and_network_auditing() -> None:
    """Verify linked files resolution, vulnerability auditing, and network reputation caching."""
    from devops_cli.models.vulnerability import (
        DependencySpec,
        NetworkReference,
        NetworkReputationRecord,
        PackageLookupResult,
        VulnerabilityRecord,
    )

    orchestrator = ReviewPipelineOrchestrator(session_id="audit-test", target_dir=Path("."))

    # 1. Linked files
    meta1 = FileAnalysisMeta(
        path="src/a.py", key_symbols=["ServiceA"], dependencies=["devops_cli.b"]
    )
    meta2 = FileAnalysisMeta(
        path="src/b.py", key_symbols=["ServiceB"], dependencies=["devops_cli.b"]
    )
    meta_dict = {"src/a.py": meta1, "src/b.py": meta2}

    linked = orchestrator._find_linked_files("src/a.py", meta1, meta_dict)
    assert len(linked) == 1
    assert linked[0].path == "src/b.py"

    # 2. Audit dependencies
    dep_clean = DependencySpec(name="pydantic", version_range="2.11.0", ecosystem="PyPI")
    dep_vuln = DependencySpec(name="requests", version_range="2.20.0", ecosystem="PyPI")
    dep_failed = DependencySpec(name="urllib3", version_range="1.26.0", ecosystem="PyPI")
    vuln_rec = VulnerabilityRecord(
        id="CVE-2023-1234",
        summary="Vuln in requests",
        severity="CRITICAL",
        fixed_version="2.31.0",
    )
    dep_cache = {
        ("requests", "2.20.0", "PyPI"): PackageLookupResult(
            status="ok", vulnerabilities=[vuln_rec]
        ),
        ("pydantic", "2.11.0", "PyPI"): PackageLookupResult(status="ok", vulnerabilities=[]),
        ("urllib3", "1.26.0", "PyPI"): PackageLookupResult(status="failed", vulnerabilities=[]),
    }
    dep_unqueried = DependencySpec(name="flask", version_range="*", ecosystem="PyPI")

    findings = orchestrator._audit_file_dependencies(
        "src/app.py", [dep_clean, dep_vuln, dep_failed, dep_unqueried], dep_cache
    )
    assert (
        dep_clean.severity,
        dep_clean.queried,
        dep_vuln.severity,
        dep_vuln.queried,
        dep_failed.severity,
        dep_failed.queried,
        dep_failed.security_status,
        dep_unqueried.severity,
        dep_unqueried.queried,
        dep_unqueried.security_status,
        len(findings),
        "CVE-2023-1234" in findings[0].title,
    ) == (
        "CLEAN",
        True,
        "CRITICAL",
        True,
        "UNCHECKED",
        False,
        "Lookup Failed",
        "UNCHECKED",
        False,
        "Not Queried",
        1,
        True,
    )

    # 3. Audit network references
    net_clean = NetworkReference(target="127.0.0.1", reference_type="ip", is_local=True)
    net_mal = NetworkReference(
        target="https://malicious-site.cc", reference_type="url", is_local=False
    )
    net_cache = {
        "https://malicious-site.cc": NetworkReputationRecord(
            target="https://malicious-site.cc",
            ip="198.51.100.1",
            is_malicious=True,
            reputation_summary="C2 Server",
        )
    }

    net_findings = orchestrator._audit_file_network_references(
        "src/app.py", [net_clean, net_mal], net_cache
    )
    assert "Network Reference" in net_findings[0].title


def test_review_pipeline_orchestrator_extended_helpers(tmp_path: Path) -> None:
    """Verify ReviewPipelineOrchestrator path resolution, server info, and metadata matching."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.models.ai import FileAnalysisMeta

    orchestrator = ReviewPipelineOrchestrator(session_id="ext-test", target_dir=tmp_path)

    # 1. Path resolution
    safe_rel = orchestrator._resolve_file_path("src/app.py")
    assert str(tmp_path) in str(safe_rel)

    traversal_p = orchestrator._resolve_file_path("../../outside.py")
    assert str(tmp_path) in str(traversal_p)

    # 2. Server info
    cfg = AIConfig(
        provider="ollama", model="qwen2.5-coder:14b", ollama_urls=["http://example.com:11434"]
    )
    client = LLMClient(cfg)
    orchestrator_llm = ReviewPipelineOrchestrator(
        session_id="llm-info-test", llm_client=client, target_dir=tmp_path
    )
    s_info = orchestrator_llm._get_server_info()
    assert "qwen2.5-coder:14b" in s_info or "ollama" in s_info.lower()

    # 3. Matching metadata
    meta_exact = FileAnalysisMeta(path="src/utils/helpers.py", key_symbols=["help1"])
    meta_dict = {"src/utils/helpers.py": meta_exact}

    matched_exact = orchestrator._find_matching_metadata("src/utils/helpers.py", meta_dict)
    assert matched_exact is not None and matched_exact.key_symbols == ["help1"]

    matched_suffix = orchestrator._find_matching_metadata("utils/helpers.py", meta_dict)
    assert matched_suffix is not None

    matched_none = orchestrator._find_matching_metadata("nonexistent.py", meta_dict)
    assert matched_none is None


def test_orchestrator_session_directory_resolution(tmp_path: Path) -> None:
    """Verify session_dir resolution uses central data directory and does not contaminate subdirectories."""
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.review.session import ReviewSessionStore

    sub_target = tmp_path / "src" / "exceptions"
    sub_target.mkdir(parents=True, exist_ok=True)

    orch = ReviewPipelineOrchestrator(
        session_id="20260827-test-session",
        target_dir=sub_target,
    )

    assert orch.session_dir.parent == ReviewSessionStore.root()
    assert not (sub_target / ".data").exists()


def test_format_extraction_summary_distinguishes_probed_references() -> None:
    """Verify _format_extraction_summary distinguishes in-file vs workspace probed references."""
    from devops_cli.ai.review.pipeline import _format_extraction_summary

    # Case 1: Purely in-file references, 0 probed
    res_direct = _format_extraction_summary(
        direct_deps_count=5,
        direct_nets_count=2,
        probed_deps_count=0,
        probed_nets_count=0,
    )
    assert res_direct == "5 unique dependency(ies) and 2 network target(s)"

    # Case 2: 0 in-file references, both deps and nets probed
    res_probed_all = _format_extraction_summary(
        direct_deps_count=0,
        direct_nets_count=0,
        probed_deps_count=36,
        probed_nets_count=21,
    )
    assert res_probed_all == (
        "0 in-file references (36 project dependencies probed from workspace manifests, "
        "21 network targets probed from workspace configs)"
    )

    # Case 3: 0 in-file references, only deps probed
    res_probed_deps = _format_extraction_summary(
        direct_deps_count=0,
        direct_nets_count=0,
        probed_deps_count=12,
        probed_nets_count=0,
    )
    assert (
        res_probed_deps
        == "0 in-file references (12 project dependencies probed from workspace manifests)"
    )

    # Case 4: Partial in-file references with probed supplementary references
    res_mixed = _format_extraction_summary(
        direct_deps_count=2,
        direct_nets_count=1,
        probed_deps_count=0,
        probed_nets_count=8,
    )
    assert res_mixed == (
        "2 in-file dependency(ies) and 1 in-file network target(s) "
        "(8 network targets probed from workspace configs)"
    )


def test_try_reuse_cached_analysis_meta_invalidation(tmp_path: Path) -> None:
    """Verify that cached metadata is invalidated when mtime or content hash changes."""
    import hashlib
    from datetime import UTC, datetime, timedelta

    from devops_cli.ai.review.pipeline import _try_reuse_cached_analysis_meta
    from devops_cli.models.ai import FileAnalysisMeta

    test_file = tmp_path / "service.py"
    test_file.write_text("def run(): pass\n", encoding="utf-8")
    content_hash = hashlib.sha256(test_file.read_bytes(), usedforsecurity=False).hexdigest()

    past_dt = datetime.now(UTC) - timedelta(hours=1)
    future_dt = datetime.now(UTC) + timedelta(hours=1)

    cached_meta = FileAnalysisMeta(
        path="service.py",
        size_bytes=len("def run(): pass\n"),
        last_analyzed=future_dt.isoformat(),
        pseudocode=["1. Run service loop"],
        content_hash=content_hash,
    )

    # 1. Matching mtime & content hash -> Reused successfully
    file_mtime = datetime.fromtimestamp(test_file.stat().st_mtime, UTC)
    reused = _try_reuse_cached_analysis_meta(cached_meta, test_file, file_mtime)
    assert reused is not None
    assert reused.content_hash == content_hash
    assert reused.pseudocode == ["1. Run service loop"]

    # 2. File modified after cached last_analyzed -> Invalidated
    stale_meta = cached_meta.model_copy(update={"last_analyzed": past_dt.isoformat()})
    assert _try_reuse_cached_analysis_meta(stale_meta, test_file, file_mtime) is None

    # 3. File content changed (hash mismatch) -> Invalidated
    test_file.write_text("def run(): return 42\n", encoding="utf-8")
    new_mtime = datetime.fromtimestamp(test_file.stat().st_mtime, UTC)
    assert _try_reuse_cached_analysis_meta(cached_meta, test_file, new_mtime) is None

    # 4. File size mismatch -> Invalidated
    size_mismatched = cached_meta.model_copy(update={"size_bytes": 9999})
    assert _try_reuse_cached_analysis_meta(size_mismatched, test_file, new_mtime) is None


def test_render_single_finding_panel_escapes_malformed_markup(tmp_path: Path) -> None:
    """Verify that code snippets with unescaped closing tags like [/{status_color}] do not crash Rich."""
    from rich.console import Console

    orchestrator = ReviewPipelineOrchestrator(llm_client=MagicMock(), target_dir=tmp_path)
    console = Console(record=True, color_system=None)

    finding = SavedFinding(
        severity="HIGH",
        location="src/devops_cli/output/formatters/tables.py:402",
        title="Unescaped formatting in f'[{status_color}]{phase}[/{status_color}]'",
        description="Snippet has malformed markup: [/{status_color}] and [None] and list[int].",
        fix="Use escape_text(f'[{status_color}]{phase}[/{status_color}]') to sanitize.",
        invalidation_reason="Criteria: [/{status_color}] was detected.",
        references=["CWE-116", "https://example.com/cwe/[116]"],
    )

    # Must execute cleanly without raising rich.errors.MarkupError
    orchestrator._render_single_finding_panel(console, finding, 1)
    output = console.export_text()
    assert "Finding #1" in output
    assert "tables.py:402" in output
    assert "[/{status_color}]" in output


def test_orchestrator_worker_clamping_to_total_files() -> None:
    """Verify worker pool concurrency is clamped to total_files count."""
    from devops_cli.ai.review.pipeline import _review_worker_count

    config = AIConfig(provider="ollama", ollama_max_parallel=2)
    count1, _ = _review_worker_count(config, total_files=1, requested=16)
    assert count1 == 1

    count2, _ = _review_worker_count(config, total_files=2, requested=16)
    assert count2 == 2


def _file_pool_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    provider: str,
    file_count: int,
    concurrency: int | None,
    gateway_enabled: bool = False,
) -> int:
    """The concurrency sized for `file_count` files by a client of `provider`."""
    from devops_cli.ai.review.pipeline import _review_worker_count
    from devops_cli.output import print_info

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    config = AIConfig(
        provider=provider,
        gateway_enabled=gateway_enabled,
        ollama_urls=[f"http://example.com:{port}" for port in (11434, 11435, 11436)],
        ollama_max_parallel=2,
    )
    count, clamped = _review_worker_count(config, file_count, concurrency)
    if clamped is not None:
        print_info(
            f"--concurrency {clamped} is above the gateway's {count} backend slots; using {count}"
        )
    return count


def test_gateway_file_pool_is_the_slot_sum_whatever_the_ollama_nodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a gateway review's file pool is the gateway's slot sum, not Ollama nodes × slots."""
    from devops_cli.config.defaults import DEFAULT_GATEWAY_REVIEW_CONCURRENCY

    pool_size = _file_pool_size(
        tmp_path, monkeypatch, provider="gateway", file_count=6, concurrency=None
    )

    assert (pool_size, DEFAULT_GATEWAY_REVIEW_CONCURRENCY) == (3, 3)


def test_gateway_concurrency_above_the_slot_sum_is_clamped_with_one_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify an explicit --concurrency above the gateway's slots is clamped, and one warning
    names both numbers."""
    pool_size = _file_pool_size(
        tmp_path, monkeypatch, provider="gateway", file_count=6, concurrency=8
    )
    warning = "--concurrency 8 is above the gateway's 3 backend slots; using 3"

    assert (pool_size, capsys.readouterr().out.count(warning)) == (3, 1)


@pytest.mark.parametrize(
    ("gateway_enabled", "concurrency", "expected_pool_size"),
    [(False, 8, 8), (True, 8, 8), (True, None, 6)],
    ids=["explicit", "explicit-with-gateway-enabled", "nodes-with-gateway-enabled"],
)
def test_ollama_review_keeps_its_node_sizing_and_an_explicit_concurrency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    gateway_enabled: bool,
    concurrency: int | None,
    expected_pool_size: int,
) -> None:
    """Verify an Ollama review is sized by its nodes and keeps an explicit --concurrency above
    the gateway's slot sum, with no warning, even with `ai.gateway_enabled` set: that setting
    sends no chat call to the gateway, so the review takes none of its slots."""
    pool_size = _file_pool_size(
        tmp_path,
        monkeypatch,
        provider="ollama",
        file_count=10,
        concurrency=concurrency,
        gateway_enabled=gateway_enabled,
    )

    assert (pool_size, "backend slots" in capsys.readouterr().out) == (expected_pool_size, False)
