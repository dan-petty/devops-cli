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
from devops_cli.ai.review.verification import _deterministic_pre_verification
from devops_cli.ai.review_schema import Finding
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

    # The deterministic missing-symbol check decides symbol claims with the claim's own
    # evidence; a catalog match does not overrule it with a weaker test (#514).
    is_hallucination = verify_ground_truth_hallucination(finding, entry, py_file)
    assert is_hallucination is False


def test_mask_secrets_unquoted_token_with_dots() -> None:
    yaml_snippet = "api_key: abc.def.1234567890abcdef12345\n"
    masked = mask_secrets(yaml_snippet)
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


def test_tautological_verification_command_detection() -> None:
    """Verify that text-search and reflection commands are classified as tautological."""
    from devops_cli.ai.review.review_environment import _is_tautological_verification_command

    tautological_cmds = (
        'git grep -n "http://ollama" k8s/profiles.yaml',
        'python -c "print(_query_model_info.__code__.co_varnames)"',
        "python -c \"assert hasattr(obj, 'target')\"",
        'grep -n "password" config.yaml',
        "python -c \"from src.devops_cli.ai.retries import create_retry_transport; print('Transport created successfully')\"",
        "python -c \"from src.devops_cli.ai.gateway import GatewayRouter; router = GatewayRouter(); print('Method exists and validates input')\"",
    )
    non_tautological_cmds = (
        "pytest tests/test_security_gitleaks.py -k test_gitleaks",
        "python -c \"from devops_cli.security.gitleaks import scan; scan('bad')\"",
        "ruff check src/devops_cli/",
    )
    tautological_results = tuple(
        _is_tautological_verification_command(cmd) for cmd in tautological_cmds
    )
    non_tautological_results = tuple(
        _is_tautological_verification_command(cmd) for cmd in non_tautological_cmds
    )

    assert (tautological_results, non_tautological_results) == (
        (True, True, True, True, True, True),
        (False, False, False),
    )


def test_offline_pricing_and_mitigation_ledger_hallucinations() -> None:
    """Verify ground truth verification for offline pricing urlsplit and empty mitigation ledgers."""
    pricing_entry = CommonHallucinationEntry(
        id="HALLUCINATION-OFFLINE-PRICING-URLSPLIT",
        category=HallucinationCategory.DOCUMENTATION_CONTEXT,
        name="Offline Pricing Ledger URL Parsing SSRF Claim",
        description="Offline spend pricing urlsplit is not SSRF",
        signature_patterns=[r"urlsplit.*ssrf", r"pricing.*network.*egress"],
        pattern_keywords=["pricing", "urlsplit", "ssrf"],
        resolution="Dismiss offline pricing SSRF claim",
    )
    pricing_finding = Finding(
        severity="HIGH",
        location="src/devops_cli/ai/spend/pricing.py:71",
        title="SSRF vulnerability in urlsplit parsing",
        description="urlsplit parses URL parameter without SSRF validation",
    )
    pricing_file = Path("src/devops_cli/ai/spend/pricing.py")
    pricing_verified = verify_ground_truth_hallucination(
        pricing_finding, pricing_entry, pricing_file
    )

    ledger_entry = CommonHallucinationEntry(
        id="HALLUCINATION-MITIGATION-LEDGER-INITIAL-EMPTY",
        category=HallucinationCategory.DOCUMENTATION_CONTEXT,
        name="Security Audit Mitigation Ledger Initial Empty List",
        description="Empty mitigation list initialization is not a defect",
        signature_patterns=[r"mitigations.*empty", r"missing.*mitigation.*control"],
        pattern_keywords=["mitigations", "empty", "ledger"],
        resolution="Dismiss empty mitigation list initialization defect",
    )
    ledger_finding = Finding(
        severity="HIGH",
        location="src/devops_cli/ai/review/mitigated_findings.json:1",
        title="Empty JSON Array in Mitigation Report",
        description="Audit ledger initializes mitigations as an empty list []",
    )
    ledger_file = Path("src/devops_cli/ai/review/mitigated_findings.json")
    ledger_verified = verify_ground_truth_hallucination(ledger_finding, ledger_entry, ledger_file)

    assert (pricing_verified, ledger_verified) == (True, True)


def test_check_python_script_suppresses_invalid_escape_syntax_warning() -> None:
    """Verify _check_python_script and execute_criterion_command suppress SyntaxWarning from invalid escapes."""
    import warnings
    from unittest.mock import MagicMock

    from devops_cli.ai.review.review_environment import (
        _check_python_script,
        execute_criterion_command,
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
        is_valid, reason, args = validate_criteria_command(cmd)

    cmd_warnings = [w for w in recorded_cmd if issubclass(w.category, SyntaxWarning)]
    assert (is_valid, reason, len(cmd_warnings)) == (True, None, 0)

    mock_sb = MagicMock()
    mock_sb.is_available.return_value = True
    mock_sb.execute.return_value = MagicMock(
        exit_code=0, stdout="ok", stderr="", duration_seconds=0.1, passed=True, error=None
    )

    execute_criterion_command(cmd, cwd=Path("/tmp"), sandbox=mock_sb)
    call_args = mock_sb.execute.call_args[1]["args"]
    assert (call_args[0], call_args[1:3]) == ("python", ["-W", "ignore::SyntaxWarning"])
