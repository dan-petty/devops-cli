"""Unit tests for devops ai analyze command group and metadata generation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    with patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["ai", "analyze", "path", str(src_dir), "--no-enhanced"])

    assert result.exit_code == 0
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
    from devops_cli.ai.analyze.outlines import EnhancedMetadataOutput

    (tmp_path / ".git").mkdir()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "worker.py"
    py_file.write_text(
        '"""Worker module."""\ndef run_task() -> None:\n    if True:\n        pass\n'
    )

    mock_enhanced = EnhancedMetadataOutput(
        primary_purpose="Worker module for running tasks",
        key_symbols=["run_task"],
        dependencies=[],
        pseudocode=["run_task(): pass"],
        complexity_score="Low",
        confidence_score=0.95,
        quality_score=0.90,
    )

    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch(
            "devops_cli.ai.analyze.outlines._enhance_file_metadata_with_ai",
            return_value=mock_enhanced,
        ),
    ):
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
        assert payload_rerun.project.enhanced is True
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
    from devops_cli.ai.analyze.outlines import EnhancedMetadataOutput

    (tmp_path / ".git").mkdir()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "worker.py"
    py_file.write_text('"""Worker module."""\ndef run_task() -> None:\n    pass\n')

    mock_enhanced = EnhancedMetadataOutput(
        primary_purpose="Worker module for running tasks",
        key_symbols=["run_task"],
        dependencies=[],
        pseudocode=["run_task(): pass"],
        complexity_score="Low",
        confidence_score=0.92,
        quality_score=0.88,
    )

    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch(
            "devops_cli.ai.analyze.outlines._enhance_file_metadata_with_ai",
            return_value=mock_enhanced,
        ),
    ):
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


def test_ai_analyze_branch_and_pr_execution(tmp_path: Path) -> None:
    """Test analyze branch and pr with mocked git and github interactions."""
    (tmp_path / ".git").mkdir()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    worker_file = src_dir / "worker.py"
    worker_file.write_text("def do_work(): pass\n", encoding="utf-8")

    mock_diff_proc = subprocess.CompletedProcess(
        args=["git", "diff"],
        returncode=0,
        stdout="M\tsrc/worker.py\n",
        stderr="",
    )

    mock_pull = MagicMock()
    mock_pull.number = 42
    mock_pull.title = "Add worker"
    mock_pull.head_ref = "feat/worker"
    mock_pull.base_ref = "main"

    mock_file = MagicMock()
    mock_file.filename = "src/worker.py"
    mock_file.status = "modified"
    mock_file.patch = "@@ -1 +1 @@\n+def do_work(): pass\n"
    mock_pull.get_files.return_value = [mock_file]

    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch(
            "devops_cli.git.operations.list_branches", return_value=MagicMock(current="feat/worker")
        ),
        patch("devops_cli.core.process.run_subprocess", return_value=mock_diff_proc),
        patch("devops_cli.core.repo.get_repo_origin_name", return_value="org/repo"),
        patch("devops_cli.config.settings.get_github_token", return_value="mock_token"),
        patch("devops_cli.github.client.GitHubClient.get_pull", return_value=mock_pull),
    ):
        res_branch = runner.invoke(analyze_app, ["branch", "feat/worker", "--no-enhanced"])
        assert res_branch.exit_code == 0

        res_branch_explain = runner.invoke(analyze_app, ["branch", "--explain"])
        assert res_branch_explain.exit_code == 0

        res_pr = runner.invoke(analyze_app, ["pr", "42", "--no-enhanced"])
        assert res_pr.exit_code == 0

        res_pr_explain = runner.invoke(analyze_app, ["pr", "42", "--explain"])
        assert res_pr_explain.exit_code == 0


def test_scanner_ast_and_purpose_heuristics() -> None:
    """Verify AST parser, language extractors, and file purpose inference."""
    from devops_cli.ai.analyze.scanner import (
        _analyze_python_ast,
        _extract_file_dependencies,
        _extract_file_purpose,
        _extract_file_symbols,
    )

    # 1. Python AST parsing with syntax error
    doc, syms, imps = _analyze_python_ast("invalid syntax ((")
    assert doc is None
    assert syms == []
    assert imps == []

    # 2. Python AST with docstring and classes
    py_code = '"""Main entry point."""\nCONST_TIMEOUT = 30\nclass Engine:\n    pass\ndef run():\n    pass\nimport custom_lib\n'
    doc, syms, imps = _analyze_python_ast(py_code)
    assert doc == "Main entry point"
    assert "Engine" in syms
    assert "CONST_TIMEOUT" in syms
    assert "run" in syms
    assert "custom_lib" in imps

    # 3. Purpose inference
    assert "Python package configuration" in _extract_file_purpose("pyproject.toml", "", "toml", [])
    assert "Docker container" in _extract_file_purpose("Dockerfile", "", "dockerfile", [])
    assert "Documentation guide: API Architecture" in _extract_file_purpose(
        "docs/api.md", "# API Architecture\nGuide text", "markdown", []
    )

    # 4. Symbol extraction and dependency extraction
    syms_extracted = _extract_file_symbols(py_code, "python")
    assert "Engine" in syms_extracted

    ts_code = "import axios from 'axios';\nconst x = require('express');\n"
    deps = _extract_file_dependencies(ts_code, "typescript")
    assert "axios" in deps or "express" in deps


def test_scan_directory_and_extended_heuristics(tmp_path: Path) -> None:
    """Verify scan_directory file crawling and purpose / dependency heuristics across languages."""
    from devops_cli.ai.analyze.scanner import (
        _extract_file_dependencies,
        _extract_file_purpose,
        _extract_file_symbols,
        scan_directory,
    )

    # 1. Purpose inference for configuration files
    assert "exclusion rules" in _extract_file_purpose(".gitignore", "", "ignore", [])
    assert "Editor formatting" in _extract_file_purpose(".editorconfig", "", "ini", [])
    assert "Build target rules" in _extract_file_purpose("Makefile", "", "makefile", [])
    assert "Pin local Python" in _extract_file_purpose(".python-version", "", "text", [])
    assert "Implements core code logic" in _extract_file_purpose(
        "core.py", "", "python", ["ServiceWorker"]
    )

    # 2. Non-python regex symbol extraction
    js_code = "class WorkerPool {}\nfunction dispatchTask() {}\nconst CONST_MAX_WORKERS = 8;\n"
    js_syms = _extract_file_symbols(js_code, "javascript")
    assert "WorkerPool" in js_syms
    assert "CONST_MAX_WORKERS" in js_syms

    # 3. Non-python dependencies
    go_code = 'import "github.com/gin-gonic/gin"\nimport "fmt"\n'
    go_deps = _extract_file_dependencies(go_code, "go")
    assert any("gin" in d for d in go_deps)

    # 4. scan_directory
    src_dir = tmp_path / "pkg"
    src_dir.mkdir()
    (src_dir / "mod.py").write_text("class MyMod: pass\n", encoding="utf-8")
    (src_dir / "README.md").write_text("# My Module Guide\n", encoding="utf-8")

    results = scan_directory(src_dir)
    assert len(results) >= 2
    paths = [r.path for r in results]
    assert any("mod.py" in p for p in paths)


def test_scanner_extended_heuristics_and_sanitization(tmp_path: Path) -> None:
    """Verify sanitize_reference, shebang detection, AST constants, and language fallbacks."""
    from devops_cli.ai.analyze.scanner import (
        _analyze_python_ast,
        _extract_file_dependencies,
        _extract_file_purpose,
        detect_language,
        sanitize_reference,
    )

    # 1. sanitize_reference
    assert sanitize_reference("", repo_root=Path("/my/repo")) == "repo"
    assert sanitize_reference(".", repo_root=Path("/my/repo")) == "repo"
    assert sanitize_reference("feature/branch_name@1.0") == "feature-branch_name-1-0"
    long_ref = "a" * 200
    assert len(sanitize_reference(long_ref)) <= 128

    # 2. detect_language shebangs & manifest variants
    assert detect_language("Dockerfile.prod") == "dockerfile"
    assert detect_language("script", content="#!/usr/bin/env python3\nprint(1)") == "python"
    assert detect_language("runner", content="#!/bin/bash\necho 1") == "shell"
    assert detect_language("bundle", content="#!/usr/bin/env node\nconsole.log(1)") == "javascript"
    assert detect_language("main.tf") == "hcl"
    assert detect_language("main.rs") == "rust"
    assert detect_language("unknown.xyz123") == "plaintext"

    # 3. AST AnnAssign and imports filter
    py_code = """
