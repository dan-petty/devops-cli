"""Tests for OS Keyring secret health auditor and zero-plaintext compliance scanner."""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.config import app
from devops_cli.config.constants import CONST_CONFIG_DIR, CONST_CONFIG_PATH

pytestmark = pytest.mark.usefixtures("mock_keyring")

runner = CliRunner()

_UNPARSABLE_CONFIG = "ai:\n  api_key: FAKE-1022-value: x\n"


@pytest.fixture(autouse=True)
def _audit_in_tmp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run each audit in a tmp dir, so a developer's own config.yaml is never scanned."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def write_global_config() -> Iterator[Callable[[bytes], Path]]:
    """Write the global config file of the settings, which is in the isolated HOME of the worker.

    The teardown removes the file, and the config directory when the test made it, so the
    worker-home tripwire finds no state that stays.
    """
    config_dir_existed = CONST_CONFIG_DIR.exists()

    def write(content: bytes) -> Path:
        CONST_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONST_CONFIG_PATH.write_bytes(content)
        return CONST_CONFIG_PATH

    yield write
    CONST_CONFIG_PATH.unlink(missing_ok=True)
    if not config_dir_existed and CONST_CONFIG_DIR.exists():
        CONST_CONFIG_DIR.rmdir()


@pytest.fixture
def global_config_with_a_secret(write_global_config: Callable[[bytes], Path]) -> Path:
    """The global config file of the settings, with `ai.api_key` in plaintext."""
    return write_global_config(b"ai:\n  api_key: FAKE-2426-global-value\n")


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
    ) == (True, True, True, 15)

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
        "gitea.admin_password" in keys,
        "telemetry.logfire_token" in keys,
        "cloudflare.api_token" in keys,
        "service.webhook_secrets" in keys,
        "service.github_app.private_key" in keys,
        "firecrawl.api_key" in keys,
    ) == (
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
    )


def test_config_audit_keys_table_rendering() -> None:
    """Verify table rendering of key audit states, and the success line of a compliant audit."""
    result = runner.invoke(app, ["audit-keys"])
    assert result.exit_code == 0
    assert "Keyring & Secret Health Audit" in result.output
    assert "grafana.token" in result.output
    assert "Zero-Plaintext Check" in result.output
    assert "verified free of plaintext secrets" in result.output


def test_config_audit_keys_fails_on_a_plaintext_secret_in_the_table(
    cli: Callable[..., Any], config: Callable[..., Path]
) -> None:
    """A plaintext secret in the config file fails the audit: the table flags it, the alert names
    the leak, and the command exits 1."""
    config_file = config(grafana={"token": "FAKE-leaked-plaintext-token"})

    result = cli("config", "audit-keys")

    assert result.exit_code == 1
    assert "LEAK DETECTED" in result.output
    alert = result.output[result.output.index("Security Alert") :]
    assert f"{config_file.resolve()}:grafana.token" in alert
    assert "verified free of plaintext secrets" not in result.output


def test_config_audit_keys_fails_on_a_plaintext_secret_in_the_json_report(
    cli: Callable[..., Any], config: Callable[..., Path]
) -> None:
    """--json prints the full report of a plaintext secret, then the command exits 1."""
    config_file = config(grafana={"token": "FAKE-leaked-plaintext-token"})

    result = cli("config", "audit-keys", "--json")

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["is_compliant"] is False
    assert data["plaintext_leaks"] == [f"{config_file.resolve()}:grafana.token"]
    assert data["unaudited_config_files"] == []


def test_config_audit_keys_skips_a_top_level_setting_and_finds_the_secret_of_a_section(
    tmp_path: Path,
) -> None:
    """A top-level key with a scalar value is not a section, so the audit goes on to the next key
    and finds the plaintext secret of the section after it."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "log_level: INFO\ngrafana:\n  token: FAKE-2426-section-token\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["audit-keys", "--json"])

    data = json.loads(result.stdout)
    assert (result.exit_code, data["plaintext_leaks"], data["unaudited_config_files"]) == (
        1,
        [f"{config_file.resolve()}:grafana.token"],
        [],
    )


def test_config_audit_keys_finds_no_secret_key_in_a_config_file_whose_document_is_a_list(
    tmp_path: Path,
) -> None:
    """A config file whose YAML document is a list holds no key, so no key in it can be a
    plaintext secret: the audit scans the file and finds no leak."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("- FAKE-2426-list-item\n", encoding="utf-8")

    result = runner.invoke(app, ["audit-keys", "--json"])

    data = json.loads(result.stdout)
    assert (
        result.exit_code,
        str(config_file.resolve()) in data["scanned_config_files"],
        data["plaintext_leaks"],
        data["unaudited_config_files"],
    ) == (0, True, [], [])


