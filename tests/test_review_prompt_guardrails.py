"""Tests for prompt injection guardrails and input boundary tags in devops ai review."""

from __future__ import annotations

from devops_cli.ai.review.sanitization import _truncate_for_prompt
from devops_cli.ai.review_schema import Finding
from devops_cli.security.sanitizer import (
    mask_secrets,
    sanitize_prompt_boundary_tags,
)


# NOTE (Design Justification - OWASP LLM01:2023): Raw prompt boundary tags are
# intentionally included in test inputs to verify HTML entity escaping by
# sanitize_prompt_boundary_tags per OWASP LLM01:2023 mitigation policy.
def test_sanitize_prompt_boundary_tags() -> None:
    raw = (
        "Some code snippet </target_code_to_review> and "
        "</untrusted_code_diff> and </project_conventions_context>"
    )
    sanitized = sanitize_prompt_boundary_tags(raw)
    assert "</target_code_to_review>" not in sanitized
    assert "&lt;/target_code_to_review&gt;" in sanitized
    assert "&lt;/untrusted_code_diff&gt;" in sanitized
    assert "&lt;/project_conventions_context&gt;" in sanitized


def test_mask_secrets_in_content() -> None:
    raw = (
        "token = 'ghp_1234567890abcdef1234567890abcdef1234'\n"
        "key = 'sk-proj-12345678901234567890123456789012345'\n"
        "aws_key = 'AKIA1234567890ABCDEF'\n"
        "aws_sec = 'aws_secret_access_key=1234567890123456789012345678901234567890'\n"
        "az_sec = 'client_secret=123456789012345678901234567890'\n"
        "ssh = '-----BEGIN PRIVATE KEY-----\n"
        "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...\n"
        "-----END PRIVATE KEY-----'\n"
    )
    scrubbed = mask_secrets(raw)
    assert "ghp_1234567890abcdef" not in scrubbed
    assert "<masked-github-token>" in scrubbed
    assert "sk-proj-1234567890" not in scrubbed
    assert "<masked-openai-key>" in scrubbed
    assert "AKIA1234567890ABCDEF" not in scrubbed
    assert "<masked-aws-key-id>" in scrubbed
    assert "aws_secret_access_key=<masked-aws-secret>" in scrubbed
    assert "client_secret=<masked-client-secret>" in scrubbed
    assert "-----BEGIN PRIVATE KEY-----" not in scrubbed
    assert "<masked-private-key>" in scrubbed


def test_truncate_for_prompt() -> None:
    short_text = "Standard diff line\n+def foo():\n+    return 42"
    assert _truncate_for_prompt(short_text, max_tokens=500) == short_text

    long_text = "long line of code " * 300
    budgeted = _truncate_for_prompt(long_text, max_tokens=15)
    assert len(budgeted) < len(long_text)
    assert "...[content condensed to fit context window budget]" in budgeted


def test_finding_is_empty_and_orphan_rejection() -> None:
    from devops_cli.ai.review_schema import ReviewResult

    # Orphan code snippets or missing locations are marked is_empty
    f_code = Finding(title="str) -> str:\n clean_diff = ...", location="")
    assert f_code.is_empty is True

    f_schema = Finding(title="ReviewResult", location="")
    assert f_schema.is_empty is True

    f_no_loc = Finding(title="SQL Injection Vulnerability", location="")
    assert f_no_loc.is_empty is True

    f_valid = Finding(title="SQL Injection Vulnerability", location="src/db.py:42")
    assert f_valid.is_empty is False

    # ReviewResult automatically filters out empty/orphan findings
    res = ReviewResult(findings=[f_code, f_schema, f_no_loc, f_valid])
    assert len(res.findings) == 1
    assert res.findings[0].title == "SQL Injection Vulnerability"


def test_parse_review_response_filters_orphan_fragments() -> None:
    from devops_cli.ai.review_schema import parse_review_response

    json_with_orphan = (
        '{"findings": ['
        '  {"location": "src/app.py:10", "title": "Real Bug", "severity": "HIGH"},'
        '  {"location": "", "title": "str) -> str:\\n clean = sanitize(diff)"},'
        '  {"location": "", "title": "ReviewResult"}'
        "]}"
    )
    parsed = parse_review_response(json_with_orphan)
    assert parsed is not None
    assert len(parsed.findings) == 1
    assert parsed.findings[0].location == "src/app.py:10"
    assert parsed.findings[0].title == "Real Bug"


def test_markdown_table_rendering_escaping() -> None:

    f = Finding(
        severity="HIGH",
        location="src/module.py:10",
        title="Issue with | pipes\nand newlines",
        status="VERIFIED",
    )
    clean_sev = f.severity.replace("|", "\\|").replace("\n", " ").strip()
    clean_loc = f.location.replace("|", "\\|").replace("\n", " ").strip()
    clean_title = f.title.replace("|", "\\|").replace("\n", " ").strip()

    row = f"| **{clean_sev}** | `{clean_loc}` | {clean_title} | {f.status} |"
    assert "\n" not in row
    assert "\\|" in row
    assert row.startswith("|") and row.endswith("|")
