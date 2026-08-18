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


def test_validate_segment_findings_preserves_reason_and_confidence() -> None:
    """_validate_segment_findings updates invalidation_reason and confidence_score."""
    import json

    from devops_cli.ai.review.verification import _validate_segment_findings
    from devops_cli.ai.review_schema import Finding, ReviewResult

    finding = Finding(
        title="Sample Finding",
        description="Sample Description",
        severity="HIGH",
        location="src/test.py:10-15",
        verified=True,
    )
    result = ReviewResult(findings=[finding])

    mock_client = MagicMock()
    mock_client.chat.return_value = json.dumps(
        [
            {
                "verified": False,
                "mitigated": False,
                "severity": "LOW",
                "location": "src/test.py:10-15",
                "confidence_score": 0.95,
                "reason": "Speculative assertion on internal wrapper.",
            }
        ]
    )

    validated_result, _, _ = _validate_segment_findings(
        result=result,
        all_segments=["### File: src/test.py\n```python\nprint('hello')\n```"],
        client=mock_client,
    )

    assert len(validated_result.findings) == 1
    vf = validated_result.findings[0]
    assert vf.verified is False
    assert vf.status == "UNVERIFIED"
    assert vf.invalidation_reason == "Speculative assertion on internal wrapper."
    assert vf.confidence_score == 0.95


def test_finding_sort_key_multi_tier_ordering() -> None:
    """Findings are sorted by severity, exploitability, and verification status."""
    from devops_cli.ai.review_schema import Finding, ReviewResult

    f_crit_low_unver = Finding(
        title="Crit Low Unverified",
        severity="CRITICAL",
        exploitability="LOW",
        status="UNVERIFIED",
        location="a.py:1",
    )
    f_crit_high_ver = Finding(
        title="Crit High Verified",
        severity="CRITICAL",
        exploitability="HIGH",
        status="VERIFIED",
        location="a.py:2",
    )
    f_crit_high_unver = Finding(
        title="Crit High Unverified",
        severity="CRITICAL",
        exploitability="HIGH",
        status="UNVERIFIED",
        location="a.py:3",
    )
    f_high_high_ver = Finding(
        title="High High Verified",
        severity="HIGH",
        exploitability="HIGH",
        status="VERIFIED",
        location="b.py:1",
    )
    f_med_high_ver = Finding(
        title="Med High Verified",
        severity="MEDIUM",
        exploitability="HIGH",
        status="VERIFIED",
        location="c.py:1",
    )
    f_med_med_mit = Finding(
        title="Med Med Mitigated",
        severity="MEDIUM",
        exploitability="MEDIUM",
        status="MITIGATED",
        location="c.py:2",
    )
    f_med_med_inval = Finding(
        title="Med Med Invalidated",
        severity="MEDIUM",
        exploitability="MEDIUM",
        status="INVALIDATED",
        location="c.py:3",
    )

    review = ReviewResult(
        findings=[
            f_med_med_inval,
            f_high_high_ver,
            f_med_med_mit,
            f_crit_low_unver,
            f_crit_high_unver,
            f_crit_high_ver,
            f_med_high_ver,
        ]
    )

    sorted_titles = [f.title for f in review.sorted_findings]
    assert sorted_titles == [
        "Crit High Verified",
        "Crit High Unverified",
        "Crit Low Unverified",
        "High High Verified",
        "Med High Verified",
        "Med Med Mitigated",
        "Med Med Invalidated",
    ]


def test_payload_sorted_findings_property() -> None:
    """ReviewSessionPayload and FileReviewPayload expose sorted_findings."""
    from devops_cli.ai.review_schema import FileReviewPayload, ReviewSessionPayload, SavedFinding

    f1 = SavedFinding(
        title="Issue 1",
        severity="LOW",
        exploitability="LOW",
        status="VERIFIED",
        location="x.py:1",
    )
    f2 = SavedFinding(
        title="Issue 2",
        severity="CRITICAL",
        exploitability="HIGH",
        status="VERIFIED",
        location="x.py:2",
    )

    session_payload = ReviewSessionPayload(findings=[f1, f2])
    assert session_payload.sorted_findings[0].title == "Issue 2"
    assert session_payload.sorted_findings[1].title == "Issue 1"

    file_payload = FileReviewPayload(file_path="x.py", findings=[f1, f2])
    assert file_payload.sorted_findings[0].title == "Issue 2"
    assert file_payload.sorted_findings[1].title == "Issue 1"
