"""Unit tests for ReviewPipelineOrchestrator 6-stage code review pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from devops_cli.ai.review import ReviewPipelineOrchestrator
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
