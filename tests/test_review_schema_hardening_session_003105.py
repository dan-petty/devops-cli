"""Unit tests for review schema hardening, PEP 759 exception awareness, and location sanitization."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.review.verification import _check_syntax_error_hallucination
from devops_cli.ai.review_schema import (
    Finding,
    canonicalize_finding_location,
    sanitize_finding_text,
)


def test_canonicalize_location_rejects_markdown_headers_and_stars() -> None:
    # Markdown asterisks, bold syntax, or section headers should not be parsed as locations
    assert canonicalize_finding_location("**") == ""
    assert canonicalize_finding_location("***") == ""
    assert canonicalize_finding_location("## Security Review") == ""
    assert canonicalize_finding_location("---") == ""
    assert canonicalize_finding_location("### 1. Location") == ""


def test_canonicalize_location_preserves_valid_paths_and_targets() -> None:
    assert (
        canonicalize_finding_location("src/devops_cli/ai/context_budget.py:20-21")
        == "src/devops_cli/ai/context_budget.py:20-21"
    )
    assert canonicalize_finding_location("uv.lock:jinja2") == "uv.lock:jinja2"
    assert (
        canonicalize_finding_location("In file `src/devops_cli/commands/vault.py:10-25` we found")
        == "src/devops_cli/commands/vault.py:10-25"
    )


def test_sanitize_finding_text_strips_approvals_and_conversational_filler() -> None:
    assert (
        sanitize_finding_text(
            "Good. But potential race condition: known_hosts file may be modified concurrently."
        )
        == "Potential race condition: known_hosts file may be modified concurrently."
    )
    assert sanitize_finding_text("The function uses write_file for write_bytes_file. Good.") == ""
    assert sanitize_finding_text("No issues found in this module. Looks solid.") == ""


def test_finding_is_empty_filters_markdown_garbage_and_praise() -> None:
    f_garbage = Finding(
        severity="MEDIUM",
        location="**",
        title="Security Review - Principal DevSecOps Engineer",
        description="The generate command accepts an output_dir option...",
    )
    assert f_garbage.is_empty is True

    f_praise = Finding(
        severity="MEDIUM",
        location="src/devops_cli/output/file_writer.py:1-60",
        title="The function uses write_file for write_bytes_file. Good.",
        description="The function uses write_file for write_bytes_file. Good.",
    )
    assert f_praise.is_empty is True

    f_valid = Finding(
        severity="HIGH",
        location="src/devops_cli/security/vault_broker.py:94-104",
        title="Potential SSRF via unvalidated VAULT_ADDR",
        description="Vault address is not validated against SSRF.",
    )
    assert f_valid.is_empty is False


def test_check_syntax_error_hallucination_invalidates_pep759_claims(tmp_path: Path) -> None:
    # A Python 3.14 file with PEP 759 unparenthesized except clause
    py_code = (
        "def test_fn():\n    try:\n        pass\n    except KeyError, ValueError:\n        pass\n"
    )
    py_file = tmp_path / "valid_pep759.py"
    py_file.write_text(py_code, encoding="utf-8")

    f = Finding(
        severity="CRITICAL",
        location=f"{py_file.name}:4-5",
        title="Syntax error: incorrect except clause in _get_tiktoken_encoding",
        description="Uses Python-2 syntax except KeyError, ValueError: causing a SyntaxError",
    )

    invalidated = _check_syntax_error_hallucination(f, py_file)
    assert invalidated is not None
    assert invalidated.status == "INVALIDATED"
    assert invalidated.verified is False
    assert invalidated.reportable is False
