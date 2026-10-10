"""Unit and integration tests for review defenses and path traversal guards."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.agents.tools import AgentTool
from devops_cli.ai.harness.filesystem import FileSystem
from devops_cli.ai.review.exporter import export_invalidated_feedback
from devops_cli.commands.vault import _validate_vault_path
from devops_cli.core.repo import list_repo_files
from devops_cli.exceptions import SecurityError
from devops_cli.exceptions.vault import VaultConfigurationError
from devops_cli.security.sanitizer import mask_secrets


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
    masked = mask_secrets(code_snippet)
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


def test_mask_secrets_unquoted_token_with_dots() -> None:
    yaml_snippet = "api_key: abc.def.1234567890abcdef12345\n"
    masked = mask_secrets(yaml_snippet)
    assert "abc.def" not in masked
    assert "api_key=<masked-api-key>" in masked


def test_check_python_script_suppresses_invalid_escape_syntax_warning() -> None:
    """Verify _check_python_script and the criteria validator suppress SyntaxWarning from
    invalid escapes."""
    import warnings

    from devops_cli.ai.review.review_environment import (
        _check_python_script,
        validate_criteria_command,
    )

    script_with_invalid_escape = "val = 'C:\\windows\\path'; re_val = '\\w+'"
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        err = _check_python_script(script_with_invalid_escape)

    syntax_warnings = [w for w in recorded if issubclass(w.category, SyntaxWarning)]
    assert (err, len(syntax_warnings)) == (None, 0)

    cmd = "python -c \"val = 'C:\\\\windows\\\\path'\""
    with warnings.catch_warnings(record=True) as recorded_cmd:
        warnings.simplefilter("always")
        is_valid, reason, _args = validate_criteria_command(cmd)

    cmd_warnings = [w for w in recorded_cmd if issubclass(w.category, SyntaxWarning)]
    assert (is_valid, reason, len(cmd_warnings)) == (True, None, 0)
