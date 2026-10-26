"""Unit tests for devops ai analyze command group and metadata generation."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.analyze.outlines import analyze_single_file
from devops_cli.ai.analyze.scanner import (
    detect_language,
    sanitize_reference,
)
from devops_cli.commands.analyze import (
    app as analyze_app,
)
from devops_cli.main import app
from devops_cli.models.ai import AnalysisMetadata, FileAnalysisMeta
from devops_cli.models.git import ChangedFile
from tests.support.fakes.github import (
    github_json,
    pull_request_file_payload,
    pull_request_payload,
    route_pull_request,
)
from tests.support.github_identity import fail_the_github_lookup
from tests.support.paths import FIXTURES

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

pytestmark = pytest.mark.usefixtures("mock_keyring")

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


@pytest.mark.parametrize(
    ("filename", "content", "expected"),
    [
        ("format.cc", None, "cpp"),
        ("format.cpp", None, "cpp"),
        ("format.cxx", None, "cpp"),
        ("format.c++", None, "cpp"),
        ("format.hh", None, "cpp"),
        ("format.hpp", None, "cpp"),
        ("format.hxx", None, "cpp"),
        ("format.c", None, "c"),
        ("header.h", "int add(int a, int b);", "c"),
        ("header.h", "namespace my_ns { template <typename T> class Value {}; }", "cpp"),
        ("Dockerfile", None, "dockerfile"),
        ("Dockerfile.prod", None, "dockerfile"),
        ("containerfile", None, "dockerfile"),
        ("config.yaml", None, "yaml"),
        ("config.yml", None, "yaml"),
    ],
)
def test_detect_language_table_with_empty_mimetypes_database(
    filename: str,
    content: str | None,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify detect_language classifies C++, .h, Dockerfiles, and YAML with an empty mimetypes database."""
    monkeypatch.setattr("mimetypes.guess_type", lambda _: (None, None))
    assert detect_language(filename, content=content) == expected


