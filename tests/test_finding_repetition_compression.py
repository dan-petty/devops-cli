"""Unit tests for structural repetition/cycle compression in Finding and strict thinking rejection."""

from __future__ import annotations

import json
from pathlib import Path

from devops_cli.ai.review_schema import Finding, parse_review_response


def test_finding_collapses_consecutive_duplicate_lines() -> None:
    """Finding description and fix structurally collapse consecutive duplicate lines."""
    repeated_line = '- In _format_param_default_str, the code uses "except ValueError, AttributeError:" incorrectly. That is a bug.'
    lines = [
        "Initial analysis of the function.",
        *[repeated_line for _ in range(80)],
        "Final conclusion.",
    ]
    raw_desc = "\n\n".join(lines)

    f = Finding(
        severity="MEDIUM",
        location="src/devops_cli/docs/generator.py:120-135",
        title="Syntax error in exception handling",
        description=raw_desc,
        fix="\n".join([repeated_line for _ in range(20)]),
    )

    # Consecutive duplicates must be collapsed
    assert f.description.count(repeated_line) == 1
    assert "Initial analysis of the function." in f.description
    assert "Final conclusion." in f.description
    # Fix should also be collapsed
    assert f.fix.count(repeated_line) == 1


def test_finding_collapses_repeating_multiline_cycles() -> None:
    """Finding collapses repeating n-line cycles (e.g. 2-line cycle repeated 10 times)."""
    cycle = ["- Checking function A", "- Function A is safe"]
    lines = [
        "Starting scan.",
        *(cycle * 15),
        "Scan complete.",
    ]
    raw_desc = "\n".join(lines)

    f = Finding(
        severity="LOW",
        location="src/devops_cli/docs/generator.py:50-60",
        title="Cycle test",
        description=raw_desc,
    )

    assert f.description.count("- Checking function A") == 1
    assert f.description.count("- Function A is safe") == 1
    assert "Starting scan." in f.description
    assert "Scan complete." in f.description


def test_parse_review_response_rejects_cached_thinking_monologue() -> None:
    """parse_review_response rejects raw thinking monologue from session 20260905-035954."""
    cache_path = Path(
        ".data/cache/llm/llm_6c1e77e1578309cca407f361cbf63744545fbb5da2ab0851669e2934e0024717.json"
    )
    if not cache_path.exists():
        # Fallback raw monologue if cache is cleaned
        raw_text = (
            "We need to review this file for security vulnerabilities.\n"
            "1. _format_param_default_str: It uses try/except with 'except ValueError, AttributeError:' which is Python 2 syntax.\n"
            "The location: 'src/devops_cli/docs/generator.py:??'.\n"
            "The description: The except clause uses Python 2 syntax...\n"
            "The fix: Replace with 'except (ValueError, AttributeError):'...\n"
            + (
                "- In _format_param_default_str, the code uses 'except ValueError, AttributeError:' incorrectly. That is a bug.\n"
                * 50
            )
        )
    else:
        raw_data = json.loads(cache_path.read_text(encoding="utf-8"))
        raw_text = raw_data.get("content", "")

    # A raw thinking monologue must NOT be parsed as valid findings
    result = parse_review_response(raw_text)
    assert result is None or len(result.findings) == 0


def test_parse_review_response_rejects_unstructured_conversational_markdown() -> None:
    """Conversational text or unstructured markdown is rejected by parse_review_response."""
    conversational = (
        "During our audit we noticed that Location: src/devops_cli/main.py might have issues.\n"
        "Description: We should review this function.\n"
        "Fix: None needed yet."
    )
    assert parse_review_response(conversational) is None

    unstructured_md = """
### [HIGH] Unvalidated URL Scheme in Manifest Downloader
- Location: `src/devops_cli/commands/k8s/cluster_context.py:70-79`
- Description: The manifest loader accepts raw HTTP URLs without protocol enforcement.
- Fix: Ensure only HTTPS is permitted.
"""
    assert parse_review_response(unstructured_md) is None


def test_parse_review_response_structured_model_response_succeeds() -> None:
    """Valid structured response with thinking and findings parses correctly via ModelResponse."""
    import json

    from pydantic_ai.messages import ModelResponse, TextPart, ThinkingPart

    finding_data = {
        "findings": [
            {
                "severity": "HIGH",
                "location": "src/devops_cli/commands/k8s/cluster_context.py:70-79",
                "title": "Unvalidated URL Scheme in Manifest Downloader",
                "description": "The manifest loader accepts raw HTTP URLs without protocol enforcement.",
                "fix": "Ensure only HTTPS is permitted.",
            }
        ],
        "recommendation": "REQUEST CHANGES",
        "summary": "Found 1 high severity vulnerability.",
    }
    resp = ModelResponse(
        parts=[
            ThinkingPart(content="Inspecting cluster_context.py for URL scheme validation..."),
            TextPart(content=json.dumps(finding_data)),
        ]
    )
    result = parse_review_response(resp)
    assert result is not None
    assert len(result.findings) == 1
    assert result.findings[0].severity == "HIGH"
    assert result.findings[0].location == "src/devops_cli/commands/k8s/cluster_context.py:70-79"
    assert "Unvalidated URL Scheme" in result.findings[0].title
    assert result.thinking == "Inspecting cluster_context.py for URL scheme validation..."


def test_unique_lines_and_items_preserves_first_instance_using_set() -> None:
    """unique_lines and unique_items retain only the first instance of each line or item."""
    from devops_cli.ai.review_schema import unique_items, unique_lines

    # Empty inputs
    assert unique_lines("") == ""
    assert unique_items([]) == []

    # unique_items preserving first occurrence
    items = ["apple", "banana", "apple", "cherry", "banana", "date"]
    assert unique_items(items) == ["apple", "banana", "cherry", "date"]

    # unique_lines preserving first occurrence and collapsing duplicate blank lines
    raw_text = "Line 1\nLine 2\nLine 1\n\n\nLine 3\nLine 2\n"
    deduped = unique_lines(raw_text)
    assert deduped == "Line 1\nLine 2\n\nLine 3"


def test_finding_and_review_result_clean_thinking_field() -> None:
    """Finding and ReviewResult clean and deduplicate thinking using a set."""
    from devops_cli.ai.review_schema import Finding, ReviewResult

    repeat_thought = "Inspecting AST node for try/except blocks..."
    thinking_text = "\n".join([repeat_thought for _ in range(30)])

    f = Finding(
        severity="LOW",
        location="src/test.py:10",
        title="Test",
        thinking=thinking_text,
    )
    assert f.thinking is not None
    assert f.thinking.count(repeat_thought) == 1

    r = ReviewResult(
        thinking=thinking_text,
    )
    assert r.thinking is not None
    assert r.thinking.count(repeat_thought) == 1
