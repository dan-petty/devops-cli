"""Unit tests for ReviewPipelineOrchestrator 6-stage code review pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding
from devops_cli.models.ai import FileAnalysisMeta


def test_review_pipeline_stages(tmp_path: Path, monkeypatch) -> None:
    """Test 6-stage review pipeline initialization and execution."""
    monkeypatch.setattr("devops_cli.ai.review.pipeline.CONST_DATA_DIR", tmp_path)

    orchestrator = ReviewPipelineOrchestrator(session_id="test-session")

    # Stage 1: Pre-analysis refresh
    meta_dict = orchestrator.run_pre_analysis_refresh(tmp_path)
    assert isinstance(meta_dict, dict)

    # Stage 2: Per-file payload initialization
    fmeta = FileAnalysisMeta(path="src/dummy.py", key_symbols=["foo"], dependencies=["utils"])
    payloads = orchestrator.init_per_file_payloads(["src/dummy.py"], {"src/dummy.py": fmeta})
    assert len(payloads) == 1
    assert payloads[0].file_path == "src/dummy.py"
    assert "ai_scratchpad" in payloads[0].model_dump()
    assert payloads[0].ai_scratchpad["stage"] == "initialized"

    file_json = tmp_path / "reviews" / "test-session" / "files" / "src_dummy_py.json"
    assert file_json.exists()

    # Mock LLM response handler
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

    def _fake_chat(*args, **kwargs):
        content = str(args)
        if "Verify each finding" in content:
            return verify_json
        return review_json

    mock_llm.chat_messages.side_effect = _fake_chat
    mock_llm.chat_complete.side_effect = _fake_chat
    orchestrator.llm_client = mock_llm

    # Stage 3: Multi-persona content review
    orchestrator.execute_multi_persona_review(
        payloads,
        diff_text_by_file={"src/dummy.py": "def foo(): pass"},
        personas=["devsecops"],
    )
    assert payloads[0].ai_scratchpad["stage"] == "reviewed"
    assert len(payloads[0].findings) == 1

    # Stage 4: Cross-referencing verification
    orchestrator.execute_finding_verification(payloads)
    assert payloads[0].ai_scratchpad["stage"] == "verified"

    # Stage 5: AI validation & re-ranking
    orchestrator.execute_finding_reranking(payloads)
    assert payloads[0].ai_scratchpad["stage"] == "reranked"

    # Stage 6: Consolidated report generation
    data_out, report_md = orchestrator.generate_consolidated_report(payloads)
    assert isinstance(data_out, dict)
    assert "Code Review Report" in report_md
    assert (tmp_path / "reviews" / "test-session" / "findings.json").exists()
    assert (tmp_path / "reviews" / "test-session" / "review.md").exists()


def test_get_server_info_formatting() -> None:
    """Test server info formatting under different LLM client configurations."""
    orchestrator = ReviewPipelineOrchestrator(session_id="test-info")

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
    monkeypatch.setattr("devops_cli.ai.review.pipeline.CONST_DATA_DIR", tmp_path)
    orchestrator = ReviewPipelineOrchestrator(session_id="test-path-matching")

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


def test_deterministic_pre_verification_syntax_hallucination(tmp_path: Path) -> None:
    """_deterministic_pre_verification invalidates false syntax errors on valid python files."""
    from devops_cli.ai.review.verification import _deterministic_pre_verification
    from devops_cli.ai.review_schema import Finding

    valid_py = tmp_path / "valid.py"
    valid_py.write_text(
        "def test():\n    try:\n        pass\n    except (OSError, ValueError):\n        pass\n",
        encoding="utf-8",
    )

    finding = Finding(
        severity="CRITICAL",
        location="valid.py:1-5",
        title="Syntax error in except clause",
        description="Except clause uses invalid syntax",
        fix="Use tuple",
    )
    result = _deterministic_pre_verification(finding, repo_root=tmp_path)
    assert result.verified is False
    assert result.status == "INVALIDATED"
    assert "Syntax validation passed" in str(result.invalidation_reason)


def test_deterministic_pre_verification_template_placeholder(tmp_path: Path) -> None:
    """_deterministic_pre_verification marks example secret templates as mitigated."""
    from devops_cli.ai.review.verification import _deterministic_pre_verification
    from devops_cli.ai.review_schema import Finding

    finding = Finding(
        severity="HIGH",
        location="config.example.yaml:12",
        title="Plaintext secret token detected",
        description="YOUR_TOKEN placeholder in config.example.yaml",
        fix="Use keyring",
    )
    result = _deterministic_pre_verification(finding, repo_root=tmp_path)
    assert result.verified is False
    assert result.mitigated is True
    assert result.status == "MITIGATED"


def test_consolidated_report_findings_sorted_by_severity_and_confidence(
    tmp_path: Path, monkeypatch
) -> None:
    """Findings in report_md and findings.json must be sorted by severity and confidence."""
    from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding

    monkeypatch.setattr("devops_cli.ai.review.pipeline.CONST_DATA_DIR", tmp_path)
    orchestrator = ReviewPipelineOrchestrator(session_id="sort-test-session")

    f_low = SavedFinding(
        severity="LOW",
        title="Low Finding High Confidence",
        location="src/low.py:1",
        confidence_score=0.99,
        verified=True,
    )
    f_med_high_conf = SavedFinding(
        severity="MEDIUM",
        title="Medium Finding High Confidence",
        location="src/med1.py:1",
        confidence_score=0.95,
        verified=True,
    )
    f_med_low_conf = SavedFinding(
        severity="MEDIUM",
        title="Medium Finding Low Confidence",
        location="src/med2.py:1",
        confidence_score=0.70,
        verified=True,
    )
    f_crit_low_conf = SavedFinding(
        severity="CRITICAL",
        title="Critical Finding Lower Confidence",
        location="src/crit2.py:1",
        confidence_score=0.85,
        verified=True,
    )
    f_crit_high_conf = SavedFinding(
        severity="CRITICAL",
        title="Critical Finding Higher Confidence",
        location="src/crit1.py:1",
        confidence_score=0.98,
        verified=True,
    )
    f_high = SavedFinding(
        severity="HIGH",
        title="High Finding",
        location="src/high.py:1",
        confidence_score=0.90,
        verified=True,
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


def test_consolidate_duplicate_findings_across_personas(tmp_path: Path, monkeypatch) -> None:
    """Duplicate findings across personas should be merged, retaining highest severity."""
    from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding

    monkeypatch.setattr("devops_cli.ai.review.pipeline.CONST_DATA_DIR", tmp_path)
    orchestrator = ReviewPipelineOrchestrator(session_id="dedup-test-session")

    # devsecops reports High severity finding
    f_secops = SavedFinding(
        severity="HIGH",
        title="Insecure subprocess execution",
        location="src/k8s.py:42-50",
        confidence_score=0.90,
        description="Subprocess invocation without sanitization",
        fix="Use run_subprocess with check=True",
        persona="devsecops",
        persona_title="Security Engineer",
        verified=True,
    )

    # auditor reports Medium severity finding for overlapping lines with similar title
    f_auditor = SavedFinding(
        severity="MEDIUM",
        title="Insecure subprocess execution call",
        location="src/k8s.py:45",
        confidence_score=0.85,
        description="Subprocess call lacks execution audit logging",
        fix="Add audit logging wrapper",
        persona="auditor",
        persona_title="Compliance Auditor",
        verified=False,
    )

    # qa reports distinct finding in another function
    f_qa = SavedFinding(
        severity="LOW",
        title="Missing unit test edge case",
        location="src/k8s.py:120",
        confidence_score=0.95,
        description="Timeout error case is uncovered",
        fix="Add test_timeout unit test",
        persona="qa",
        persona_title="QA Engineer",
        verified=True,
    )

    payload = FileReviewPayload(
        file_path="src/k8s.py",
        findings=[f_secops, f_auditor, f_qa],
    )

    data_out, report_md = orchestrator.generate_consolidated_report([payload])

    # 3 raw findings should be consolidated into 2 unique findings
    findings = data_out["findings"]
    assert len(findings) == 2

    # The merged finding should take highest severity (HIGH) and merged personas
    merged_finding = next(f for f in findings if "subprocess" in f["title"].lower())
    assert merged_finding["severity"] == "HIGH"
    assert merged_finding["confidence_score"] == 0.90
    assert "devsecops" in merged_finding["persona"]
    assert "auditor" in merged_finding["persona"]
    assert merged_finding["verified"] is True

    # Check report_md rendering
    assert "Insecure subprocess execution" in report_md
    assert "Security Engineer, Compliance Auditor" in report_md


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
    monkeypatch.setattr("devops_cli.config.constants.CONST_DATA_DIR", tmp_path / ".data")
    monkeypatch.setattr(
        "devops_cli.config.constants.CONST_REVIEWS_DATA_DIR", tmp_path / ".data" / "reviews"
    )

    orchestrator = ReviewPipelineOrchestrator(session_id="criteria-test", llm_client=MagicMock())

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

    orchestrator.execute_finding_reranking([payload])
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


def test_persona_and_persona_title_distinctness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that multi-persona reviews populate distinct short persona slug and full title."""
    monkeypatch.setattr("devops_cli.config.constants.CONST_DATA_DIR", tmp_path / ".data")
    monkeypatch.setattr(
        "devops_cli.config.constants.CONST_REVIEWS_DATA_DIR", tmp_path / ".data" / "reviews"
    )

    mock_client = MagicMock()
    # Mock pipeline result step
    step_mock = MagicMock()
    step_mock.backend_info = "mock-ollama"
    step_mock.agent_name = "NIST/PCI/SOC Auditor"
    step_mock.parsed_data = None
    step_mock.content = (
        '{"recommendation": "REQUEST CHANGES", "summary": "Audit issues", "findings": ['
        '{"severity": "LOW", "location": "task.yml:10", "title": "Missing validation", '
        '"description": "Fields lack validation", "fix": "Add validation", '
        '"confidence_score": 0.8, "verification_criteria": ["Missing block"], '
        '"invalidation_criteria": ["Block present"]}]}'
    )

    pipeline_result_mock = MagicMock()
    pipeline_result_mock.steps = [step_mock]

    with patch(
        "devops_cli.ai.agents.pipeline.MultiAgentPipeline.run",
        return_value=pipeline_result_mock,
    ):
        orchestrator = ReviewPipelineOrchestrator(session_id="persona-test", llm_client=mock_client)
        payload = FileReviewPayload(file_path="task.yml")
        orchestrator.execute_multi_persona_review(
            [payload],
            diff_text_by_file={"task.yml": "diff content"},
            personas=["auditor"],
        )

        assert len(payload.findings) == 1
        finding = payload.findings[0]
        assert finding.persona == "auditor"
        assert finding.persona_title == "NIST/PCI/SOC Auditor"
        assert finding.persona != finding.persona_title
        assert "thoughts" in payload.ai_scratchpad
        assert len(payload.ai_scratchpad["thoughts"]) > 0