def test_detect_language_helm_template_beside_chart_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify detect_language identifies .tpl inside a Helm chart and plaintext outside."""
    chart_dir = tmp_path / "chart"
    templates_dir = chart_dir / "templates"
    templates_dir.mkdir(parents=True)
    (chart_dir / "Chart.yaml").write_text("name: test\n", encoding="utf-8")
    tpl_file = templates_dir / "_helpers.tpl"
    tpl_file.write_text("{{/* Helper */}}", encoding="utf-8")

    outside_dir = tmp_path / "other"
    outside_dir.mkdir(parents=True)
    outside_tpl = outside_dir / "standalone.tpl"
    outside_tpl.write_text("template content", encoding="utf-8")

    assert detect_language(tpl_file) == "helm"
    assert detect_language(outside_tpl) == "plaintext"

    monkeypatch.setattr("mimetypes.guess_type", lambda _: (None, None))
    assert detect_language(tpl_file) == "helm"
    assert detect_language(outside_tpl) == "plaintext"


def test_detect_language_cpp_not_mislabeled_as_c_on_host_with_mimetypes() -> None:
    """Verify mimetypes text/x-c++src does not turn C++ extensions into C."""
    for ext in (".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx"):
        assert detect_language(f"test{ext}") == "cpp"


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
        result_update_all = runner.invoke(
            app, ["ai", "analyze", "path", str(src_dir), "--update-all"]
        )
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


def test_ai_analyze_branch_and_pr_execution(tmp_path: Path, github_api: GitHubApiFake) -> None:
    """Test analyze branch and pr with mocked git interactions and the GitHub API fake."""
    (tmp_path / ".git").mkdir()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    worker_file = src_dir / "worker.py"
    worker_file.write_text("def do_work(): pass\n", encoding="utf-8")
    route_pull_request(
        github_api,
        "org/repo",
        42,
        pull_request_payload(title="Add worker"),
        files=[pull_request_file_payload("src/worker.py")],
    )

    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch(
            "devops_cli.git.operations.list_branches", return_value=MagicMock(current="feat/worker")
        ),
        patch(
            "devops_cli.git.operations.list_changed_files",
            return_value=[ChangedFile(change_type="modified", path="src/worker.py")],
        ),
        patch("devops_cli.git.operations.resolve_merge_base", return_value="base-sha"),
        patch("devops_cli.git.operations.read_file_at_revision", return_value=None),
        patch("devops_cli.core.repo.get_repo_origin_name", return_value="org/repo"),
    ):
        res_branch = runner.invoke(analyze_app, ["branch", "feat/worker", "--no-enhanced"])
        assert res_branch.exit_code == 0

        res_branch_explain = runner.invoke(analyze_app, ["branch", "--explain"])
        assert res_branch_explain.exit_code == 0

        res_pr = runner.invoke(analyze_app, ["pr", "42", "--no-enhanced"])
        assert res_pr.exit_code == 0

        res_pr_explain = runner.invoke(analyze_app, ["pr", "42", "--explain"])
        assert res_pr_explain.exit_code == 0

    assert github_api.requested == [
        "GET https://api.github.com/repos/org/repo/pulls/42",
        "GET https://api.github.com/repos/org/repo/pulls/42/files?per_page=100",
    ]


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
    _doc, syms, imps = _analyze_python_ast(py_code)
    assert "CONST_API_KEY" in syms
    assert "external_pkg" in imps
    assert "internal_sub.helper" in imps

    # 4. _extract_file_dependencies for rust & unknown languages
    assert _extract_file_dependencies("const x = 1;", "python") == []
    assert _extract_file_dependencies("use tokio::sync;", "rust") == ["tokio"]
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
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    non_existent = repo_root / "does_not_exist"
    res_non = runner.invoke(analyze_app, ["path", str(non_existent)])
    assert res_non.exit_code == 1

    outside = tmp_path / "outside_dir"
    outside.mkdir()
    with patch("devops_cli.commands.analyze.find_repo_root", return_value=repo_root):
        res_out = runner.invoke(analyze_app, ["path", str(outside)])
        assert res_out.exit_code == 1


def test_analyze_pr_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github_api: GitHubApiFake
) -> None:
    """Verify devops analyze pr with no gh login, missing origin, and the GitHub API fake."""
    from devops_cli.config.settings import Settings

    # 1. No token from `gh auth token`
    empty_settings = Settings()
    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch("devops_cli.commands.analyze.load_settings", return_value=empty_settings),
        monkeypatch.context() as unauthenticated,
    ):
        fail_the_github_lookup(unauthenticated)
        res_no_token = runner.invoke(analyze_app, ["pr", "42"])
        assert (res_no_token.exit_code, "gh auth login" in res_no_token.output) == (1, True)

    # 2. Missing origin
    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch("devops_cli.commands.analyze.load_settings", return_value=empty_settings),
        patch("devops_cli.commands.analyze.get_repo_origin_name", return_value=None),
    ):
        res_no_origin = runner.invoke(analyze_app, ["pr", "42"])
        assert res_no_origin.exit_code == 1

    # 3. Successful PR analysis
    (tmp_path / ".git").mkdir(exist_ok=True)
    sample_file = tmp_path / "pr_mod.py"
    sample_file.write_text("def pr_func(): pass\n", encoding="utf-8")

    route_pull_request(
        github_api,
        "owner/repo",
        42,
        pull_request_payload(title="Add feature"),
        files=[pull_request_file_payload("pr_mod.py", additions=5, changes=5)],
    )

    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch("devops_cli.commands.analyze.load_settings", return_value=empty_settings),
        patch("devops_cli.commands.analyze.get_repo_origin_name", return_value="owner/repo"),
    ):
        res_pr_ok = runner.invoke(analyze_app, ["pr", "42", "--no-enhanced"])
        assert res_pr_ok.exit_code == 0


def test_analyze_pr_lists_the_title_and_the_files_of_every_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    git: Callable[..., None],
    github_api: GitHubApiFake,
    pin_github_session: str,
) -> None:
    """For the recorded pull request, whose second page of files GitHub links, the analysis holds
    the pull request's title and both changed files, with the token of the session on every read."""
    recorded = json.loads(
        (FIXTURES / "github" / "hello_world_pull_request.json").read_text(encoding="utf-8")
    )
    first, second = recorded["files_pages"]
    github_api.route(
        "GET", "/repos/octocat/Hello-World/pulls/158", github_json(recorded["pull_request"])
    )
    github_api.route(
        "GET",
        "/repos/octocat/Hello-World/pulls/158/files?per_page=100",
        github_json(first["body"], headers={"link": first["link"]}),
    )
    github_api.route(
        "GET",
        "/repositories/1296269/pulls/158/files?per_page=1&page=2",
        github_json(second["body"], headers={"link": second["link"]}),
    )
    root = tmp_path / "checkout"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "remote", "add", "origin", "https://github.com/octocat/Hello-World.git")
    monkeypatch.chdir(root)
    monkeypatch.setenv("DEVOPS_CLI_DATA_ANALYSIS_DIR", str(tmp_path / "analysis"))

    result = runner.invoke(analyze_app, ["pr", "158", "--no-enhanced"])

    saved = AnalysisMetadata.model_validate_json(
        (tmp_path / "analysis" / "pr-158-metadata.json").read_text(encoding="utf-8")
    )
    assert (
        result.exit_code,
        saved.project.title,
        [(meta.path, meta.change_type) for meta in saved.files],
        len(github_api.sent),
        {request.headers["authorization"] for request in github_api.sent},
    ) == (
        0,
        "checkout PR #158 analysis: Update and rename README to README.md. Also Added Bolding",
        [("README", "removed"), ("README.md", "added")],
        3,
        {f"token {pin_github_session}"},
    )