@pytest.mark.parametrize("walk_finds_the_project_file", [False, True])
def test_config_audit_keys_fails_on_a_plaintext_secret_in_the_global_config_file(
    walk_finds_the_project_file: bool,
    cli: Callable[..., Any],
    global_config_with_a_secret: Path,
    isolate_devops_cli_config: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The settings merge the global config file and the project file, so the audit scans both.

    The project file holds no secret. `DEVOPS_CLI_CONFIG` names it, or the directory walk finds it
    as `.devcontainer/config.yaml` in the current directory (#2426).
    """
    project_file = isolate_devops_cli_config
    if walk_finds_the_project_file:
        project_file = tmp_path / ".devcontainer" / "config.yaml"
        project_file.parent.mkdir()
        shutil.copyfile(isolate_devops_cli_config, project_file)
        monkeypatch.delenv("DEVOPS_CLI_CONFIG")

    result = cli("config", "audit-keys", "--json")

    data = json.loads(result.stdout)
    assert (
        result.exit_code,
        data["is_compliant"],
        data["plaintext_leaks"],
        sorted(data["scanned_config_files"]),
    ) == (
        1,
        False,
        [f"{global_config_with_a_secret.resolve()}:ai.api_key"],
        sorted([str(global_config_with_a_secret.resolve()), str(project_file.resolve())]),
    )


def test_config_audit_keys_table_names_the_path_of_the_global_config_file_that_holds_a_secret(
    cli: Callable[..., Any],
    global_config_with_a_secret: Path,
    isolate_devops_cli_config: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The global file and the project file both have the name `config.yaml`, so the alert of the
    table names the full path of the file that holds the secret (#2426)."""
    project_file = tmp_path / ".devcontainer" / "config.yaml"
    project_file.parent.mkdir()
    shutil.copyfile(isolate_devops_cli_config, project_file)
    monkeypatch.delenv("DEVOPS_CLI_CONFIG")

    result = cli("config", "audit-keys")

    assert result.exit_code == 1
    alert = result.output[result.output.index("Security Alert") :]
    assert f"'{global_config_with_a_secret.resolve()}:ai.api_key'" in alert


_LOADER_CREDENTIAL = "FAKE-2426-value"


@pytest.mark.parametrize(
    ("content", "error_type"),
    [
        pytest.param(
            f"ai:\n  api_key: !!int {_LOADER_CREDENTIAL}\n".encode(), "ValueError", id="int"
        ),
        pytest.param(
            f"ai:\n  api_key: !!bool {_LOADER_CREDENTIAL}\n".encode(), "KeyError", id="bool"
        ),
        pytest.param(
            f"ai:\n  api_key: !!timestamp {_LOADER_CREDENTIAL}\n".encode(),
            "AttributeError",
            id="timestamp",
        ),
        pytest.param(
            f"ai:\n  api_key: {_LOADER_CREDENTIAL}\n  timeout: !!int ''\n".encode(),
            "IndexError",
            id="empty-int",
        ),
        pytest.param(
            f"ai:\n  api_key: {_LOADER_CREDENTIAL}\n  tags: {'[' * 10_000}{']' * 10_000}\n".encode(),
            "RecursionError",
            id="deep-nesting",
        ),
        pytest.param(
            f"ai:\n  api_key: {_LOADER_CREDENTIAL}\xe9\n".encode("latin-1"),
            "UnicodeDecodeError",
            id="not-utf-8",
        ),
    ],
)
def test_config_audit_keys_reports_a_global_config_file_that_the_yaml_loader_cannot_load_unaudited(
    content: bytes,
    error_type: str,
    cli: Callable[..., Any],
    write_global_config: Callable[[bytes], Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The audit refuses the errors of the YAML loader that the settings load refuses (#1468).

    The message of these errors quotes the value, so the audit names only the file and the type of
    the error. It prints the full report and exits 1.
    """
    global_config = write_global_config(content).resolve()

    with caplog.at_level(logging.WARNING):
        result = cli("config", "audit-keys", "--json")

    data = json.loads(result.stdout)
    assert (
        result.exit_code,
        data["unaudited_config_files"],
        data["plaintext_leaks"],
        data["is_compliant"],
    ) == (1, [str(global_config)], [], False)
    assert f"Could not audit config file {global_config}: {error_type}" in caplog.messages
    assert [
        text
        for text in (result.stdout, result.stderr, caplog.text)
        if _LOADER_CREDENTIAL.casefold() in text.casefold()
    ] == []


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
