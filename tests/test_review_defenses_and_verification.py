"""Unit and integration tests for review defenses, path traversal guards, and hallucination verification."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.agents.tools import AgentTool
from devops_cli.ai.harness.filesystem import FileSystem
from devops_cli.ai.review.common_hallucinations import (
    CommonHallucinationEntry,
    HallucinationCategory,
    calculate_hallucination_similarity,
    verify_ground_truth_hallucination,
)
from devops_cli.ai.review.exporter import export_invalidated_feedback
from devops_cli.ai.review.sanitization import _mask_secrets_in_content
from devops_cli.ai.review.verification import _deterministic_pre_verification
from devops_cli.ai.review_schema import Finding
from devops_cli.commands.vault import _validate_vault_path
from devops_cli.core.repo import list_repo_files
from devops_cli.exceptions import SecurityError
from devops_cli.exceptions.vault import VaultConfigurationError


def test_list_repo_files_symlink_traversal_prevention(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    real_file = repo_dir / "valid.py"
    real_file.write_text("print('valid')\n", encoding="utf-8")

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.write_text("SUPER_SECRET", encoding="utf-8")

    # Create symlink inside repo pointing to outside file
    symlink_file = repo_dir / "symlink_escape.txt"
    try:
        symlink_file.symlink_to(secret_file)
    except OSError:
        pytest.skip("Symlinks not supported in environment")

    files = list_repo_files(repo_dir)
    assert real_file.resolve() in [f.resolve() for f in files]
    assert secret_file.resolve() not in [f.resolve() for f in files]
    assert symlink_file.resolve() not in [f.resolve() for f in files]


def test_agent_tool_validate_args_empty_parameters_traversal_check() -> None:
    tool = AgentTool(
        name="test_tool",
        description="A tool with empty parameters declaration",
        func=lambda **kwargs: "ok",
        parameters={},
    )

    with pytest.raises(SecurityError, match=r"(?i)path traversal.*detected"):
        tool.validate_args({"path": "../../../etc/passwd"})


def test_validate_vault_path_percent_encoded_traversal() -> None:
    # Standard traversal
    with pytest.raises(VaultConfigurationError, match="traversal"):
        _validate_vault_path("secret/../admin")

    # Percent-encoded traversal: %2e%2e
    with pytest.raises(VaultConfigurationError, match="traversal"):
        _validate_vault_path("secret/%2e%2e/admin")


def test_export_invalidated_feedback_unsafe_reviews_dir() -> None:
    outside_dir = Path("/etc/unauthorized_reviews_dir")

    with pytest.raises(SecurityError, match="escapes allowed"):
        export_invalidated_feedback(reviews_dir=outside_dir)


def test_mask_secrets_preserves_function_invocations() -> None:
    code_snippet = (
        "embedder = EmbeddingsEngine(ai_config=st.ai, api_key=settings_mod.get_ai_api_key(st))\n"
    )
    masked = _mask_secrets_in_content(code_snippet)
    # The function call settings_mod.get_ai_api_key(st) must NOT be replaced with <masked-api-key>(st)
    assert "<masked-api-key>(st)" not in masked
    assert "settings_mod.get_ai_api_key(st)" in masked


def test_filesystem_search_files_redos_guard(tmp_path: Path) -> None:
    fs = FileSystem(root=tmp_path)
    (tmp_path / "hello.txt").write_text("hello world\n", encoding="utf-8")

    # Excessively long query string
    huge_query = "a" * 500
    res = fs._search_files(query=huge_query)
    assert "Error:" in res or "exceeds" in res or "No matches" in res


def test_common_hallucinations_masked_placeholder_nameerror() -> None:
    finding = Finding(
        severity="HIGH",
        location="src/devops_cli/ai/rag/investigator.py:47",
        title="Undefined placeholder for API key",
        description="The code uses a placeholder <masked-api-key>(st) which is not defined, causing a NameError at runtime.",
        fix="Replace the placeholder with a proper function call",
    )

    # Invalidator check
    invalidation_res = _deterministic_pre_verification(finding, repo_root=Path.cwd())
    assert invalidation_res is not None
    assert invalidation_res.status == "INVALIDATED"
    assert "Sanitization marker" in (invalidation_res.invalidation_reason or "")


def test_common_hallucinations_missing_symbol_false_alarm(tmp_path: Path) -> None:
    py_file = tmp_path / "module.py"
    py_file.write_text("DEFAULT_HTTP_BROKER = 'broker_instance'\n", encoding="utf-8")

    finding = Finding(
        severity="HIGH",
        location=f"{py_file}:1",
        title="ImportError: DEFAULT_HTTP_BROKER not defined",
        description="The broker module does not expose DEFAULT_HTTP_BROKER, causing ImportError.",
        fix="Define DEFAULT_HTTP_BROKER",
    )

    entry = CommonHallucinationEntry(
        id="HALLUCINATION-MISSING-SYMBOL-FALSE-ALARM",
        name="False-Positive Missing Import or Symbol Claim",
        category=HallucinationCategory.SYNTAX_GRAMMAR,
        description="Claiming symbol does not exist when defined",
        signature_patterns=[
            r"DEFAULT_HTTP_BROKER",
            r"(?:missing|undefined)\s+[A-Z0-9_]+\s+(?:import|symbol)",
        ],
        pattern_keywords=["default_http_broker", "missing_symbol"],
        file_patterns=["*.py"],
        resolution="Symbol actually exists in target module.",
    )

    # Similarity should match
    sim = calculate_hallucination_similarity(finding, entry, file_path=py_file)
    assert sim.similarity_score > 0.6

    # Ground truth verification should confirm symbol exists in module AST
    is_hallucination = verify_ground_truth_hallucination(finding, entry, py_file)
    assert is_hallucination is True


def test_mask_secrets_unquoted_token_with_dots() -> None:
    yaml_snippet = "api_key: abc.def.1234567890abcdef12345\n"
    masked = _mask_secrets_in_content(yaml_snippet)
    assert "abc.def" not in masked
    assert "api_key=<masked-api-key>" in masked


def test_verify_symbol_defined_in_ast_or_module_fallback(tmp_path: Path) -> None:
    import ast

    from devops_cli.ai.review.common_hallucinations import _verify_symbol_defined_in_ast_or_module

    py_file = tmp_path / "sample.py"
    py_file.write_text("x = 1\n", encoding="utf-8")
    tree = ast.parse("x = 1\n")

    # Case 1: No candidate symbol in finding text -> must return False to avoid false invalidation
    finding_no_symbol = Finding(
        severity="LOW",
        location=f"{py_file}:1",
        title="Generic issue without identifier",
        description="Something is missing here",
    )
    assert _verify_symbol_defined_in_ast_or_module(finding_no_symbol, tree, py_file) is False

    # Case 2: Candidate symbol is genuinely missing -> must return False
    finding_missing_symbol = Finding(
        severity="HIGH",
        location=f"{py_file}:1",
        title="Missing NON_EXISTENT_VAR",
        description="NON_EXISTENT_VAR is not defined",
    )
    assert _verify_symbol_defined_in_ast_or_module(finding_missing_symbol, tree, py_file) is False

    # Case 3: Candidate symbol is defined in AST -> returns True
    finding_existing_symbol = Finding(
        severity="HIGH",
        location=f"{py_file}:1",
        title="Missing `x` variable",
        description="`x` is not defined",
    )
    assert _verify_symbol_defined_in_ast_or_module(finding_existing_symbol, tree, py_file) is True


def test_resolve_target_file_src_layout_fallback(tmp_path: Path) -> None:
    from devops_cli.ai.review.verification import _resolve_target_file

    repo_dir = tmp_path / "my_project"
    repo_dir.mkdir()
    src_dir = repo_dir / "src" / "pkg"
    src_dir.mkdir(parents=True)
    target = src_dir / "module.py"
    target.write_text("a = 1\n", encoding="utf-8")

    # Finding omits "src/"
    resolved = _resolve_target_file("pkg/module.py", repo_root=repo_dir)
    assert resolved is not None
    assert resolved.resolve() == target.resolve()
