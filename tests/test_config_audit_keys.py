"""Tests for OS Keyring secret health auditor and zero-plaintext compliance scanner."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.config import app

runner = CliRunner()

_UNPARSABLE_CONFIG = "ai:\n  api_key: FAKE-1022-value: x\n"


@pytest.fixture(autouse=True)
def _audit_in_tmp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run each audit in a tmp dir, so a developer's own config.yaml is never scanned."""
    monkeypatch.chdir(tmp_path)


def test_config_audit_keys_dry_run() -> None:
    """Verify dry-run execution of config audit-keys command."""
    result = runner.invoke(app, ["audit-keys", "--dry-run"])
    assert result.exit_code == 0
    assert "COMPLIANT_DRY_RUN" in result.output or "audit_keyring_and_secrets" in result.output


def test_config_audit_keys_json_output() -> None:
    """Verify structured JSON output from config audit-keys."""
    result = runner.invoke(app, ["audit-keys", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert (
        "keyring_backend" in data,
        "keys" in data,
        "is_compliant" in data,
        len(data["keys"]),
    ) == (True, True, True, 13)

    keys = {k["key"] for k in data["keys"]}
    assert (
        not [key for key in keys if key.partition(".")[0] == "github"],
        "grafana.token" in keys,
        "grafana.password" in keys,
        "argocd.token" in keys,
        "argocd.password" in keys,
        "ai.api_key" in keys,
        "qdrant.api_key" in keys,
        "valkey.password" in keys,
        "runs.index_password" in keys,
        "telemetry.logfire_token" in keys,
        "cloudflare.api_token" in keys,
        "service.webhook_secrets" in keys,
        "tavily.api_key" in keys,
    ) == (True, True, True, True, True, True, True, True, True, True, True, True, True)


def test_config_audit_keys_table_rendering() -> None:
    """Verify table rendering of key audit states."""
    result = runner.invoke(app, ["audit-keys"])
    assert result.exit_code == 0
    assert "Keyring & Secret Health Audit" in result.output
    assert "grafana.token" in result.output
    assert "Zero-Plaintext Check" in result.output


def test_config_audit_keys_plaintext_leak_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that a plaintext secret in config file triggers leak detection and non-compliant status."""
    leaked_config = tmp_path / "config.yaml"
    leaked_config.write_text("grafana:\n  token: FAKE-leaked-plaintext-token\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(leaked_config))

    result = runner.invoke(app, ["audit-keys", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["is_compliant"] is False
    assert any("grafana.token" in leak for leak in data["plaintext_leaks"])


def test_config_audit_keys_canonical_secret_leak_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Canonical secret options in plaintext config trigger leak detection."""
    leaked_config = tmp_path / "config.yaml"
    leaked_config.write_text("ai:\n  api_key: FAKE-ai-key\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(leaked_config))

    data = json.loads(runner.invoke(app, ["audit-keys", "--json"]).output)
    leaked = [leak.partition(":")[2] for leak in data["plaintext_leaks"]]
    assert (data["is_compliant"], leaked) == (False, ["ai.api_key"])


def test_config_audit_keys_never_logs_an_unparsable_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A config line the audit cannot parse is never printed or logged, only its position."""
    config = tmp_path / "config.yaml"
    config.write_text(_UNPARSABLE_CONFIG, encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(config))

    with caplog.at_level(logging.WARNING):
        result = runner.invoke(app, ["audit-keys"])

    messages = [record.getMessage() for record in caplog.records]
    assert "FAKE-1022-value" not in result.output
    assert "FAKE-1022-value" not in result.stderr
    assert not [message for message in messages if "FAKE-1022-value" in message]
    assert [
        message
        for message in messages
        if str(config.resolve()) in message
        and "ScannerError" in message
        and "line 2, column 27" in message
    ]


def test_config_audit_keys_reports_an_unparsable_file_unaudited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A config file the audit cannot parse is reported unaudited, not clean, and exits 1."""
    config = tmp_path / "config.yaml"
    config.write_text(_UNPARSABLE_CONFIG, encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(config))

    result = runner.invoke(app, ["audit-keys"])

    assert result.exit_code == 1
    assert "UNAUDITED" in result.output
    assert "CLEAN (0 Plaintext)" not in result.output
    assert "verified free of plaintext secrets" not in result.output


def test_config_audit_keys_json_lists_unaudited_files_apart_from_leaks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--json lists a file the audit cannot parse under unaudited_config_files, not as a leak."""
    config = tmp_path / "config.yaml"
    config.write_text(_UNPARSABLE_CONFIG, encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(config))

    result = runner.invoke(app, ["audit-keys", "--json"])

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["unaudited_config_files"] == [str(config.resolve())]
    assert data["plaintext_leaks"] == []
    assert data["is_compliant"] is False
    assert {key["compliant"] for key in data["keys"]} == {False}


def test_config_audit_keys_reports_an_undecodable_file_unaudited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A config file that is not UTF-8 is reported unaudited, logged without a position."""
    config = tmp_path / "config.yaml"
    config.write_bytes(b"ai:\n  api_key: FAKE\xff\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(config))

    with caplog.at_level(logging.WARNING):
        result = runner.invoke(app, ["audit-keys", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["unaudited_config_files"] == [str(config.resolve())]
    messages = [record.getMessage() for record in caplog.records]
    (message,) = [message for message in messages if str(config.resolve()) in message]
    assert "UnicodeDecodeError" in message
    assert "line " not in message
    assert "column " not in message


def test_config_audit_keys_reports_an_unconstructable_value_unaudited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A value PyYAML resolves but cannot build (an impossible date) leaves the file unaudited."""
    config = tmp_path / "config.yaml"
    config.write_text("ai:\n  api_key: 2024-13-45\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(config))

    result = runner.invoke(app, ["audit-keys", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["unaudited_config_files"] == [str(config.resolve())]