CONST_API_KEY: str = "secret"
from external_pkg import client
import internal_sub.helper
"""
    doc, syms, imps = _analyze_python_ast(py_code)
    assert "CONST_API_KEY" in syms
    assert "external_pkg" in imps
    assert "internal_sub.helper" in imps

    # 4. _extract_file_dependencies for rust & unknown languages
    assert _extract_file_dependencies("const x = 1;", "python") == []
    assert _extract_file_dependencies("use tokio::sync;", "rust") == []
    assert _extract_file_dependencies("import fmt", "unknown_lang") == []

    # 5. _extract_file_purpose fallback stem
    assert "Helper Utils" in _extract_file_purpose("helper_utils.xyz", "", "unknown", [])


def test_analyze_explain_commands() -> None:
    """Verify analyze path, branch, and pr with --explain flag."""
    with patch("devops_cli.ai.explain.render_explanation") as mock_explain:
        res_path = runner.invoke(analyze_app, ["path", "src", "--explain"])
        assert res_path.exit_code == 0
        mock_explain.assert_called_with("analyze")

        mock_explain.reset_mock()
        res_branch = runner.invoke(analyze_app, ["branch", "main", "--explain"])
        assert res_branch.exit_code == 0
        mock_explain.assert_called_with("analyze")

        mock_explain.reset_mock()
        res_pr = runner.invoke(analyze_app, ["pr", "42", "--explain"])
        assert res_pr.exit_code == 0
        mock_explain.assert_called_with("analyze")


def test_analyze_path_errors(tmp_path: Path) -> None:
    """Verify analyze path errors on non-existent path and outside repo."""
    (tmp_path / ".git").mkdir()
    non_existent = tmp_path / "does_not_exist"
    res_non = runner.invoke(analyze_app, ["path", str(non_existent)])
    assert res_non.exit_code == 1

    outside = tmp_path.parent / "outside_dir"
    outside.mkdir(exist_ok=True)
    try:
        with patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path):
            res_out = runner.invoke(analyze_app, ["path", str(outside)])
            assert res_out.exit_code == 1
    finally:
        if outside.exists():
            outside.rmdir()


def test_analyze_pr_command(tmp_path: Path) -> None:
    """Verify devops analyze pr with missing token, missing origin, and mock client."""
    from devops_cli.config.settings import Settings

    # 1. Missing token
    empty_settings = Settings()
    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch("devops_cli.commands.analyze.load_settings", return_value=empty_settings),
        patch("devops_cli.commands.analyze.get_github_token", return_value=None),
    ):
        res_no_token = runner.invoke(analyze_app, ["pr", "42"])
        assert res_no_token.exit_code == 1

    # 2. Missing origin
    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch("devops_cli.commands.analyze.load_settings", return_value=empty_settings),
        patch("devops_cli.commands.analyze.get_github_token", return_value="token123"),
        patch("devops_cli.commands.analyze.get_repo_origin_name", return_value=None),
    ):
        res_no_origin = runner.invoke(analyze_app, ["pr", "42"])
        assert res_no_origin.exit_code == 1

    # 3. Successful PR analysis
    (tmp_path / ".git").mkdir(exist_ok=True)
    sample_file = tmp_path / "pr_mod.py"
    sample_file.write_text("def pr_func(): pass\n", encoding="utf-8")

    mock_pr_file = MagicMock()
    mock_pr_file.filename = "pr_mod.py"
    mock_pr_file.status = "modified"
    mock_pr_file.changes = 5
    mock_pr_file.additions = 5

    mock_pr = MagicMock()
    mock_pr.title = "Add feature"
    mock_pr.get_files.return_value = [mock_pr_file]

    mock_gh = MagicMock()
    mock_gh.get_pull.return_value = mock_pr

    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch("devops_cli.commands.analyze.load_settings", return_value=empty_settings),
        patch("devops_cli.commands.analyze.get_github_token", return_value="token123"),
        patch("devops_cli.commands.analyze.get_repo_origin_name", return_value="owner/repo"),
        patch("devops_cli.github.client.GitHubClient", return_value=mock_gh),
    ):
        res_pr_ok = runner.invoke(analyze_app, ["pr", "42", "--no-enhanced"])
        assert res_pr_ok.exit_code == 0


def test_scan_directory_and_heuristics(tmp_path: Path) -> None:
    """Verify scan_directory and language detection edge cases."""
    from devops_cli.ai.analyze.scanner import detect_language, scan_directory

    # Dockerfile prefix
    assert detect_language("Dockerfile.prod") == "dockerfile"
    # Shebangs
    assert (
        detect_language("run_node", content="#!/usr/bin/env node\nconsole.log(1);") == "javascript"
    )
    assert (
        detect_language("run_deno", content="#!/usr/bin/env deno\nconsole.log(1);") == "javascript"
    )

    # scan_directory
    (tmp_path / ".git").mkdir()
    py_mod = tmp_path / "mod.py"
    py_mod.write_text("def run(): pass\n", encoding="utf-8")

    results = scan_directory(tmp_path)
    assert len(results) >= 1
    assert any(r.path == "mod.py" for r in results)
