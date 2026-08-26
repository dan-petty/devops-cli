"""Unit tests covering the devops review CLI subcommands and workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review_schema import ReviewSessionPayload
from devops_cli.commands.review import app as review_app

runner = CliRunner()


def test_review_explain() -> None:
    """Verify review subcommands with --explain flag."""
    res = runner.invoke(review_app, ["path", "--explain"])
    assert res.exit_code == 0

    res_pr = runner.invoke(review_app, ["pr", "123", "--explain"])
    assert res_pr.exit_code == 0

    res_br = runner.invoke(review_app, ["branch", "feat/test", "--explain"])
    assert res_br.exit_code == 0


def test_review_path_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops review path workflow execution."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    py_file = tmp_path / "app.py"
    py_file.write_text("def run():\n    pass\n", encoding="utf-8")

    mock_wf = [(MagicMock(title="Architect", name="architect"), "Review comments")]
    with (
        patch(
            "devops_cli.commands.review._prepare_path_content",
            return_value=(["code page"], "Path Review", "AGENTS.md"),
        ),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=mock_wf),
        patch("devops_cli.commands.review.load_settings"),
    ):
        res = runner.invoke(review_app, ["path", str(py_file), "--persona", "architect"])
        assert res.exit_code == 0


def test_review_branch_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops review branch workflow execution."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )

    mock_wf = [(MagicMock(title="DevSecOps", name="devsecops"), "Security comments")]
    with (
        patch(
            "devops_cli.commands.review._prepare_branch_content",
            return_value=(["diff content"], "Branch Review", "AGENTS.md"),
        ),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=mock_wf),
        patch("devops_cli.commands.review.load_settings"),
    ):
        res = runner.invoke(review_app, ["branch", "feat/my-feature", "--persona", "devsecops"])
        assert res.exit_code == 0


def test_review_pr_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops review pr workflow execution."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_pull = MagicMock()
    mock_wf = [(MagicMock(title="QA", name="qa"), "QA feedback")]

    with (
        patch("devops_cli.config.settings.get_github_token", return_value="ghp_test"),
        patch(
            "devops_cli.commands.review._prepare_pr_content",
            return_value=(["pr diff"], "PR 10", "AGENTS.md", mock_pull, "org/repo"),
        ),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=mock_wf),
        patch("devops_cli.commands.review.load_settings"),
    ):
        res = runner.invoke(review_app, ["pr", "10", "--persona", "qa"])
        assert res.exit_code == 0


def test_review_verify_and_apply_patch(tmp_path: Path) -> None:
    """Verify apply-patch subcommand execution."""
    with patch("devops_cli.commands.review.stage_finding_patch", return_value=True):
        res_patch = runner.invoke(review_app, ["apply-patch", "session-123", "--index", "1"])
        assert res_patch.exit_code == 0


def test_review_findings_stats_export_feedback(tmp_path: Path) -> None:
    """Verify review findings, stats, and export-feedback subcommands."""
    session_dir = tmp_path / "session_1"
    session_dir.mkdir()
    findings_file = session_dir / "findings.json"
    session_payload = ReviewSessionPayload(
        target_type="path",
        target_ref=str(tmp_path),
        findings=[],
        generated_at=datetime.now(UTC).isoformat(),
    )
    findings_file.write_text(session_payload.model_dump_json(), encoding="utf-8")

    with (
        patch("devops_cli.commands.review._find_session_dir", return_value=session_dir),
        patch(
            "devops_cli.commands.review.export_invalidated_feedback",
            return_value=(1, tmp_path / "fb.jsonl"),
        ),
    ):
        res_find = runner.invoke(review_app, ["findings"])
        assert res_find.exit_code == 0

        res_stats = runner.invoke(review_app, ["stats"])
        assert res_stats.exit_code == 0

        res_fb = runner.invoke(
            review_app,
            [
                "export-feedback",
                "--reviews-dir",
                str(tmp_path),
                "--output",
                str(tmp_path / "fb.jsonl"),
            ],
        )
        assert res_fb.exit_code == 0


def test_review_verify_command(tmp_path: Path) -> None:
    """Verify devops review verify updating finding status."""
    from devops_cli.ai.review_schema import SavedFinding

    session_dir = tmp_path / "session_verify"
    session_dir.mkdir()
    findings_file = session_dir / "findings.json"

    f1 = SavedFinding(
        title="SQL Injection",
        location="src/db.py:10",
        description="Raw SQL concatenation",
        fix="Use parameters",
        status="UNVERIFIED",
    )
    f2 = SavedFinding(
        title="Weak Cryptography",
        location="src/crypto.py:20",
        description="MD5 usage",
        fix="Use SHA256",
        status="UNVERIFIED",
    )
    session_payload = ReviewSessionPayload(
        target_type="path",
        target_ref=str(tmp_path),
        findings=[f1, f2],
        generated_at=datetime.now(UTC).isoformat(),
    )
    findings_file.write_text(session_payload.model_dump_json(), encoding="utf-8")

    with patch("devops_cli.ai.review.runner._find_session_dir", return_value=session_dir):
        # Update by index
        res_idx = runner.invoke(
            review_app, ["verify", "session_verify", "--index", "1", "--status", "VERIFIED"]
        )
        assert res_idx.exit_code == 0
        assert "VERIFIED" in res_idx.output

        # Update by title pattern
        res_title = runner.invoke(
            review_app,
            [
                "verify",
                "session_verify",
                "--title",
                "Weak Crypto",
                "--status",
                "INVALIDATED",
                "--reason",
                "False positive",
            ],
        )
        assert res_title.exit_code == 0
        assert "INVALIDATED" in res_title.output

        # Index out of bounds
        res_oob = runner.invoke(
            review_app, ["verify", "session_verify", "--index", "99", "--status", "VERIFIED"]
        )
        assert res_oob.exit_code == 1

        # Invalid status choice
        res_bad_st = runner.invoke(
            review_app, ["verify", "session_verify", "--index", "1", "--status", "INVALID_CHOICE"]
        )
        assert res_bad_st.exit_code == 1

        # Neither index nor title provided
        res_no_spec = runner.invoke(
            review_app, ["verify", "session_verify", "--status", "VERIFIED"]
        )
        assert res_no_spec.exit_code == 1

        # Findings command filtering
        res_unver = runner.invoke(
            review_app, ["findings", "--session", "session_verify", "--unverified"]
        )
        assert res_unver.exit_code == 0

        res_ver = runner.invoke(
            review_app, ["findings", "--session", "session_verify", "--verified"]
        )
        assert res_ver.exit_code == 0

        res_inval = runner.invoke(
            review_app, ["findings", "--session", "session_verify", "--invalidated"]
        )
        assert res_inval.exit_code == 0


def test_review_stats_and_export_empty(tmp_path: Path) -> None:
    """Verify review stats and export-feedback empty behavior."""
    # Stats with non-existent directory
    res_no_dir = runner.invoke(
        review_app, ["stats", "--reviews-dir", str(tmp_path / "nonexistent")]
    )
    assert res_no_dir.exit_code == 0

    # Stats with empty directory
    empty_dir = tmp_path / "empty_reviews"
    empty_dir.mkdir()
    res_empty = runner.invoke(review_app, ["stats", "--reviews-dir", str(empty_dir)])
    assert res_empty.exit_code == 0

    # Export feedback when count is 0
    with patch(
        "devops_cli.commands.review.export_invalidated_feedback",
        return_value=(0, tmp_path / "empty.jsonl"),
    ):
        res_exp_0 = runner.invoke(review_app, ["export-feedback", "--reviews-dir", str(empty_dir)])
        assert res_exp_0.exit_code == 0


def test_review_error_branches_and_patch_failure(tmp_path: Path) -> None:
    """Verify error branches for missing session dirs, missing findings.json, and apply-patch failure."""
    # 1. verify with non-existent session
    res_no_sess = runner.invoke(review_app, ["verify", "nonexistent_sess_123", "--index", "1"])
    assert res_no_sess.exit_code == 1

    # 2. verify with missing findings.json
    empty_sess = tmp_path / "empty_sess"
    empty_sess.mkdir()
    with patch("devops_cli.commands.review._find_session_dir", return_value=empty_sess):
        res_no_find = runner.invoke(review_app, ["verify", "empty_sess", "--index", "1"])
        assert res_no_find.exit_code == 1

        # findings with missing findings.json
        res_find_none = runner.invoke(review_app, ["findings", "--session", "empty_sess"])
        assert res_find_none.exit_code == 0

    # 3. apply-patch failure
    with patch("devops_cli.commands.review.stage_finding_patch", return_value=False):
        res_patch_fail = runner.invoke(review_app, ["apply-patch", "sess-1", "--index", "1"])
        assert res_patch_fail.exit_code == 1


def test_review_multiple_targets_and_findings_options(tmp_path: Path) -> None:
    """Verify review path with multiple file targets, patterns, and findings formatting."""
    f1 = tmp_path / "app1.py"
    f2 = tmp_path / "app2.py"
    f1.write_text("def a(): pass\n", encoding="utf-8")
    f2.write_text("def b(): pass\n", encoding="utf-8")

    with (
        patch("devops_cli.commands.review._execute_review_workflow") as mock_exec,
        patch("devops_cli.ai.review.runner._is_allowed_review_boundary", return_value=True),
    ):
        res_multi = runner.invoke(
            review_app, ["path", str(f1), str(f2), "--pattern", "*.py", "--persona", "architect"]
        )
        assert res_multi.exit_code == 0
        mock_exec.assert_called_once()


def test_review_verify_stats_and_export_extended(tmp_path: Path) -> None:
    """Verify review verify with title pattern, stats false positive rates, and apply-patch success."""
    from devops_cli.ai.review_schema import ReviewSessionPayload, SavedFinding

    # Setup session with findings
    sess_dir = tmp_path / "rev_sess_1"
    sess_dir.mkdir()
    findings_file = sess_dir / "findings.json"

    f1 = SavedFinding(
        id="f-001",
        persona="devsecops",
        severity="HIGH",
        title="Hardcoded API Key",
        location="src/app.py:10",
        description="Found sensitive secret in source",
        status="UNVERIFIED",
    )
    f2 = SavedFinding(
        id="f-002",
        persona="architect",
        severity="MEDIUM",
        title="Cyclic Dependency",
        location="src/mod.py:20",
        description="Circular import between modules",
        status="UNVERIFIED",
    )
    payload = ReviewSessionPayload(
        target="src/",
        timestamp="2026-08-26T12:00:00Z",
        findings=[f1, f2],
    )
    findings_file.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

    with patch("devops_cli.ai.review.runner._find_session_dir", return_value=sess_dir):
        # 1. verify with title pattern

        res_ver_title = runner.invoke(
            review_app,
            [
                "verify",
                "rev_sess_1",
                "--title",
                "Hardcoded",
                "--status",
                "INVALIDATED",
                "--reason",
                "False positive test token",
            ],
        )
        assert res_ver_title.exit_code == 0
        assert "status → INVALIDATED" in res_ver_title.output

        # 2. verify with invalid status
        res_ver_bad_st = runner.invoke(
            review_app, ["verify", "rev_sess_1", "--index", "2", "--status", "UNKNOWN_STATUS"]
        )
        assert res_ver_bad_st.exit_code == 1

        # 3. verify with index out of bounds
        res_ver_oob = runner.invoke(
            review_app, ["verify", "rev_sess_1", "--index", "99", "--status", "VERIFIED"]
        )
        assert res_ver_oob.exit_code == 1

        # 4. verify with status MITIGATED
        res_ver_mit = runner.invoke(
            review_app, ["verify", "rev_sess_1", "--index", "2", "--status", "MITIGATED"]
        )
        assert res_ver_mit.exit_code == 0

    # 5. stats command with sessions
    res_stats = runner.invoke(review_app, ["stats", "--reviews-dir", str(tmp_path)])
    assert res_stats.exit_code == 0
    assert "Finding Status Breakdown" in res_stats.output
    assert "Persona False Positive Rate" in res_stats.output

    # 6. apply-patch success
    with patch("devops_cli.commands.review.stage_finding_patch", return_value=True):
        res_patch_ok = runner.invoke(review_app, ["apply-patch", "rev_sess_1", "--index", "1"])
        assert res_patch_ok.exit_code == 0

    # 7. findings command with --details pretty formatting
    with patch("devops_cli.ai.review.runner._find_session_dir", return_value=sess_dir):
        res_details = runner.invoke(
            review_app, ["findings", "--session", "rev_sess_1", "--details"]
        )
        assert res_details.exit_code == 0
        assert "Finding #1" in res_details.output
        assert "Hardcoded API Key" in res_details.output
        assert "Found sensitive secret in source" in res_details.output


def test_format_clean_text_field_and_finding_unwrapping() -> None:
    """Verify that format_clean_text_field unwraps raw lists, tuples, and stringified Python lists."""
    from devops_cli.ai.review_schema import Finding, format_clean_text_field

    # Test raw list of strings
    raw_list = ["Step 1: Validate input", "Step 2: Apply boundary check"]
    assert (
        format_clean_text_field(raw_list) == "Step 1: Validate input\nStep 2: Apply boundary check"
    )

    # Test stringified Python list
    stringified_list = "['Validate module path prefix', 'Reject untrusted modules']"
    cleaned = format_clean_text_field(stringified_list)
    assert cleaned == "Validate module path prefix\nReject untrusted modules"
    assert "['" not in cleaned

    # Test Finding initialization with list fix and description
    finding_dict = {
        "title": ["Insecure", "Deserialization"],
        "location": "src/loader.py:10",
        "description": ["Avoid pickle.loads", "Use json.loads instead"],
        "fix": ["Replace pickle with json", "Add schema validation"],
        "references": "['https://cwe.mitre.org/995', 'https://owasp.org']",
    }
    f = Finding(**finding_dict)  # type: ignore[arg-type]
    assert f.title == "Insecure Deserialization"
    assert f.description == "Avoid pickle.loads\nUse json.loads instead"
    assert f.fix == "Replace pickle with json\nAdd schema validation"
    assert f.references == ["https://cwe.mitre.org/995", "https://owasp.org"]
