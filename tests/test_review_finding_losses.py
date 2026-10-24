"""Findings are not lost between the model's reply and the report (#512)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from devops_cli.ai.review import ReviewPipelineOrchestrator
from devops_cli.ai.review.pipeline import _build_malicious_network_finding, _is_exact_version
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding
from devops_cli.models.vulnerability import NetworkReference, NetworkReputationRecord


@pytest.fixture(autouse=True)
def _no_rag() -> object:
    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        yield


@pytest.mark.parametrize(
    ("version", "ecosystem", "exact"),
    [
        ("==2.11.0", "PyPI", True),
        ("2.11.0", "npm", True),
        ("v1.9.2", "Go", True),
        (">=2.32.3", "PyPI", False),
        ("^18.2.0", "npm", False),
        ("~1.4", "npm", False),
        ("1.x", "npm", False),
        ("*", "npm", False),
        ("1.0", "crates.io", False),
        ("", "PyPI", False),
        ("1.0.0-linux", "npm", True),
    ],
)
def test_only_exact_versions_are_looked_up(version: str, ecosystem: str, exact: bool) -> None:
    """Verify a version range is not sent to OSV, which would return every advisory ever."""
    assert _is_exact_version(version, ecosystem) is exact


def test_threat_intel_network_findings_start_unverified() -> None:
    """Verify a host with published CVEs is left for verification, not reported as verified."""
    finding = _build_malicious_network_finding(
        "README.md",
        NetworkReference(target="203.0.113.7", reference_type="ip", line_number=4),
        NetworkReputationRecord(target="203.0.113.7", ip="203.0.113.7", is_malicious=True),
    )

    assert (finding.status, finding.verified, finding.reportable) == ("UNVERIFIED", False, True)


_FINDING = (
    '{"severity": "CRITICAL", "location": "app.py:10", "title": "SQL injection in search", '
    '"description": "The search term is formatted into the query.", "fix": "Bind parameters."}'
)


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param(
            '{"findings": [' + _FINDING + '], "external_dependencies": ["requests"]}',
            id="bad-field",
        ),
        pytest.param(
            '{"findings": [' + _FINDING + ', {"title": 5, "location": []}]}', id="bad-sibling"
        ),
        pytest.param('{"issues": [' + _FINDING + "]}", id="synonym-key"),
        pytest.param('{"review": {"findings": [' + _FINDING + "]}}", id="nested"),
        pytest.param(
            'I checked `{}` handling first.\n```json\n{"findings": [' + _FINDING + "]}\n```",
            id="prose-braces",
        ),
    ],
)
def test_a_reply_keeps_its_valid_findings(reply: str) -> None:
    """Verify one malformed field, a synonym key, nesting or stray braces cost no valid finding."""
    from devops_cli.ai.review_schema import parse_review_response

    result = parse_review_response(reply)

    titles = [f.title for f in result.findings] if result else None
    assert titles == ["SQL injection in search"]


def test_a_finding_quoting_think_does_not_truncate_the_reply() -> None:
    """Verify a literal <think> inside a finding is text, not unclosed reasoning."""
    from devops_cli.ai.review_schema import parse_review_response

    quoting = (
        '{"severity": "LOW", "location": "chat.py:4", "title": "Unescaped <think> tag in output", '
        '"description": "The <think> marker reaches users.", "fix": "Strip it."}'
    )
    result = parse_review_response('{"findings": [' + quoting + ", " + _FINDING + "]}")

    titles = [f.title for f in result.findings] if result else []
    assert titles == ["Unescaped <think> tag in output", "SQL injection in search"]


def test_a_candidate_cannot_set_its_own_verification_state() -> None:
    """Verify a finding marked INVALIDATED or VERIFIED starts unverified and reported."""
    from devops_cli.ai.review_schema import Finding, reset_verification_state

    f1 = Finding(
        severity="HIGH",
        location="src/app.py:3",
        title="SQL injection in search",
        description="d",
        fix="f",
        status="INVALIDATED",
        reportable=False,
    )
    f2 = Finding(
        severity="LOW",
        location="src/app.py:9",
        title="Verbose logging",
        description="d",
        fix="f",
        status="VERIFIED",
        verified=True,
    )
    assert [
        (f.title, f.status, f.reportable, f.verified)
        for f in [reset_verification_state(f1), reset_verification_state(f2)]
    ] == [
        ("SQL injection in search", "UNVERIFIED", True, False),
        ("Verbose logging", "UNVERIFIED", True, False),
    ]


def _at(
    title: str, location: str, description: str = "d", status: str = "UNVERIFIED"
) -> SavedFinding:
    return SavedFinding(
        severity="HIGH",
        location=location,
        title=title,
        description=description,
        status=status,
        fingerprint=title,
    )


@pytest.mark.parametrize(
    "pair",
    [
        pytest.param(
            [_at("Missing timeout", "a.py:40-42"), _at("Missing authorization check", "a.py:41")],
            id="shared-filler-word",
        ),
        pytest.param(
            [
                _at("Hardcoded secret", "c.py:5", "`AWS_ACCESS_KEY` is committed."),
                _at("Hardcoded secret", "c.py:90", "`DB_PASSWORD` is committed."),
            ],
            id="same-title-far-apart",
        ),
        pytest.param(
            [
                _at("Missing timeout on HTTP request", "a.py:20"),
                _at("Missing timeout on database request", "a.py:200"),
            ],
            id="similar-title-far-apart",
        ),
        pytest.param(
            [
                _at("`parse_config` swallows exceptions", "cfg.py:10-30"),
                _at("`parse_config` reads file without size limit", "cfg.py:12"),
            ],
            id="one-function-two-defects",
        ),
    ],
)
def test_distinct_defects_are_not_merged(pair: list[SavedFinding]) -> None:
    """Verify exact deduplication keeps different defects apart."""
    orchestrator = ReviewPipelineOrchestrator(session_id="test", target_dir=Path("."))
    payloads = [FileReviewPayload(file_path=p.location.split(":")[0], findings=[p]) for p in pair]
    assert len(orchestrator._collect_and_deduplicate_findings(payloads)) == 2


def test_the_same_defect_reported_twice_still_merges() -> None:
    """Verify exact matches on fingerprint and location merge."""
    orchestrator = ReviewPipelineOrchestrator(session_id="test", target_dir=Path("."))
    pair = [
        SavedFinding(
            severity="HIGH",
            location="a.py:10",
            title="SQL injection",
            description="d",
            fingerprint="sql-inj-1",
        ),
        SavedFinding(
            severity="HIGH",
            location="a.py:10",
            title="SQL injection",
            description="d",
            fingerprint="sql-inj-1",
        ),
    ]
    payloads = [FileReviewPayload(file_path="a.py", findings=pair)]
    assert len(orchestrator._collect_and_deduplicate_findings(payloads)) == 1


@pytest.mark.parametrize(
    "title",
    [
        "Looks good overall, but token is logged in plaintext",
        "No issues with auth, but SQL injection in search()",
        "Checking of token expiry is missing.",
        "Based on the code, the lock is never released.",
        "Verification criteria list is never deduplicated",
    ],
)
def test_sanitizing_keeps_real_titles(title: str) -> None:
    """Verify a title that reads like praise, reasoning or a prompt header still survives."""
    from devops_cli.ai.review_schema import sanitize_finding_text

    assert sanitize_finding_text(title) == title


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Looks good.", ""),
        ("No issues found.", ""),
        ("Let's check the handler. SQL injection in search", "SQL injection in search"),
        ("Command injection. Verification criteria: run it", "Command injection."),
    ],
)
def test_sanitizing_still_removes_praise_reasoning_and_leaks(text: str, expected: str) -> None:
    """Verify praise-only titles, leading reasoning and leaked criteria sections are removed."""
    from devops_cli.ai.review_schema import sanitize_finding_text

    assert sanitize_finding_text(text) == expected


@pytest.mark.parametrize(
    ("code", "syntax", "masked"),
    [
        ("password = hashlib.md5(pw.encode()).hexdigest()", "code", False),
        ("const token = req.query.token;", "code", False),
        ('token = os.environ["GH_TOKEN"]', "code", False),
        ('requests.get("http://api.internal:8080/v1/users?email=a@b.com")', "code", False),
        ("password: hunter2hunter2", "code", True),
        ('password = "hunter2(x)y"', "code", True),
        ("https://bob:s3cr3tpass@db.example.com/x", "code", True),
        ("password: hunter2(x)y", "code", True),
        ("password=Xk9{mP2[qL7z", "code", True),
        ("password: correct.horse.battery", "data", True),
        ("token=Ab3dEf[gh]Ij9kLmN", "code", True),
        ("--password=Pa(ss)word1!", "code", True),
    ],
)
def test_redaction_masks_secrets_but_not_code(code: str, syntax: str, masked: bool) -> None:
    """Verify redaction hides credential literals and leaves code the reviewer must see."""
    from devops_cli.security.sanitizer import mask_secrets

    assert ("<masked-" in mask_secrets(code, syntax=syntax)) is masked


def test_a_masked_private_key_keeps_its_line_count() -> None:
    """Verify masking a key block does not move the lines after it."""
    from devops_cli.security.sanitizer import mask_secrets

    # Split so the pre-commit private-key detector does not flag this fixture.
    header = "PRIVATE " + "KEY-----"
    key = f"-----BEGIN RSA {header}\nAAAA\nBBBB\n-----END RSA {header}"
    text = f"line1\n{key}\neval(user_input)\n"

    assert mask_secrets(text).splitlines().index("eval(user_input)") == 5


@pytest.mark.parametrize(
    ("given", "severity"),
    [
        ("BLOCKER", "CRITICAL"),
        ("P0", "CRITICAL"),
        ("severe", "CRITICAL"),
        ("High severity", "HIGH"),
        ("major", "HIGH"),
        ("minor", "LOW"),
        ("SUGGESTION", "INFO"),
        ("informational", "INFO"),
        ("whatever", "MEDIUM"),
    ],
)
def test_severity_names_outside_the_schema_keep_their_meaning(given: str, severity: str) -> None:
    """Verify a BLOCKER is not reported as MEDIUM, nor a suggestion as a defect."""
    finding = SavedFinding(severity=given, location="a.py:1", title="t", description="d")

    assert finding.severity == severity