@pytest.mark.parametrize("unreadable", ["the pull request", "its files"])
def test_analyze_pr_ends_with_the_github_error_when_the_pull_request_cannot_be_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    git: Callable[..., None],
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    unreadable: str,
) -> None:
    """A 500 that outlasts the retries, on the pull request or on its files, ends the command with
    the session's message and status 1, and prints no traceback."""
    recorded = json.loads(
        (FIXTURES / "github" / "hello_world_pull_request.json").read_text(encoding="utf-8")
    )
    pull = "/repos/octocat/Hello-World/pulls/158"
    failure = github_json({"message": "Server Error"}, status=500)
    if unreadable == "the pull request":
        github_api.route("GET", pull, failure)
    else:
        github_api.route("GET", pull, github_json(recorded["pull_request"]))
        github_api.route("GET", f"{pull}/files?per_page=100", failure)
    root = tmp_path / "checkout"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "remote", "add", "origin", "https://github.com/octocat/Hello-World.git")
    monkeypatch.chdir(root)

    result = cli("ai", "analyze", "pr", "158", "--no-enhanced")

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "(HTTP 500)" in result.output
    assert "Traceback" not in result.output


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


def test_evict_excess_analysis_files(tmp_path: Path) -> None:
    """Verify _evict_excess_analysis_files prunes oldest metadata files exceeding max_files."""
    from devops_cli.ai.analyze.cache import _evict_excess_analysis_files

    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()

    for i in range(5):
        f = analysis_dir / f"branch-feat-{i}-metadata.json"
        f.write_text("{}", encoding="utf-8")
        os.utime(f, (1000.0 + i * 10, 1000.0 + i * 10))

    pruned = _evict_excess_analysis_files(analysis_dir, max_files=3)
    remaining = sorted(p.name for p in analysis_dir.glob("*-metadata.json"))

    assert (pruned, remaining) == (
        2,
        [
            "branch-feat-2-metadata.json",
            "branch-feat-3-metadata.json",
            "branch-feat-4-metadata.json",
        ],
    )


