"""Unit tests for review finding verification, manual invalidation, and stats commands."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review_schema import Finding
from devops_cli.commands.review import app

runner = CliRunner()


def test_finding_status_defaults_and_normalization() -> None:
    f1 = Finding(title="SQL Injection", location="db.py:10", status="unverified")
    assert f1.status == "UNVERIFIED"
    assert f1.verified is False

    f2 = Finding(
        title="XSS", location="ui.py:5", status="invalidated", invalidation_reason="False positive"
    )
    assert f2.status == "INVALIDATED"
    assert f2.invalidation_reason == "False positive"

    f3 = Finding(title="Secret Leak", location="cfg.py:1", status="mitigated", mitigated=True)
    assert f3.status == "MITIGATED"
    assert f3.mitigated is True


def test_review_findings_list_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviews_dir = tmp_path / "reviews"
    session_dir = reviews_dir / "20260809-120000-test-repo"
    session_dir.mkdir(parents=True)

    findings_payload = {
        "generated_at": "2026-08-09T12:00:00",
        "personas": ["devsecops", "architect"],
        "findings": [
            {
                "persona": "devsecops",
                "severity": "HIGH",
                "location": "auth.py:42",
                "title": "Hardcoded Token",
                "description": "Token in source",
                "status": "UNVERIFIED",
                "verified": True,
                "mitigated": False,
            },
            {
                "persona": "architect",
                "severity": "MEDIUM",
                "location": "server.py:100",
                "title": "Tight Coupling",
                "description": "Direct class dependency",
                "status": "INVALIDATED",
                "invalidation_reason": "Design choice",
                "verified_by": "human",
                "verified": False,
                "mitigated": False,
            },
        ],
    }
    (session_dir / "findings.json").write_text(json.dumps(findings_payload), encoding="utf-8")

    monkeypatch.setattr("devops_cli.commands.review.CONST_DATA_DIR", tmp_path)

    res = runner.invoke(app, ["findings", "--session", "test-repo"], env={"COLUMNS": "160"})
    assert res.exit_code == 0
    assert "Hardcoded Token" in res.output
    assert "Tight Coupling" in res.output
    assert "INVALIDATED" in res.output


def test_review_verify_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviews_dir = tmp_path / "reviews"
    session_dir = reviews_dir / "20260809-120000-test-repo"
    session_dir.mkdir(parents=True)

    findings_payload = {
        "generated_at": "2026-08-09T12:00:00",
        "personas": ["devsecops"],
        "findings": [
            {
                "persona": "devsecops",
                "severity": "HIGH",
                "location": "auth.py:42",
                "title": "Hardcoded Token",
                "description": "Token in source",
                "status": "UNVERIFIED",
                "verified": True,
                "mitigated": False,
            }
        ],
    }
    findings_file = session_dir / "findings.json"
    findings_file.write_text(json.dumps(findings_payload), encoding="utf-8")

    monkeypatch.setattr("devops_cli.commands.review.CONST_DATA_DIR", tmp_path)

    res = runner.invoke(
        app,
        [
            "verify",
            "test-repo",
            "--index",
            "1",
            "--status",
            "INVALIDATED",
            "--reason",
            "Environment variable fallback used",
        ],
    )
    assert res.exit_code == 0
    assert "Updated finding #1" in res.output

    updated_data = json.loads(findings_file.read_text(encoding="utf-8"))
    updated_finding = updated_data["findings"][0]
    assert updated_finding["status"] == "INVALIDATED"
    assert updated_finding["verified"] is False
    assert updated_finding["invalidation_reason"] == "Environment variable fallback used"
    assert updated_finding["verified_by"] == "human"


def test_review_stats_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviews_dir = tmp_path / "reviews"
    session_dir = reviews_dir / "20260809-120000-test-repo"
    session_dir.mkdir(parents=True)

    findings_payload = {
        "generated_at": "2026-08-09T12:00:00",
        "personas": ["devsecops"],
        "findings": [
            {
                "persona": "devsecops",
                "severity": "HIGH",
                "location": "auth.py:42",
                "title": "Hardcoded Token",
                "status": "VERIFIED",
            },
            {
                "persona": "devsecops",
                "severity": "MEDIUM",
                "location": "logging.py:10",
                "title": "Verbose Log",
                "status": "INVALIDATED",
                "invalidation_reason": "Debug mode only",
            },
        ],
    }
    (session_dir / "findings.json").write_text(json.dumps(findings_payload), encoding="utf-8")

    monkeypatch.setattr("devops_cli.commands.review.CONST_DATA_DIR", tmp_path)

    res = runner.invoke(app, ["stats"])
    assert res.exit_code == 0
    assert "Total Sessions:  1" in res.output
    assert "Total Findings:  2" in res.output
    assert "VERIFIED" in res.output
    assert "INVALIDATED" in res.output


def test_find_related_file_metas_matches_dependencies_and_symbols() -> None:
    from devops_cli.commands.review import _find_related_file_metas
    from devops_cli.models.ai import FileAnalysisMeta

    finding = Finding(
        title="Unvalidated Egress Request",
        location="src/devops_cli/commands/review.py:100",
        description="Call to validate_service_url without timeout.",
        status="UNVERIFIED",
    )
    analysis_metas = {
        "src/devops_cli/commands/review.py": FileAnalysisMeta(
            path="src/devops_cli/commands/review.py",
            dependencies=["devops_cli.http.client", "devops_cli.models.ai"],
        ),
        "src/devops_cli/http/client.py": FileAnalysisMeta(
            path="src/devops_cli/http/client.py",
            primary_purpose="Secure HTTP client with SSRF validation",
            key_symbols=["validate_service_url", "safe_get"],
            pseudocode=["validate_service_url(url)", "httpx.get(...)"],
        ),
    }

    related = _find_related_file_metas(finding, "src/devops_cli/commands/review.py", analysis_metas)
    assert len(related) == 1
    assert related[0].path == "src/devops_cli/http/client.py"


def test_build_validation_prompt_includes_related_file_analysis_metadata() -> None:
    from devops_cli.commands.review import _build_validation_prompt
    from devops_cli.models.ai import FileAnalysisMeta

    finding = Finding(
        title="Insecure Key Generation",
        location="crypto/ssh.py:15",
        description="Uses weak key size.",
        status="UNVERIFIED",
    )
    analysis_metas = {
        "crypto/ssh.py": FileAnalysisMeta(
            path="crypto/ssh.py",
            dependencies=["crypto.keyring"],
        ),
        "crypto/keyring.py": FileAnalysisMeta(
            path="crypto/keyring.py",
            primary_purpose="OS Keyring secret store and ED25519 helper",
            key_symbols=["get_secret", "generate_ed25519_key"],
            pseudocode=["generate_ed25519_key()", "keyring.set_password(...)"],
        ),
    }

    prompt = _build_validation_prompt(
        [finding],
        ["### File: crypto/ssh.py\ncode\n"],
        analysis_metas=analysis_metas,
    )
    assert "<untrusted_related_files>" in prompt
    assert "crypto/keyring.py" in prompt
    assert "generate_ed25519_key" in prompt
    assert "Pseudocode Outline" in prompt


def test_deterministic_pre_verification_path_traversal_guard(tmp_path: Path) -> None:
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    outside_file = tmp_path / "outside.py"
    outside_file.write_text("valid = True\n", encoding="utf-8")

    sub_repo = tmp_path / "repo"
    sub_repo.mkdir()

    finding = Finding(
        title="Syntax error in python code",
        location="../outside.py:1",
        description="Fake syntax error",
        status="UNVERIFIED",
    )
    # Even if outside file exists, path traversal should be ignored and not crash/resolve outside
    result = _deterministic_pre_verification(finding, repo_root=sub_repo)
    assert result.location == "../outside.py:1"


def test_deterministic_pre_verification_documentation_avoidance_context(tmp_path: Path) -> None:
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    docs_dir = tmp_path / "docs" / "security"
    docs_dir.mkdir(parents=True)
    guide = docs_dir / "ssrf_prevention.md"
    guide.write_text(
        "# SSRF Prevention Guide\n\n"
        "Never use unvalidated URLs. Avoid insecure configurations such as binding to 0.0.0.0 "
        "or allowing unrestricted redirects. Mitigate SSRF by enforcing strict allowlists.\n",
        encoding="utf-8",
    )

    finding = Finding(
        title="Missing SSRF mitigation and insecure 0.0.0.0 binding",
        location="docs/security/ssrf_prevention.md:3-5",
        description="Documentation describes binding to 0.0.0.0 and SSRF vulnerabilities.",
        status="UNVERIFIED",
    )

    result = _deterministic_pre_verification(finding, repo_root=tmp_path)
    assert result.status == "INVALIDATED"
    assert result.verified is False
    assert result.reportable is False
    assert result.invalidation_reason is not None
    assert "avoiding said configuration" in result.invalidation_reason
