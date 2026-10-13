"""Property-based fuzzing tests for review JSON parsing and schema resilience.

Grounds property assertions in the review JSON schema specification:
- Review reply format accepts structured JSON objects declaring `findings` list.
- Schema tolerance accepts top-level list of finding objects.
- Synonym key tolerance maps `issues` and `results` keys to findings.
- Markdown code block extraction (` ```json ... ``` `) and conversational preamble stripping.
- Malformed payloads that contain no valid findings return None safely without unhandled exceptions.
"""

from __future__ import annotations

import json

from hypothesis import Phase, example, given, settings
from hypothesis import strategies as st

from devops_cli.ai.review_schema import ReviewResult, parse_review_response

_FUZZ_SETTINGS = settings(
    phases=[Phase.explicit, Phase.generate],
    derandomize=True,
    max_examples=35,
    deadline=None,
)

_VALID_SEVERITIES = ("critical", "high", "medium", "low", "info")


@_FUZZ_SETTINGS
@given(
    title=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ ",
        min_size=1,
        max_size=30,
    ).filter(lambda t: bool(t.strip()) and t.strip()[0].isalpha() and "  " not in t),
    description=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789_., ", min_size=1, max_size=50
    ),
    file_path=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789_./-", min_size=1, max_size=30
    ).filter(
        lambda p: (
            bool(p.strip())
            and p.strip() not in {"none", "n/a", "na", "null", "undefined"}
            and any(c.isalnum() for c in p)
            and not p.strip().startswith("#")
            and not p.strip().endswith("/")
        )
    ),
    line_number=st.integers(min_value=1, max_value=5000),
    severity=st.sampled_from(_VALID_SEVERITIES),
    preamble=st.sampled_from(
        ["", "Here is the code review:\n", "```json\n", "<think>analyzing</think>\n"]
    ),
)
@example(
    title="SQL injection vulnerability",
    description="User input passed directly to database query without parameterization",
    file_path="src/db.py",
    line_number=42,
    severity="high",
    preamble="",
)
@example(
    title="Insecure permissions",
    description="File created with world-writable permissions",
    file_path="src/io.py",
    line_number=10,
    severity="medium",
    preamble="```json\n",
)
@example(
    title="Hardcoded credentials",
    description="API token hardcoded in source file",
    file_path="config.py",
    line_number=5,
    severity="critical",
    preamble="<think>analyzing</think>\n",
)
def test_review_json_schema_valid_findings_specification(
    title: str,
    description: str,
    file_path: str,
    line_number: int,
    severity: str,
    preamble: str,
) -> None:
    """Review JSON schema specification: valid findings dictionary parses into ReviewResult."""
    clean_title = title.strip()
    clean_path = file_path.strip()
    location_str = f"{clean_path}:{line_number}"

    payload = {
        "findings": [
            {
                "title": clean_title,
                "description": description,
                "path": location_str,
                "severity": severity,
            }
        ],
        "summary": "Review complete",
    }
    raw_json = json.dumps(payload)
    if preamble.startswith("```"):
        text = f"```json\n{raw_json}\n```"
    elif preamble:
        text = f"{preamble}{raw_json}"
    else:
        text = raw_json

    result = parse_review_response(text)
    assert isinstance(result, ReviewResult)
    assert len(result.findings) == 1
    f = result.findings[0]
    assert (f.title, f.location, f.severity.lower()) == (
        clean_title,
        location_str,
        severity.lower(),
    )


@_FUZZ_SETTINGS
@given(
    synonym=st.sampled_from(["issues", "results"]),
    title=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ ",
        min_size=1,
        max_size=25,
    ).filter(lambda t: bool(t.strip()) and t.strip()[0].isalpha() and "  " not in t),
    file_path=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789_./-", min_size=1, max_size=25
    ).filter(
        lambda p: (
            bool(p.strip())
            and p.strip() not in {"none", "n/a", "na", "null", "undefined"}
            and any(c.isalnum() for c in p)
            and not p.strip().startswith("#")
            and not p.strip().endswith("/")
        )
    ),
    line_number=st.integers(min_value=1, max_value=1000),
)
@example(synonym="issues", title="Missing auth check", file_path="auth.py", line_number=12)
@example(synonym="results", title="Buffer overflow risk", file_path="native.c", line_number=88)
def test_review_json_schema_synonym_keys_specification(
    synonym: str, title: str, file_path: str, line_number: int
) -> None:
    """Review JSON schema tolerance: synonym keys ('issues', 'results') map to findings."""
    clean_title = title.strip()
    clean_path = file_path.strip()
    location_str = f"{clean_path}:{line_number}"

    payload = {
        synonym: [
            {
                "title": clean_title,
                "description": "Synonym test finding description",
                "path": location_str,
                "severity": "low",
            }
        ]
    }
    text = json.dumps(payload)
    result = parse_review_response(text)

    assert isinstance(result, ReviewResult)
    assert len(result.findings) == 1
    assert (result.findings[0].title, result.findings[0].location) == (clean_title, location_str)


@_FUZZ_SETTINGS
@given(
    title=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ ",
        min_size=1,
        max_size=25,
    ).filter(lambda t: bool(t.strip()) and t.strip()[0].isalpha() and "  " not in t),
    file_path=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789_./-", min_size=1, max_size=25
    ).filter(
        lambda p: (
            bool(p.strip())
            and p.strip() not in {"none", "n/a", "na", "null", "undefined"}
            and any(c.isalnum() for c in p)
            and not p.strip().startswith("#")
            and not p.strip().endswith("/")
        )
    ),
    line_number=st.integers(min_value=1, max_value=1000),
)
@example(title="Top level list finding", file_path="main.py", line_number=1)
def test_review_json_schema_top_level_list_specification(
    title: str, file_path: str, line_number: int
) -> None:
    """Review JSON schema tolerance: top-level list of findings parses into ReviewResult."""
    clean_title = title.strip()
    clean_path = file_path.strip()
    location_str = f"{clean_path}:{line_number}"

    payload = [
        {
            "title": clean_title,
            "description": "Top level list finding description",
            "path": location_str,
            "severity": "medium",
        }
    ]
    text = json.dumps(payload)
    result = parse_review_response(text)

    assert isinstance(result, ReviewResult)
    assert len(result.findings) == 1
    assert (result.findings[0].title, result.findings[0].location) == (clean_title, location_str)


@_FUZZ_SETTINGS
@given(
    garbage=st.text(
        alphabet="!@#$%^&*()_+=-~`{}[]|;:,.<>?/ \t\n",
        min_size=0,
        max_size=30,
    )
)
@example(garbage="")
@example(garbage="not json at all")
@example(garbage="{unclosed: json")
@example(garbage="None")
@example(garbage='[{"title": "-", "path": "test.py:1"}]')
def test_review_json_invalid_payload_returns_none_or_empty_specification(
    garbage: str,
) -> None:
    """Review JSON error boundary: unparseable text returns None without crashing."""
    result = parse_review_response(garbage)
    assert result is None or (isinstance(result, ReviewResult) and len(result.findings) == 0)
