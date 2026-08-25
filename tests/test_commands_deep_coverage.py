"""Comprehensive tests covering workspace, uv, ssh, tls, scan, review, github, core repo/audit."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.ai.review_schema import ReviewSessionPayload
from devops_cli.commands.review import app as review_app
from devops_cli.commands.scan import app as scan_app
from devops_cli.commands.ssh import app as ssh_app
from devops_cli.commands.tls import app as tls_app
from devops_cli.commands.uv import app as uv_app
from devops_cli.commands.workspace import app as workspace_app
from devops_cli.core.audit import record_audit_event, stream_audit_records
from devops_cli.core.repo import get_repo_origin_name, is_ignored_by_git
from devops_cli.git.operations import iter_workspace_repos
from devops_cli.github.client import GitHubClient
from devops_cli.models.ssh import ManagedSSHKey
from devops_cli.models.tls import CertificateInfo

runner = CliRunner()


def _mock_proc(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["cmd"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ── Workspace Commands ────────────────────────────────────────────────────────
def test_workspace_commands(tmp_path: Path) -> None:
    ws_file = tmp_path / "test.code-workspace"
    ws_file.write_text(json.dumps({"folders": [{"path": "."}]}), encoding="utf-8")

    with patch("devops_cli.commands.workspace._PROJECT_ROOT", tmp_path):
        res_add = runner.invoke(workspace_app, ["add", str(tmp_path), "--workspace", str(ws_file)])
        assert res_add.exit_code == 0

        res_remove = runner.invoke(
            workspace_app, ["remove", str(tmp_path), "--workspace", str(ws_file)]
        )
        assert res_remove.exit_code == 0

        res_gen = runner.invoke(workspace_app, ["generate", "--workspace", str(ws_file)])
        assert res_gen.exit_code == 0


# ── UV Commands ───────────────────────────────────────────────────────────────
def test_uv_commands() -> None:
    with patch("devops_cli.commands.uv.run_subprocess", return_value=_mock_proc(0)):
        res_sync = runner.invoke(uv_app, ["sync", "--frozen"])
        assert res_sync.exit_code == 0

        res_lock = runner.invoke(uv_app, ["lock", "--upgrade"])
        assert res_lock.exit_code == 0

        res_py = runner.invoke(uv_app, ["python-install", "--version", "3.14"])
        assert res_py.exit_code == 0


# ── SSH Commands ──────────────────────────────────────────────────────────────
def test_ssh_commands(tmp_path: Path) -> None:
    mock_key_info = ManagedSSHKey(
        path=tmp_path / "id_ed25519-2024JAN15",
        key_date=date(2024, 1, 15),
        age_days=10,
    )
    priv_file = tmp_path / "id_ed25519-2024JAN15"
    pub_file = tmp_path / "id_ed25519-2024JAN15.pub"
    priv_file.write_text("private", encoding="utf-8")
    pub_file.write_text("ssh-ed25519 AAAA test@domain.com", encoding="utf-8")

    with (
        patch("devops_cli.crypto.ssh_keys.list_managed_keys_info", return_value=[mock_key_info]),
        patch("devops_cli.crypto.ssh_keys.generate_ed25519_key"),
        patch("devops_cli.crypto.ssh_keys.find_newest_key", return_value=priv_file),
        patch("devops_cli.github.ssh.register_key_on_github", return_value=True),
        patch("devops_cli.config.settings.get_github_token", return_value="ghp_test"),
        patch("devops_cli.commands.ssh._configure_git_signing"),
    ):
        res_gen = runner.invoke(
            ssh_app, ["generate", "--key-dir", str(tmp_path), "--comment", "test@domain.com"]
        )
        assert res_gen.exit_code == 0

        res_stat = runner.invoke(ssh_app, ["status", "--key-dir", str(tmp_path)])
        assert res_stat.exit_code == 0

        res_audit = runner.invoke(ssh_app, ["audit", "--key-dir", str(tmp_path)])
        assert res_audit.exit_code == 0

        res_reg = runner.invoke(
            ssh_app, ["register", "--key-file", str(priv_file), "--title", "My Key"]
        )
        assert res_reg.exit_code == 0


# ── TLS Commands ──────────────────────────────────────────────────────────────
def test_tls_commands(tmp_path: Path) -> None:
    ca_cert = tmp_path / "ca.crt"
    ca_key = tmp_path / "ca.key"
    srv_cert = tmp_path / "srv.crt"
    srv_key = tmp_path / "srv.key"

    mock_info = CertificateInfo(
        subject={"CN": "example.com"},
        issuer={"CN": "Test CA"},
        not_before=datetime.now(UTC),
        not_after=datetime.now(UTC),
        sans_dns=["example.com"],
        serial_number="12345",
        signature_algorithm="sha256WithRSAEncryption",
        is_ca=False,
    )

    with (
        patch(
            "devops_cli.commands.tls.generate_ca_certificate",
            return_value=(ca_cert, ca_key),
        ),
        patch(
            "devops_cli.commands.tls.generate_server_certificate",
            return_value=(srv_cert, srv_key, srv_cert),
        ),
        patch("devops_cli.commands.tls.inspect_certificate", return_value=mock_info),
    ):
        res_ca = runner.invoke(tls_app, ["ca", "--output-dir", str(tmp_path)])
        assert res_ca.exit_code == 0

        res_cert = runner.invoke(
            tls_app,
            [
                "cert",
                "--common-name",
                "example.com",
                "--ca-cert",
                str(ca_cert),
                "--ca-key",
                str(ca_key),
                "--output-dir",
                str(tmp_path),
            ],
        )
        assert res_cert.exit_code == 0

        srv_cert.write_text(
            "-----BEGIN CERTIFICATE-----\n-----END CERTIFICATE-----", encoding="utf-8"
        )
        res_insp = runner.invoke(tls_app, ["inspect", str(srv_cert)])
        assert res_insp.exit_code == 0


# ── Scan & Review Commands ────────────────────────────────────────────────────
def test_scan_and_review_commands(tmp_path: Path) -> None:
    res_scan = runner.invoke(scan_app, ["--dry-run"])
    assert res_scan.exit_code == 0

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


# ── GitHub Client & Core Repo / Audit ─────────────────────────────────────────
def test_github_client_and_core_repo_audit(tmp_path: Path) -> None:
    gh = GitHubClient(token="ghp_test")
    assert gh is not None

    (tmp_path / ".git").mkdir()
    (tmp_path / "org" / "repo1" / ".git").mkdir(parents=True)

    mock_git_remote = "git@github.com:org/repo.git\n"
    with patch(
        "devops_cli.core.process.run_subprocess", return_value=_mock_proc(0, mock_git_remote)
    ):
        origin = get_repo_origin_name(tmp_path)
        assert origin == "org/repo"

    (tmp_path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    assert is_ignored_by_git(tmp_path, tmp_path / "ignored.txt") is True
    assert is_ignored_by_git(tmp_path, tmp_path / ".git" / "config") is True

    repos = list(iter_workspace_repos(tmp_path))
    assert len(repos) >= 1

    audit_file = tmp_path / "audit.jsonl"
    record_audit_event("TEST_ACTION", details={"status": "ok"}, log_file=audit_file)
    count = stream_audit_records("https://siem.example.com/logs", log_file=audit_file)
    assert count == 1
