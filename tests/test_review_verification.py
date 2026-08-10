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