def test_load_cached_analysis_and_file_metas(tmp_path: Path) -> None:
    """Verify load_cached_analysis and _load_file_analysis_metas."""
    from devops_cli.ai.analyze.cache import _load_file_analysis_metas, load_cached_analysis
    from devops_cli.config.settings import Settings
    from devops_cli.models.ai import AnalysisMetadata, FileAnalysisMeta, ProjectAnalysisMeta

    assert (load_cached_analysis(tmp_path), _load_file_analysis_metas(repo_root=tmp_path)) == (
        None,
        {},
    )

    analysis_dir = tmp_path / ".data" / "analysis"
    analysis_dir.mkdir(parents=True)
    custom_settings = Settings()
    custom_settings.data.analysis_dir = analysis_dir
    with patch("devops_cli.config.settings.load_settings", return_value=custom_settings):
        assert load_cached_analysis(tmp_path) is None

        bad_file = analysis_dir / "bad-metadata.json"
        bad_file.write_text("not json", encoding="utf-8")
        assert load_cached_analysis(tmp_path) is None
        bad_file.unlink()

        file_meta = FileAnalysisMeta(
            path="src/main.py", language="python", line_count=10, char_count=100
        )
        proj_meta = ProjectAnalysisMeta(
            title="Test",
            target_type="path",
            target_reference="src",
            timestamp="2026-09-19T00:00:00Z",
            total_files=1,
            total_lines=10,
            total_chars=100,
            languages=["python"],
            primary_purpose="Testing",
            key_symbols=[],
            dependencies=[],
        )
        payload = AnalysisMetadata(project=proj_meta, files=[file_meta])
        good_file = analysis_dir / "path-src-metadata.json"
        good_file.write_text(payload.model_dump_json(), encoding="utf-8")
        os.utime(good_file, (2000.0, 2000.0))

        loaded = load_cached_analysis(tmp_path)
        all_metas = _load_file_analysis_metas(repo_root=tmp_path)
        filtered_metas = _load_file_analysis_metas(
            files=["src/main.py", "nonexistent.py"], repo_root=tmp_path
        )

        assert (
            loaded is not None,
            len(all_metas),
            "src/main.py" in filtered_metas,
            "nonexistent.py" in filtered_metas,
        ) == (True, 1, True, False)


def test_compute_symbol_delta() -> None:
    """Verify symbol delta computation detects added, removed, and retained symbols."""
    from devops_cli.ai.analyze.symbols import compute_symbol_delta

    base_code = """
def kept_func(): pass
def removed_func(): pass
class RetainedClass:
    def old_method(self): pass
"""
    head_code = """
def kept_func(): pass
def added_func(): pass
class RetainedClass:
    def new_method(self): pass
"""
    added, removed, retained = compute_symbol_delta(base_code, head_code)
    assert (
        "added_func" in added,
        "RetainedClass.new_method" in added,
        "removed_func" in removed,
        "RetainedClass.old_method" in removed,
        "kept_func" in retained,
        "RetainedClass" in retained,
    ) == (True, True, True, True, True, True)


def test_python_source_symbols_name_declarations_assignments_and_methods() -> None:
    """Verify a Python source's symbols are its top-level functions, classes and assigned names,
    and each method both bare and by class, and that source which does not parse has none."""
    from devops_cli.ai.analyze.symbols import extract_python_source_symbols

    source = (
        '__all__ = ["fetch"]\n'
        "LIMIT = 1\n"
        "first = second = 2\n"
        "class Client:\n"
        "    def send(self): ...\n"
        "async def fetch(): ...\n"
        "def helper(): ...\n"
    )

    assert (
        extract_python_source_symbols(source),
        extract_python_source_symbols("def (:\n"),
        extract_python_source_symbols(None),
    ) == (
        {
            "__all__",
            "LIMIT",
            "first",
            "second",
            "Client",
            "send",
            "Client.send",
            "fetch",
            "helper",
        },
        set(),
        set(),
    )


