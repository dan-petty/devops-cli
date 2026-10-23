"""A write of a config file keeps a copy of the file it replaces and records the change in the
audit log, never a value (#1921)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.settings import Settings, save_settings
from tests.support.fakes.clock import ClockFake

_WRITTEN_AT = datetime(2026, 10, 23, 16, 10, 5, tzinfo=UTC)
_STAMP = "20261023-161005"


def _config_writes(data_dir: Path) -> list[dict[str, Any]]:
    """The details of each config write the audit log holds, the oldest first."""
    log = data_dir / "logs" / "audit.jsonl"
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    return [record["details"] for record in records]


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def test_a_config_write_keeps_a_copy_of_the_file_it_replaces_and_records_the_changed_keys(
    tmp_path: Path, isolate_data_dir: Path, clock: ClockFake
) -> None:
    """A write that drops `ssh.key_prefix` leaves the old file in a copy beside it and a record
    that names the key, so a person can see the loss and undo it."""
    config = tmp_path / "project" / "config.yaml"
    save_settings(Settings.model_validate({"ssh": {"key_prefix": "devops_cli"}}), config)
    before = config.read_bytes()
    clock.move_to(_WRITTEN_AT)

    save_settings(Settings(), config)

    backup = config.with_name(f"config.yaml.bak-{_STAMP}")
    assert _names(config.parent) == ["config.yaml", f"config.yaml.bak-{_STAMP}"]
    assert backup.read_bytes() == before
    assert _config_writes(isolate_data_dir)[-1] == {
        "action": "config_write",
        "path": str(config),
        "backup": str(backup),
        "changed_keys": ["ssh.key_prefix"],
    }


def test_the_first_write_of_a_config_file_records_every_key_and_keeps_no_copy(
    tmp_path: Path, isolate_data_dir: Path
) -> None:
    config = tmp_path / "project" / "config.yaml"
    settings = Settings.model_validate({"ssh": {"key_prefix": "devops_cli"}})

    save_settings(settings, config)

    [written] = _config_writes(isolate_data_dir)
    assert _names(config.parent) == ["config.yaml"]
    assert written["backup"] is None
    assert "ssh.key_prefix" in written["changed_keys"]
    assert written["changed_keys"] == sorted(_dotted_keys(yaml.safe_load(config.read_bytes())))


def _dotted_keys(mapping: dict[str, Any], prefix: str = "") -> list[str]:
    """The dotted name of each value in `mapping` that is not a mapping with keys."""
    names: list[str] = []
    for key, value in mapping.items():
        if isinstance(value, dict) and value:
            names += _dotted_keys(value, f"{prefix}{key}.")
        else:
            names.append(f"{prefix}{key}")
    return names


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

    save_settings(Settings(), config)

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

    save_settings(Settings(), config)
    save_settings(Settings.model_validate({"ssh": {"key_prefix": "other"}}), config)

    backup = config.with_name(f"config.yaml.bak-{_STAMP}")
    assert _names(config.parent) == ["config.yaml", backup.name]
    assert backup.read_text(encoding="utf-8") == "ssh:\n  key_prefix: devops_cli\n"
    assert [write["backup"] for write in _config_writes(isolate_data_dir)] == [str(backup)] * 2


def test_a_config_write_that_changes_no_byte_writes_nothing_and_records_nothing(
    tmp_path: Path, isolate_data_dir: Path, clock: ClockFake
) -> None:
    config = tmp_path / "project" / "config.yaml"
    save_settings(Settings(), config)
    written = config.stat().st_mtime_ns
    clock.move_to(_WRITTEN_AT)

    save_settings(Settings(), config)

    assert _names(config.parent) == ["config.yaml"]
    assert config.stat().st_mtime_ns == written
    assert len(_config_writes(isolate_data_dir)) == 1


def test_config_set_records_its_command_and_the_key_it_changed(
    cli: Any, isolate_devops_cli_config: Path, isolate_data_dir: Path
) -> None:
    """The record names the command path, which holds no argument and so no typed value."""
    assert cli("config", "set", "github.default_org", "first-org").exit_code == 0

    result = cli("config", "set", "github.default_org", "second-org")

    log = isolate_data_dir / "logs" / "audit.jsonl"
    last = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert result.exit_code == 0
    assert (last["command"], last["details"]["changed_keys"]) == (
        "devops config set",
        ["github.default_org"],
    )
    assert "second-org" not in log.read_text(encoding="utf-8")