def test_ai_scratchpad_thoughts_collection_across_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that thoughts and LLM reasoning are accumulated into ai_scratchpad.thoughts."""
    monkeypatch.setattr("devops_cli.config.constants.CONST_DATA_DIR", tmp_path / ".data")
    monkeypatch.setattr(
        "devops_cli.config.constants.CONST_REVIEWS_DATA_DIR", tmp_path / ".data" / "reviews"
    )

    mock_client = MagicMock()
    step_mock = MagicMock()
    step_mock.backend_info = "mock-ollama"
    step_mock.agent_name = "Principal DevSecOps Engineer"
    step_mock.parsed_data = None
    step_mock.thoughts = ["Analyzing potential command injection vector in auth handler"]
    step_mock.content = (
        "<think>Found unescaped user input passed to subshell</think>"
        '{"recommendation": "REQUEST CHANGES", "summary": "Security flaw", "findings": ['
        '{"severity": "HIGH", "location": "auth.py:12", "title": "Command injection", '
        '"description": "Unescaped input", "fix": "Use shlex.quote", '
        '"confidence_score": 0.9, "verification_criteria": ["os.system call with raw var"], '
        '"invalidation_criteria": ["Input sanitized"]}]}'
    )

    pipeline_result_mock = MagicMock()
    pipeline_result_mock.steps = [step_mock]

    with patch(
        "devops_cli.ai.agents.pipeline.MultiAgentPipeline.run",
        return_value=pipeline_result_mock,
    ):
        orchestrator = ReviewPipelineOrchestrator(
            session_id="thoughts-test", llm_client=mock_client
        )
        payload = FileReviewPayload(file_path="src/auth.py")
        orchestrator.execute_multi_persona_review(
            [payload],
            diff_text_by_file={"src/auth.py": "diff"},
            personas=["devsecops"],
        )

        thoughts = payload.ai_scratchpad.get("thoughts", [])
        assert any("Analyzing potential command injection" in t for t in thoughts)
        assert any("Evaluated src/auth.py" in t for t in thoughts)

        # Stage 5 reranking appends stage thoughts
        orchestrator.execute_finding_reranking([payload])
        reranked_thoughts = payload.ai_scratchpad.get("thoughts", [])
        assert any("[Stage 5 Re-ranking]" in t for t in reranked_thoughts)


def test_generate_consolidated_report_with_intelligence_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that dependencies and network references with security status are
    rendered in review report.
    """
    monkeypatch.setattr("devops_cli.config.constants.CONST_DATA_DIR", tmp_path / ".data")
    monkeypatch.setattr(
        "devops_cli.config.constants.CONST_REVIEWS_DATA_DIR", tmp_path / ".data" / "reviews"
    )

    from devops_cli.models.vulnerability import DependencySpec, NetworkReference

    orchestrator = ReviewPipelineOrchestrator(
        session_id="intel-tables-test", llm_client=MagicMock()
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
                target="api.example-corp.com",
                reference_type="domain",
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

    assert "## External Dependencies (OSV.dev & NVD)" in report_md
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
        "| `api.example-corp.com` | domain | External | ✓ Safe / Low Risk | `src/main.py:15` |"
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
    monkeypatch.setattr("devops_cli.config.constants.CONST_DATA_DIR", tmp_path / ".data")
    monkeypatch.setattr(
        "devops_cli.config.constants.CONST_REVIEWS_DATA_DIR", tmp_path / ".data" / "reviews"
    )

    orchestrator = ReviewPipelineOrchestrator(
        session_id="summary-output-test", llm_client=MagicMock()
    )
    finding = SavedFinding(
        severity="HIGH",
        location="src/auth.py:42",
        title="Hardcoded Credential",
        description="Found hardcoded secret key in auth module",
        status="VERIFIED",
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
    assert "External Dependencies Security Audit" in captured
    assert "Network References & Endpoints Security Audit" in captured
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
    monkeypatch.setattr("devops_cli.config.constants.CONST_DATA_DIR", tmp_path / ".data")
    monkeypatch.setattr(
        "devops_cli.config.constants.CONST_REVIEWS_DATA_DIR", tmp_path / ".data" / "reviews"
    )

    orchestrator = ReviewPipelineOrchestrator(
        session_id="clean-summary-test", llm_client=MagicMock()
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
    monkeypatch.setattr("devops_cli.config.constants.CONST_DATA_DIR", tmp_path / ".data")
    monkeypatch.setattr(
        "devops_cli.config.constants.CONST_REVIEWS_DATA_DIR", tmp_path / ".data" / "reviews"
    )

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
                persona="devsecops",
                persona_title="Principal DevSecOps Engineer",
                reportable=True,
            )
        ],
        external_dependencies=[],
        network_references=[],
    )

    data_out, report_md = orchestrator.generate_consolidated_report([valid_payload])
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