def test_apply_symbol_delta_to_meta(tmp_path: Path) -> None:
    """Verify that _apply_symbol_delta_to_meta lists an added file's symbols as added."""
    from devops_cli.commands.analyze import _apply_symbol_delta_to_meta

    meta = FileAnalysisMeta(path="test_mod.py")
    head_code = "def new_feature(): pass\n"

    updated = _apply_symbol_delta_to_meta(
        meta=meta,
        repo=tmp_path,
        base_revision="main",
        change=ChangedFile(change_type="added", path="test_mod.py"),
        head_content=head_code,
    )

    assert (
        "new_feature" in updated.symbols_added,
        len(updated.symbols_removed),
        len(updated.symbols_retained),
    ) == (True, 0, 0)


def test_apply_symbol_delta_reports_a_symbol_removed_since_the_base(
    symbol_removal_repo: Path,
) -> None:
    """A symbol the branch removes lands in symbols_removed, and a kept one is not added (#787)."""
    from devops_cli.commands.analyze import _apply_symbol_delta_to_meta

    head = (symbol_removal_repo / "mod.py").read_text(encoding="utf-8")
    updated = _apply_symbol_delta_to_meta(
        meta=FileAnalysisMeta(path="mod.py"),
        repo=symbol_removal_repo,
        base_revision="main",
        change=ChangedFile(change_type="modified", path="mod.py"),
        head_content=head,
    )

    assert (updated.symbols_removed, updated.symbols_added, updated.symbols_retained) == (
        ["gone"],
        ["added"],
        ["kept"],
    )


def test_analyze_branch_compares_a_renamed_file_with_its_old_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rename is analysed at its new path and its base read at the old one, at the merge base.

    The plain `--name-status` parser kept `old_name.py<TAB>new_name.py` as one path, which does not
    exist, and recorded the renamed file as deleted (#593).
    """
    monkeypatch.setenv("DEVOPS_CLI_DATA_ANALYSIS_DIR", str(tmp_path / "analysis"))
    (tmp_path / ".git").mkdir()
    (tmp_path / "new_name.py").write_text("def moved(): pass\ndef fresh(): pass\n", "utf-8")
    reads: list[tuple[str, str]] = []

    def read(repo: Path, revision: str, rel_path: str) -> str:
        reads.append((revision, rel_path))
        return "def moved(): pass\ndef dropped(): pass\n"

    renamed = ChangedFile(change_type="renamed", path="new_name.py", old_path="old_name.py")
    with (
        patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path),
        patch("devops_cli.git.operations.resolve_merge_base", return_value="merge-sha"),
        patch("devops_cli.git.operations.list_changed_files", return_value=[renamed]) as lister,
        patch("devops_cli.git.operations.read_file_at_revision", side_effect=read),
    ):
        result = runner.invoke(
            analyze_app, ["branch", "feature", "--base", "main", "--no-enhanced"]
        )

    saved = AnalysisMetadata.model_validate_json(
        next((tmp_path / "analysis").glob("branch-*-metadata.json")).read_text("utf-8")
    )
    assert (
        result.exit_code,
        lister.call_args.args[1:],
        reads,
        [
            (m.path, m.change_type, m.symbols_added, m.symbols_removed, m.symbols_retained)
            for m in saved.files
        ],
    ) == (
        0,
        ("merge-sha", "feature"),
        [("merge-sha", "old_name.py")],
        [("new_name.py", "renamed", ["fresh"], ["dropped"], ["moved"])],
    )


def test_analyze_pr_dry_run_previews_and_contacts_no_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`analyze pr --dry-run` renders the preview and opens no GitHub session."""
    (tmp_path / ".git").mkdir(exist_ok=True)
    monkeypatch.chdir(tmp_path)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dry run contacted GitHub")

    monkeypatch.setattr("devops_cli.github.session.get_github_session", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("subprocess.Popen", forbidden)
    with patch("devops_cli.commands.analyze.find_repo_root", return_value=tmp_path):
        result = runner.invoke(analyze_app, ["pr", "42", "--dry-run"])
        monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
        env_result = runner.invoke(analyze_app, ["pr", "42"])

    assert result.exit_code == 0, result.output
    assert "devops ai analyze pr" in result.output
    assert "42" in result.output
    assert env_result.exit_code == 0, env_result.output
    assert not (tmp_path / ".data" / "analysis").exists()
