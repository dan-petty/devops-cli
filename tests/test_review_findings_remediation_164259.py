"""Tests verifying remediation of review findings from session 20260906-164259.

Validates:
1. Dry-run state restoration across calls (Finding 1).
2. Recursive configuration dictionary sanitization (Finding 2).
3. URI credential masking without malformed user prefix (Finding 3).
4. Cross-module import symbol detection disproving false ImportError claims (Finding 4).
5. Dynamic Authorization header inspection disproving false missing-header claims (Finding 5).
"""

from __future__ import annotations

import ast
from pathlib import Path

from devops_cli.ai.review.common_hallucinations import (
    _check_imported_module_for_symbol,
    _verify_symbol_defined_in_ast_or_module,
    is_common_hallucination,
    verify_ground_truth_hallucination,
)
from devops_cli.ai.review.verification import (
    _check_missing_header_hallucination,
    _check_missing_symbol_hallucination,
    _deterministic_pre_verification,
)
from devops_cli.ai.review_schema import Finding
from devops_cli.dry_run.decorator import is_dry_run, set_dry_run
from devops_cli.security.sanitizer import mask_uri_credentials
from devops_cli.server.routes.workspace import _redact_config_dict


def test_finding1_dry_run_state_preservation() -> None:
    """Ensure dry-run state is preserved and restored after execution."""
    set_dry_run(False)
    assert not is_dry_run()

    from devops_cli.dry_run.decorator import dry_run_command

    @dry_run_command(command="devops test", action="test_action")
    def sample_command(*, dry_run: bool = False) -> str:
        return "executed"

    # Call with dry_run=True
    sample_command(dry_run=True)
    # State must be restored to False
    assert not is_dry_run()


def test_finding2_recursive_config_redaction() -> None:
    """Ensure nested dictionaries and dotted secret paths are redacted."""
    secret_options = frozenset({"github.token", "custom.deep.api_token"})
    payload = {
        "github": {"token": "ghp_12345", "org": "my-org"},
        "custom": {
            "deep": {
                "api_token": "secret_token_val",
                "non_secret": "normal_val",
            },
        },
        "services": {
            "database": {
                "password": "db_password_123",
                "secret_key": "raw_secret",
            }
        },
    }

    sanitized = _redact_config_dict(payload, secret_options)
    assert sanitized["github"]["token"] == "***REDACTED***"
    assert sanitized["github"]["org"] == "my-org"
    assert sanitized["custom"]["deep"]["api_token"] == "***REDACTED***"
    assert sanitized["custom"]["deep"]["non_secret"] == "normal_val"
    assert sanitized["services"]["database"]["password"] == "***REDACTED***"
    assert sanitized["services"]["database"]["secret_key"] == "***REDACTED***"


def test_finding3_mask_uri_credentials_empty_username() -> None:
    """Ensure mask_uri_credentials does not prepend ':***@' when username is absent."""
    url_no_user = "http://:mysecretpassword@service.internal:9000/api/v1"
    masked = mask_uri_credentials(url_no_user)
    assert "mysecretpassword" not in masked
    assert masked == "http://***@service.internal:9000/api/v1"
    assert not masked.startswith("http://:***@")

    # Regular credentials with username
    url_with_user = "http://admin:mysecretpassword@service.internal:9000/api/v1"
    masked_user = mask_uri_credentials(url_with_user)
    assert "mysecretpassword" not in masked_user
    assert masked_user == "http://admin:***@service.internal:9000/api/v1"


def test_finding4_cross_module_import_symbol_invalidation() -> None:
    """Ensure false ImportError claims on imported symbols are deterministically invalidated."""
    init_path = Path("src/devops_cli/commands/k8s/__init__.py").resolve()
    assert init_path.is_file()

    finding = Finding(
        severity="LOW",
        location="src/devops_cli/commands/k8s/__init__.py:16",
        title="Missing _cluster_reachable import causes ImportError",
        description=(
            "The module imports `_cluster_reachable` from `devops_cli.commands.k8s.cluster_runtime`, "
            "but that symbol is not defined in `cluster_runtime.py`. Importing `k8s/__init__.py` "
            "will raise an `ImportError`."
        ),
        fix="Remove the import or implement _cluster_reachable",
        references=[],
    )

    # 1. Test AST import resolution directly
    tree = ast.parse(init_path.read_text(encoding="utf-8"))
    assert _check_imported_module_for_symbol(tree, "_cluster_reachable", init_path)
    assert _verify_symbol_defined_in_ast_or_module(finding, tree, init_path)

    # 2. Test common hallucination matcher
    match = is_common_hallucination(finding, threshold=0.7, file_path=init_path)
    assert match is not None
    assert match.hallucination.id == "HALLUCINATION-MISSING-SYMBOL-FALSE-ALARM"
    assert verify_ground_truth_hallucination(finding, match.hallucination, init_path)

    # 3. Test _check_missing_symbol_hallucination directly
    symbol_res = _check_missing_symbol_hallucination(finding, init_path)
    assert symbol_res is not None
    assert symbol_res.status == "INVALIDATED"
    assert not symbol_res.verified
    assert not symbol_res.reportable

    # 4. Test deterministic pre-verification pipeline

    pre_result = _deterministic_pre_verification(finding, repo_root=Path.cwd())
    assert pre_result.status == "INVALIDATED"
    assert not pre_result.verified
    assert not pre_result.reportable
    assert "symbol is defined" in (pre_result.invalidation_reason or "").lower() or (
        "common hallucination" in (pre_result.invalidation_reason or "").lower()
    )


def test_finding5_missing_header_invalidation() -> None:
    """Ensure false missing Authorization header claims are invalidated when header is dynamically set."""
    openai_path = Path("src/devops_cli/ai/providers/openai.py").resolve()
    assert openai_path.is_file()

    finding = Finding(
        severity="LOW",
        location="src/devops_cli/ai/providers/openai.py:51-55",
        title="Missing Authorization header in OpenAIProvider",
        description=(
            "The OpenAIProvider constructs a request to the OpenAI-compatible endpoint "
            "without including an Authorization header. If the configuration contains an API key, "
            "the request will be sent without authentication."
        ),
        fix="Add Authorization header",
        references=[],
    )

    # 1. Test _check_missing_header_hallucination directly
    invalidated = _check_missing_header_hallucination(finding, openai_path)
    assert invalidated is not None
    assert invalidated.status == "INVALIDATED"
    assert not invalidated.verified
    assert not invalidated.reportable
    assert (
        "authorization header is dynamically configured"
        in (invalidated.invalidation_reason or "").lower()
    )

    # 2. Test deterministic pre-verification pipeline
    pre_result = _deterministic_pre_verification(finding, repo_root=Path.cwd())
    assert pre_result.status == "INVALIDATED"
    assert not pre_result.verified
    assert not pre_result.reportable
