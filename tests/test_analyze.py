"""Unit tests for devops ai analyze command group and metadata generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.analyze import (
    analyze_single_file,
    detect_language,
    sanitize_reference,
)
from devops_cli.commands.analyze import (
    app as analyze_app,
)
from devops_cli.main import app
from devops_cli.models.ai import AnalysisMetadata

runner = CliRunner()


def test_sanitize_reference_basic() -> None:
    """sanitize_reference converts slashes and special chars to hyphens."""
    assert sanitize_reference("feature/login-fix") == "feature-login-fix"
    assert sanitize_reference("refs/heads/main") == "refs-heads-main"
    assert sanitize_reference("42") == "42"
    assert sanitize_reference("src/devops_cli/ai") == "src-devops_cli-ai"


def test_sanitize_reference_dot(tmp_path: Path) -> None:
    """sanitize_reference for '.' returns repo directory name."""
    repo = tmp_path / "my-devops-repo"
    repo.mkdir()
    assert sanitize_reference(".", repo_root=repo) == "my-devops-repo"


def test_detect_language() -> None:
    """detect_language maps extensions, filenames, shebangs, and mimetypes."""
    assert detect_language("script.py") == "python"
    assert detect_language("app.ts") == "typescript"
    assert detect_language("config.yaml") == "yaml"
    assert detect_language("Dockerfile") == "dockerfile"
    assert detect_language("Jenkinsfile") == "jenkinsfile"
    assert detect_language("Makefile") == "makefile"
    assert detect_language("main.tf") == "hcl"
    assert detect_language("schema.proto") == "protobuf"
    assert (
        detect_language("custom_exec", content="#!/usr/bin/env python3\nprint('hello')") == "python"
    )
    assert detect_language("run.sh", content="#!/bin/bash\necho hi") == "shell"
    assert detect_language("unknown.xyz") == "plaintext"


def test_analyze_single_file() -> None:
    """analyze_single_file extracts lines, characters, symbols, and dependencies with submodules."""
    content = (
        '"""Module docstring."""\nimport httpx2\nfrom rich.console import Console\n'
        "from devops_cli.models.ai import FileAnalysisMeta\n\nclass MyWorker:\n    pass\n"
    )
    meta = analyze_single_file("src/worker.py", content, len(content.encode("utf-8")))

    assert meta.path == "src/worker.py"
    assert meta.language == "python"
    assert "MyWorker" in meta.key_symbols
    assert "httpx2" in meta.dependencies
    assert "rich.console" in meta.dependencies
    assert "devops_cli.models.ai" in meta.dependencies


def test_ai_analyze_path_command(tmp_path: Path) -> None:
    """devops ai analyze path creates .data/analysis/path-*-metadata.json."""
    (tmp_path / ".git").mkdir()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "sample.py"
    py_file.write_text('"""Sample module."""\ndef hello() -> str:\n    return "hi"\n')

    result = runner.invoke(app, ["ai", "analyze", "path", str(src_dir)])

    assert result.exit_code == 0
    analysis_file = tmp_path / ".data" / "analysis" / f"path-{tmp_path.name}-src-metadata.json"
    if not analysis_file.exists():
        files = list((tmp_path / ".data" / "analysis").glob("*.json"))
        assert len(files) == 1
        analysis_file = files[0]

    data = json.loads(analysis_file.read_text(encoding="utf-8"))
    payload = AnalysisMetadata.model_validate(data)

    assert payload.project.target_type == "path"
    assert payload.project.total_files >= 1
    assert any(f.path.endswith("sample.py") for f in payload.files)


def test_ai_analyze_branch_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """devops ai analyze branch dry run mode."""
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
    result = runner.invoke(analyze_app, ["branch", "main"])

    assert result.exit_code == 0


def test_ai_analyze_path_enhanced(tmp_path: Path) -> None:
    """devops ai analyze path defaults to enhanced metadata."""
    (tmp_path / ".git").mkdir()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "worker.py"
    py_file.write_text(
        '"""Worker module."""\ndef run_task() -> None:\n    if True:\n        pass\n'
    )

    # Invoked without flags — enhanced is default True
    result = runner.invoke(app, ["ai", "analyze", "path", str(src_dir)])

    assert result.exit_code == 0
    files = list((tmp_path / ".data" / "analysis").glob("*.json"))
    assert len(files) == 1
    analysis_file = files[0]

    data = json.loads(analysis_file.read_text(encoding="utf-8"))
    payload = AnalysisMetadata.model_validate(data)

    assert payload.project.enhanced is True
    assert payload.project.last_analyzed is not None
    file_meta = payload.files[0]
    assert file_meta.pseudocode is not None
    assert isinstance(file_meta.pseudocode, list)
    assert len(file_meta.pseudocode) > 0
    assert file_meta.last_updated is not None
    assert file_meta.last_analyzed is not None
    assert file_meta.complexity_score in ("Low", "Medium", "High")

    # Re-run analysis on unchanged file (incremental test)
    result_rerun = runner.invoke(app, ["ai", "analyze", "path", str(src_dir)])
    assert result_rerun.exit_code == 0
    data_rerun = json.loads(analysis_file.read_text(encoding="utf-8"))
    payload_rerun = AnalysisMetadata.model_validate(data_rerun)
    assert payload_rerun.files[0].pseudocode == file_meta.pseudocode
    assert payload_rerun.files[0].last_analyzed is not None

    # Re-run analysis with --update-all flag
    result_update_all = runner.invoke(app, ["ai", "analyze", "path", str(src_dir), "--update-all"])
    assert result_update_all.exit_code == 0
    data_update = json.loads(analysis_file.read_text(encoding="utf-8"))
    payload_update = AnalysisMetadata.model_validate(data_update)
    assert payload_update.files[0].last_analyzed is not None

    # Test explicit --no-enhanced flag
    result_no_enhanced = runner.invoke(
        app, ["ai", "analyze", "path", str(src_dir), "--no-enhanced", "--update-all"]
    )
    assert result_no_enhanced.exit_code == 0
    data_no_enhanced = json.loads(analysis_file.read_text(encoding="utf-8"))
    payload_no_enhanced = AnalysisMetadata.model_validate(data_no_enhanced)
    assert payload_no_enhanced.project.enhanced is False
    assert payload_no_enhanced.files[0].pseudocode is None


def test_enhanced_metadata_validation() -> None:
    """_validate_enhanced_metadata validates schemas, field types, and score ranges."""
    from devops_cli.ai.analyze.outlines import _validate_enhanced_metadata

    valid_dict = {
        "primary_purpose": "Processes incoming worker payloads.",
        "key_symbols": ["WorkerClass", "execute"],
        "dependencies": ["httpx2"],
        "pseudocode": ["execute(p): process(p)"],
        "complexity_score": "Medium",
        "confidence_score": 0.92,
        "quality_score": 0.88,
    }
    parsed, err = _validate_enhanced_metadata(
        valid_dict, has_content=True, static_symbols=["execute"]
    )
    assert err is None
    assert parsed is not None
    assert parsed.primary_purpose == "Processes incoming worker payloads."
    assert parsed.confidence_score == 0.92
    assert parsed.quality_score == 0.88

    # Out of range score
    invalid_score = dict(valid_dict, confidence_score=1.5)
    parsed_inv, err_inv = _validate_enhanced_metadata(
        invalid_score, has_content=True, static_symbols=[]
    )
    assert parsed_inv is None
    assert "confidence_score" in str(err_inv)


def test_ai_analyze_quality_and_confidence_scores(tmp_path: Path) -> None:
    """ai analyze populates quality_score and dynamic confidence_score on metadata."""
    (tmp_path / ".git").mkdir()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "worker.py"
    py_file.write_text('"""Worker module."""\ndef run_task() -> None:\n    pass\n')

    result = runner.invoke(app, ["ai", "analyze", "path", str(src_dir)])
    assert result.exit_code == 0

    files = list((tmp_path / ".data" / "analysis").glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    payload = AnalysisMetadata.model_validate(data)

    assert payload.project.confidence_score is not None
    assert 0.0 <= payload.project.confidence_score <= 1.0
    assert payload.project.quality_score is not None
    assert 0.0 <= payload.project.quality_score <= 1.0

    file_meta = payload.files[0]
    assert file_meta.confidence_score is not None
    assert 0.0 <= file_meta.confidence_score <= 1.0
    assert file_meta.quality_score is not None
    assert 0.0 <= file_meta.quality_score <= 1.0
