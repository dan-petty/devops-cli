"""A write of a config file keeps a copy of the file it replaces and records the change in the
audit log, never a value (#1921)."""

from __future__ import annotations

import json
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.config.settings import load_settings, save_settings
from devops_cli.config.write_history import _copy
from tests.support.config_writes import config_writes, written_keys
from tests.support.fakes.clock import ClockFake

_WRITTEN_AT = datetime(2026, 10, 23, 16, 10, 5, tzinfo=UTC)
_STAMP = "20261023-161005"


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def _save_key_prefix(prefix: str, target: Path | None = None) -> None:
    """Save the loaded settings with `ssh.key_prefix` changed to `prefix`."""
    settings = load_settings()
    settings.ssh.key_prefix = prefix
    save_settings(settings, target)


def test_a_config_write_keeps_a_copy_of_the_file_it_replaces_and_records_the_changed_keys(
    config: Any, isolate_data_dir: Path, clock: ClockFake
) -> None:
    """A write that changes `ssh.key_prefix` leaves the old file in a copy beside it and a record
    that names the key, so a person can see the change and undo it."""
    path = config(ssh={"key_prefix": "devops_cli"})
    before = path.read_bytes()
    clock.move_to(_WRITTEN_AT)

    _save_key_prefix("other")

    backup = path.with_name(f"config.yaml.bak-{_STAMP}")
    assert _names(path.parent) == ["config.yaml", f"config.yaml.bak-{_STAMP}"]
    assert backup.read_bytes() == before
    assert config_writes(isolate_data_dir) == [
        {
            "action": "config_write",
            "path": str(path),
            "backup": str(backup),
            "changed_keys": ["ssh.key_prefix"],
        }
    ]


def test_the_first_write_of_a_config_file_records_its_keys_and_keeps_no_copy(
    tmp_path: Path, isolate_data_dir: Path
) -> None:
    config = tmp_path / "project" / "config.yaml"

    _save_key_prefix("devops_cli", config)

    [written] = config_writes(isolate_data_dir)
    assert _names(config.parent) == ["config.yaml"]
    assert (written["backup"], written["changed_keys"]) == (None, ["ssh.key_prefix"])


def test_a_config_write_keeps_the_newest_ten_copies_and_no_file_a_person_made(
    tmp_path: Path, clock: ClockFake
) -> None:
    config = tmp_path / "project" / "config.yaml"
    config.parent.mkdir()
    config.write_text("ssh:\n  key_prefix: devops_cli\n", encoding="utf-8")
    older = [f"config.yaml.bak-20261001-0000{second:02d}" for second in range(10)]
    for name in [*older, "config.yaml.bak-mine"]:
        (config.parent / name).write_text("old\n", encoding="utf-8")
    clock.move_to(_WRITTEN_AT)

    _save_key_prefix("other", config)

    assert _names(config.parent) == sorted(
        ["config.yaml", *older[1:], f"config.yaml.bak-{_STAMP}", "config.yaml.bak-mine"]
    )


def test_a_second_write_in_the_same_second_keeps_the_copy_of_the_older_state(
    tmp_path: Path, isolate_data_dir: Path, clock: ClockFake
) -> None:
    config = tmp_path / "project" / "config.yaml"
    config.parent.mkdir()
    config.write_text("ssh:\n  key_prefix: devops_cli\n", encoding="utf-8")
    clock.move_to(_WRITTEN_AT)

    _save_key_prefix("first", config)
    _save_key_prefix("other", config)

    backup = config.with_name(f"config.yaml.bak-{_STAMP}")
    assert _names(config.parent) == ["config.yaml", backup.name]
    assert backup.read_text(encoding="utf-8") == "ssh:\n  key_prefix: devops_cli\n"
    assert [write["backup"] for write in config_writes(isolate_data_dir)] == [str(backup)] * 2


def test_a_config_write_that_changes_no_byte_writes_nothing_and_records_nothing(
    tmp_path: Path, isolate_data_dir: Path, clock: ClockFake
) -> None:
    """The changed key already holds its new value in the file, so no byte changes."""
    config = tmp_path / "project" / "config.yaml"
    config.parent.mkdir()
    config.write_text("ssh:\n  key_prefix: devops_cli\n", encoding="utf-8")
    written = config.stat().st_mtime_ns
    clock.move_to(_WRITTEN_AT)

    _save_key_prefix("devops_cli", config)
    save_settings(load_settings(), config)

    assert _names(config.parent) == ["config.yaml"]
    assert config.stat().st_mtime_ns == written
    assert config_writes(isolate_data_dir) == []


def test_config_set_records_its_command_and_writes_the_key_it_changed_alone(
    cli: Any, isolate_devops_cli_config: Path, isolate_data_dir: Path
) -> None:
    """The record names the command path, which holds no argument and so no typed value."""
    before = isolate_devops_cli_config.read_text(encoding="utf-8")

    result = cli("config", "set", "github.default_org", "first-org")

    log = (isolate_data_dir / "logs" / "audit.jsonl").read_text(encoding="utf-8")
    last = json.loads(log.splitlines()[-1])
    assert result.exit_code == 0
    assert (
        last["command"],
        last["details"]["changed_keys"],
        isolate_devops_cli_config.read_text(encoding="utf-8"),
    ) == (
        "devops config set",
        ["github.default_org"],
        before + "github:\n  default_org: first-org\n",
    )
    assert "first-org" not in log


def test_config_set_of_a_credential_writes_no_config_file(
    cli: Any, isolate_devops_cli_config: Path, isolate_data_dir: Path, keyring_store: Any
) -> None:
    """The credential goes to the keyring, and the config file stays as it is."""
    before = isolate_devops_cli_config.read_text(encoding="utf-8")

    result = cli("config", "set", "grafana.token", "example-token")

    assert (
        result.exit_code,
        isolate_devops_cli_config.read_text(encoding="utf-8"),
        written_keys(isolate_data_dir),
    ) == (0, before, [])


def test_copy_preserves_source_mode(tmp_path: Path) -> None:
    """_copy preserves the mode of the source file when redacting credentials."""
    source_file = tmp_path / "source.yaml"
    source_file.write_text("test: value\n", encoding="utf-8")
    source_file.chmod(0o600)

    assert stat.S_IMODE(source_file.stat().st_mode) == 0o600

    dest_file = tmp_path / "dest.yaml"
    _copy(source_file, dest_file, redact=[("test",)])

    assert stat.S_IMODE(dest_file.stat().st_mode) == 0o600


def test_copy_preserves_source_mode_no_redaction(tmp_path: Path) -> None:
    """_copy preserves the mode of the source file when no redaction is requested."""
    source_file = tmp_path / "source.yaml"
    source_file.write_text("test: value\n", encoding="utf-8")
    source_file.chmod(0o600)

    assert stat.S_IMODE(source_file.stat().st_mode) == 0o600

    dest_file = tmp_path / "dest.yaml"
    _copy(source_file, dest_file, redact=[])

    assert stat.S_IMODE(dest_file.stat().st_mode) == 0o600
