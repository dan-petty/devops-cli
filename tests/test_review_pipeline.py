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
