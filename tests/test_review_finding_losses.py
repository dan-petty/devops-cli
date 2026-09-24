"""Findings are not lost between the model's reply and the report (#512)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review import ReviewPipelineOrchestrator
from devops_cli.ai.review.pipeline import _build_malicious_network_finding, _is_exact_version
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding
from devops_cli.models.vulnerability import NetworkReference, NetworkReputationRecord

_PERSONA_REPLY = (
    '```json\n{"findings": [{"severity": "HIGH", "location": "src/app.py:3", '
    '"title": "SQL injection in search", "description": "Input reaches the query.", '
    '"fix": "Bind parameters."}]}\n```'
)


@pytest.fixture(autouse=True)
def _no_rag() -> object:
    with patch("devops_cli.ai.rag.investigator.investigate_rag_context", return_value=None):
        yield


def _orchestrator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reply: object) -> Any:
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    llm = MagicMock()
    for method in ("chat_messages", "chat_complete", "chat", "complete"):
        getattr(llm, method).side_effect = reply
    return ReviewPipelineOrchestrator(session_id="losses", llm_client=llm)


def _scanner_finding() -> SavedFinding:
    return SavedFinding(
        severity="CRITICAL",
        location="src/app.py:1",
        title="[gitleaks] AWS access key committed",
        description="An AWS access key is committed in plaintext.",
        fix="Revoke and rotate the key.",
        persona="devsecops",
    )


def _review(orchestrator: Any) -> FileReviewPayload:
    payload = FileReviewPayload(file_path="src/app.py", findings=[_scanner_finding()])
    orchestrator.execute_multi_persona_review(
        [payload],
        diff_text_by_file={"src/app.py": "key = 'AKIA...'\nquery = f'... {term}'\n"},
        personas=["devsecops"],
    )
    return payload


def test_scanner_findings_survive_the_persona_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify scanner findings seeded into a payload are kept beside the persona findings."""
    payload = _review(_orchestrator(tmp_path, monkeypatch, lambda *a, **k: _PERSONA_REPLY))

    assert sorted(f.title for f in payload.findings) == [
        "SQL injection in search",
        "[gitleaks] AWS access key committed",
    ]


def test_scanner_findings_survive_a_failed_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a failing persona review does not erase the file's scanner findings."""

    def fail(*args: object, **kwargs: object) -> str:
        raise RuntimeError("backend unavailable")

    orchestrator = _orchestrator(tmp_path, monkeypatch, fail)
    payload = _review(orchestrator)

    assert ([f.title for f in payload.findings], "src/app.py" in orchestrator.errored_files) == (
        ["[gitleaks] AWS access key committed"],
        True,
    )


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


def test_a_persona_cannot_set_its_own_verification_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a finding the persona marked INVALIDATED or VERIFIED starts unverified and reported."""
    reply = (
        '```json\n{"findings": ['
        '{"severity": "HIGH", "location": "src/app.py:3", "title": "SQL injection in search", '
        '"description": "d", "fix": "f", "status": "INVALIDATED", "reportable": false}, '
        '{"severity": "LOW", "location": "src/app.py:9", "title": "Verbose logging", '
        '"description": "d", "fix": "f", "status": "VERIFIED", "verified": true}]}\n```'
    )
    payload = _review(_orchestrator(tmp_path, monkeypatch, lambda *a, **k: reply))
    persona = [f for f in payload.findings if not f.title.startswith("[gitleaks]")]

    assert sorted((f.title, f.status, f.reportable, f.verified) for f in persona) == [
        ("SQL injection in search", "UNVERIFIED", True, False),
        ("Verbose logging", "UNVERIFIED", True, False),
    ]


def _at(
    title: str, location: str, description: str = "d", status: str = "UNVERIFIED"
) -> SavedFinding:
    return SavedFinding(
        severity="HIGH", location=location, title=title, description=description, status=status
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
        pytest.param(
            [
                _at("Eval of user input", "x.py:8", status="INVALIDATED"),
                _at("Eval of user input", "x.py:8", status="VERIFIED"),
            ],
            id="dismissed-and-live",
        ),
    ],
)
def test_distinct_defects_are_not_merged(pair: list[SavedFinding]) -> None:
    """Verify consolidation keeps different defects apart."""
    from devops_cli.ai.review_schema import consolidate_duplicate_findings

    assert len(consolidate_duplicate_findings(pair)) == 2


def test_the_same_defect_reported_twice_still_merges() -> None:
    """Verify a real duplicate, one defect cited at adjacent lines, is still consolidated."""
    from devops_cli.ai.review_schema import consolidate_duplicate_findings

    pair = [_at("SQL injection in search", "a.py:10"), _at("SQL injection in search()", "a.py:11")]

    assert len(consolidate_duplicate_findings(pair)) == 1


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
    ("code", "masked"),
    [
        ("password = hashlib.md5(pw.encode()).hexdigest()", False),
        ("const token = req.query.token;", False),
        ('token = os.environ["GH_TOKEN"]', False),
        ('requests.get("http://api.internal:8080/v1/users?email=a@b.com")', False),
        ("password: hunter2hunter2", True),
        ('password = "hunter2(x)y"', True),
        ("https://bob:s3cr3tpass@db.example.com/x", True),
    ],
)
def test_redaction_masks_secrets_but_not_code(code: str, masked: bool) -> None:
    """Verify redaction hides credential literals and leaves code the reviewer must see."""
    from devops_cli.security.sanitizer import mask_secrets

    assert ("<masked-" in mask_secrets(code)) is masked


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
