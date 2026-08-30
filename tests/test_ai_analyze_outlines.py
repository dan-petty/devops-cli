"""Unit tests for AI analyze outlines and pseudocode extraction."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest.mock import MagicMock

from devops_cli.ai.analyze.outlines import (
    _calculate_complexity_score,
    _extract_class_pseudocode,
    _extract_function_pseudocode,
    _extract_json_pseudocode,
    _extract_python_pseudocode_outline,
    _get_last_updated,
    _is_import_or_docstring_line,
    analyze_single_file,
)


def test_outline_extractor(tmp_path: Path) -> None:
    """Verify python and json pseudocode outline extraction and complexity scoring."""
    py_code = """
class MyService:
    \"\"\"Service class docstring.\"\"\"
    def __init__(self, name: str) -> None:
        self.name = name

    def process(self, data: dict) -> bool:
        return True

def standalone_helper(x: int) -> int:
    return x * 2
"""
    py_file = tmp_path / "service.py"
    py_file.write_text(py_code, encoding="utf-8")

    py_outline = _extract_python_pseudocode_outline(py_code)
    assert len(py_outline) > 0

    json_code = '{"name": "test", "version": "1.0.0", "dependencies": {"pkg": "1.0"}}'
    json_outline = _extract_json_pseudocode(json_code)
    assert json_outline is not None
    assert len(json_outline) > 0

    complexity = _calculate_complexity_score(py_code, 15, ["MyService", "standalone_helper"])
    assert complexity in ("Low", "Medium", "High")

    meta = analyze_single_file(
        rel_path="service.py",
        content=py_code,
        size_bytes=len(py_code),
        repo_root=tmp_path,
        ai_client=None,
        enhanced=False,
    )
    assert meta.path == "service.py"
    assert meta.language == "python"


def test_outline_scoring_and_ast_helpers(tmp_path: Path) -> None:
    """Verify docstring line filter and AST extraction."""
    # 1. Docstring & import line detector
    assert _is_import_or_docstring_line("import os") is True
    assert _is_import_or_docstring_line("from pathlib import Path") is True
    assert _is_import_or_docstring_line('"""Docstring"""') is True
    assert _is_import_or_docstring_line("Here is the pseudocode:") is True
    assert _is_import_or_docstring_line("x = 42") is False

    # 3. AST pseudocode extraction
    tree = ast.parse(
        "class BaseService:\n    def execute(self, a, b, c, d) -> bool:\n        return True\n"
    )
    cls_node = tree.body[0]
    assert isinstance(cls_node, ast.ClassDef)
    cls_lines = _extract_class_pseudocode(cls_node)
    assert len(cls_lines) >= 1
    assert "BaseService" in cls_lines[0]

    fn_node = cls_node.body[0]
    assert isinstance(fn_node, ast.FunctionDef)
    fn_lines = _extract_function_pseudocode(fn_node)
    assert len(fn_lines) >= 1
    assert "execute" in fn_lines[0]

    # 4. _get_last_updated
    f = tmp_path / "mod.py"
    f.write_text("code", encoding="utf-8")
    last_up = _get_last_updated("mod.py", repo_root=tmp_path)
    assert "T" in last_up


def test_pseudocode_generation_and_ai_enhancement(tmp_path: Path) -> None:
    """Verify shell, yaml, json pseudocode generation and AI enhancement flow."""
    from unittest.mock import MagicMock

    from devops_cli.ai.analyze.outlines import (
        _generate_ai_pseudocode,
        _generate_pseudocode,
        analyze_single_file,
    )

    # 1. Shell script pseudocode
    sh_content = "#!/bin/bash\n# Comment line\necho 'Deploying'\nkubectl apply -f manifest.yaml\n"
    sh_pseudo = _generate_pseudocode("deploy.sh", sh_content, "bash", [], "Deploy script")
    assert len(sh_pseudo) >= 2
    assert "echo 'Deploying'" in sh_pseudo[0]

    # 2. YAML pseudocode
    yaml_content = '{"kind": "Deployment", "apiVersion": "apps/v1", "replicas": 3}'
    yaml_pseudo = _generate_pseudocode("deploy.yaml", yaml_content, "yaml", [], "K8s Deployment")
    assert yaml_pseudo is not None
    assert len(yaml_pseudo) >= 1

    # 3. AI pseudocode generation
    mock_ai = MagicMock()
    mock_ai.chat_messages.return_value = (
        "1. Parse input args\n2. Execute workflow\n3. Return result"
    )
    ai_pseudo = _generate_ai_pseudocode("script.py", "print('hello')", "python", ["main"], mock_ai)
    assert ai_pseudo is not None
    assert len(ai_pseudo) == 3
    assert "Parse input args" in ai_pseudo[0]

    # 4. analyze_single_file with AI enhancement
    mock_enhanced_ai = MagicMock()
    mock_enhanced_ai.chat_messages.return_value = (
        '{"primary_purpose": "Authentication Service", "key_symbols": ["AuthManager"], '
        '"dependencies": ["jwt"], "pseudocode": ["1. Validate token", "2. Return claims"]}'
    )
    meta = analyze_single_file(
        rel_path="auth.py",
        content="class AuthManager: pass",
        size_bytes=23,
        repo_root=tmp_path,
        ai_client=mock_enhanced_ai,
        enhanced=True,
    )
    assert meta.path == "auth.py"
    assert meta.primary_purpose == "Authentication Service"
    assert "AuthManager" in meta.key_symbols


def test_outline_validation_and_enhancement_retries(tmp_path: Path) -> None:
    """Verify metadata validation error cases, complexity levels, and AI retry flow."""
    from unittest.mock import MagicMock

    from devops_cli.ai.analyze.outlines import (
        _calculate_complexity_score,
        _enhance_file_metadata_with_ai,
        _extract_json_pseudocode,
        _get_last_updated,
        _validate_enhanced_metadata,
    )

    # 1. _validate_enhanced_metadata error cases
    out, err = _validate_enhanced_metadata("not a dict", True, [])
    assert out is None and "JSON object" in str(err)

    out, err = _validate_enhanced_metadata({"primary_purpose": "hi"}, True, [])
    assert out is None and "too short" in str(err)

    out, err = _validate_enhanced_metadata(
        {"primary_purpose": "Valid Purpose", "confidence_score": 1.5}, True, []
    )
    assert out is None and "confidence_score" in str(err)

    out, err = _validate_enhanced_metadata(
        {"primary_purpose": "Valid Purpose", "quality_score": -0.5}, True, []
    )
    assert out is None and "quality_score" in str(err)

    # 2. Complexity tiers
    low_comp = _calculate_complexity_score("x = 1\n", 1, [])
    assert low_comp == "Low"

    med_code = "\n".join(
        ["if True: pass", "for i in range(10): pass", "try: pass\nexcept: pass"] * 4
    )
    med_comp = _calculate_complexity_score(med_code, 30, ["a", "b", "c", "d"])
    assert med_comp in ("Medium", "High")

    high_code = "\n".join(["if True: pass", "for i in range(10): pass"] * 25)
    high_comp = _calculate_complexity_score(high_code, 100, ["fn" + str(i) for i in range(20)])
    assert high_comp == "High"

    # 3. _get_last_updated path traversal and non-repo
    assert _get_last_updated("../traversal.py", repo_root=tmp_path) is not None
    assert _get_last_updated("/absolute/path.py", repo_root=tmp_path) is not None

    # 4. _extract_json_pseudocode with array
    json_arr = '[{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]'
    arr_pseudo = _extract_json_pseudocode(json_arr)
    assert arr_pseudo is not None
    assert len(arr_pseudo) == 2

    # 5. _enhance_file_metadata_with_ai retry loop
    mock_retry_ai = MagicMock()
    mock_retry_ai.chat_messages.side_effect = [
        "not json",
        '{"primary_purpose": "Recovered Purpose after retry", "key_symbols": ["Valid"]}',
    ]
    enhanced_res = _enhance_file_metadata_with_ai(
        "service.py", "def foo(): pass", "python", ["foo"], mock_retry_ai, max_retries=2
    )
    assert enhanced_res is not None
    assert enhanced_res.primary_purpose == "Recovered Purpose after retry"


def test_outline_async_and_multi_language(tmp_path: Path) -> None:
    """Verify async python outline, syntax error fallback, and multi-language file analysis."""
    from devops_cli.ai.analyze.outlines import (
        _extract_python_pseudocode_outline,
        analyze_single_file,
    )

    # 1. Async python outline
    async_py = "class AsyncWorker:\n    async def fetch_job(self, queue_id: str) -> dict:\n        return {'status': 'ok'}\n"
    async_outline = _extract_python_pseudocode_outline(async_py)
    assert any("fetch_job" in line for line in async_outline)

    # 2. Syntax error fallback
    bad_py = "def broken(x: int\n    return x\n"
    bad_outline = _extract_python_pseudocode_outline(bad_py)
    assert isinstance(bad_outline, list)

    # 3. analyze_single_file for YAML, Markdown, TOML
    yaml_meta = analyze_single_file(
        rel_path="config.yaml",
        content="apiVersion: v1\nkind: Service\n",
        size_bytes=30,
        change_type="existing",
        enhanced=False,
        repo_root=tmp_path,
    )
    assert yaml_meta.language == "yaml"

    md_meta = analyze_single_file(
        rel_path="README.md",
        content="# My Project\nDocumentation.\n",
        size_bytes=25,
        change_type="existing",
        enhanced=False,
        repo_root=tmp_path,
    )
    assert md_meta.language == "markdown"

    toml_meta = analyze_single_file(
        rel_path="pyproject.toml",
        content="[project]\nname = 'test'\n",
        size_bytes=25,
        change_type="existing",
        enhanced=False,
        repo_root=tmp_path,
    )
    assert toml_meta.language == "toml"


def test_outline_extended_branches(tmp_path: Path) -> None:
    """Verify RAG prompt formatting, AST unparse edge cases, and fallback pseudocode."""
    from unittest.mock import MagicMock, patch

    from devops_cli.ai.analyze.outlines import (
        _enhance_file_metadata_with_ai,
        _extract_class_pseudocode,
        _extract_function_pseudocode,
        _generate_ai_pseudocode,
        _generate_pseudocode,
        _get_last_updated,
    )

    # 1. _enhance_file_metadata_with_ai with RAG investigation success
    mock_rag_ctx = MagicMock()
    mock_rag_ctx.retrieved_chunks = [MagicMock(text="Chunk 1", similarity=0.9)]
    mock_ai = MagicMock()
    mock_ai.chat_messages.return_value = (
        '{"primary_purpose": "RAG Enhanced", "key_symbols": ["RagSym"], "confidence_score": 0.95}'
    )

    with (
        patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=mock_rag_ctx),
        patch(
            "devops_cli.ai.rag.investigator.format_rag_investigation_for_prompt",
            return_value="[RAG Context]",
        ),
    ):
        res_rag = _enhance_file_metadata_with_ai(
            "rag_file.py", "class RagSym: pass", "python", ["RagSym"], mock_ai
        )
        assert res_rag is not None
        assert res_rag.primary_purpose == "RAG Enhanced"

    # 2. _generate_ai_pseudocode with bullet prefixes
    mock_ai_pseudo = MagicMock()
    mock_ai_pseudo.chat_messages.return_value = (
        "* Step 1: Initialize client\n- Step 2: Validate token\n3. Return result\n"
    )
    pseudo = _generate_ai_pseudocode("auth.py", "code", "python", ["Auth"], mock_ai_pseudo)
    assert pseudo is not None
    assert len(pseudo) == 3
    assert pseudo[0] == "Step 1: Initialize client"

    # 3. _generate_pseudocode fallback for empty/plain text
    empty_pseudo = _generate_pseudocode("empty.txt", "", "text", [], "Empty")
    assert "empty.txt" in empty_pseudo[0]

    plain_pseudo = _generate_pseudocode(
        "custom.xyz", "custom syntax line 1\nline 2", "unknown", [], "Custom"
    )
    assert plain_pseudo == ["custom syntax line 1"]

    # 4. AST function and class unparse with multiple args & bases
    tree = ast.parse(
        "class Derived(Base1, Base2):\n"
        "    def compute(self, a, b, c, d, e) -> int:\n"
        "        if a > 0:\n"
        "            return b\n"
        "        for x in c:\n"
        "            d.append(x)\n"
    )
    cls_node = tree.body[0]
    assert isinstance(cls_node, ast.ClassDef)
    cls_lines = _extract_class_pseudocode(cls_node)
    assert any("Derived(Base1, Base2)" in line for line in cls_lines)

    fn_node = cls_node.body[0]
    assert isinstance(fn_node, ast.FunctionDef)
    fn_lines = _extract_function_pseudocode(fn_node)
    assert any("compute" in line and "..." in line for line in fn_lines)

    # 5. _get_last_updated with git log success vs stat mtime
    file_stat = tmp_path / "stat_file.py"
    file_stat.write_text("print('hello')", encoding="utf-8")
    with patch(
        "devops_cli.core.process.run_subprocess",
        return_value=MagicMock(returncode=0, stdout="2026-08-26T12:00:00+00:00\n"),
    ):
        ts_git = _get_last_updated("stat_file.py", repo_root=tmp_path)
        assert ts_git == "2026-08-26T12:00:00+00:00"


def test_outlines_extended_validation_and_shell(tmp_path: Path) -> None:
    """Verify _validate_enhanced_metadata error handling, shell pseudocode, and AI enhancement merge."""
    from devops_cli.ai.analyze.outlines import (
        _generate_pseudocode,
        _validate_enhanced_metadata,
        analyze_single_file,
    )

    # 1. _validate_enhanced_metadata
    res_none, err1 = _validate_enhanced_metadata("not a dict", has_content=True, static_symbols=[])
    assert res_none is None and "must be a JSON object" in err1

    res_none, err2 = _validate_enhanced_metadata(
        {"confidence_score": 1.5}, has_content=True, static_symbols=[]
    )
    assert res_none is None

    res_none, err3 = _validate_enhanced_metadata(
        {"primary_purpose": "tiny"}, has_content=True, static_symbols=[]
    )
    assert res_none is None and "too short" in err3

    valid_payload = {
        "primary_purpose": "Valid comprehensive purpose description",
        "key_symbols": ["SymA", "SymB"],
        "dependencies": ["httpx2"],
        "pseudocode": ["step 1", "step 2"],
        "complexity_score": "Medium",
        "confidence_score": 0.90,
        "quality_score": 0.85,
    }
    parsed, err_none = _validate_enhanced_metadata(
        valid_payload, has_content=True, static_symbols=["SymA"]
    )
    assert parsed is not None
    assert err_none is None
    assert parsed.complexity_score == "Medium"

    # 2. Shell pseudocode extraction
    sh_code = "#!/bin/bash\n# Comment\necho 'starting build'\nuv run pytest\n"
    sh_pseudo = _generate_pseudocode("script.sh", sh_code, "shell", [], "Build script")
    assert any("echo 'starting build'" in line for line in sh_pseudo)

    # 3. analyze_single_file with AI enhancement
    mock_ai = MagicMock()
    mock_ai.chat_messages.return_value = json.dumps(valid_payload)

    meta_ai = analyze_single_file(
        rel_path="src/service.py",
        content="class SymA: pass\n",
        size_bytes=20,
        enhanced=True,
        ai_client=mock_ai,
    )
    assert meta_ai.primary_purpose == "Valid comprehensive purpose description"
    assert "SymB" in meta_ai.key_symbols
    assert "httpx2" in meta_ai.dependencies
    assert meta_ai.complexity_score == "Medium"
    assert meta_ai.confidence_score == 0.90


def test_ai_pseudocode_and_mask_sensitive() -> None:
    """Verify AI pseudocode generation and sensitive data masking."""
    from devops_cli.ai.analyze.outlines import _generate_ai_pseudocode, _mask_sensitive_data

    # Sensitive data masking
    masked = _mask_sensitive_data("AWS_SECRET_KEY=AKIAIOSFODNN7EXAMPLE")
    assert "AKIAIOSFODNN7EXAMPLE" not in masked

    # AI pseudocode generation
    mock_ai = MagicMock()
    mock_ai.chat_messages.return_value = "1. Parse input configuration\n2. Execute batch pipeline"

    steps = _generate_ai_pseudocode("src/main.py", "def main(): pass", "python", ["main"], mock_ai)
    assert steps is not None
    assert "Parse input configuration" in steps[0]
    assert "Execute batch pipeline" in steps[1]
