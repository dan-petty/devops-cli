"""Tests for config file mode preservation (#2745)."""

from __future__ import annotations

import stat
from pathlib import Path

from devops_cli.config.settings import _write_content


def test_write_content_preserves_existing_file_mode(tmp_path: Path) -> None:
    """_write_content preserves the mode of an existing config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("test: value\n", encoding="utf-8")
    config_file.chmod(0o600)

    assert stat.S_IMODE(config_file.stat().st_mode) == 0o600

    _write_content(config_file, b"test: value\n", b"test: new_value\n", [])

    assert stat.S_IMODE(config_file.stat().st_mode) == 0o600


def test_write_content_creates_new_file_with_0600_mode(tmp_path: Path) -> None:
    """_write_content creates a new config file with mode 0600, never 0644."""
    config_file = tmp_path / "new_config.yaml"

    _write_content(config_file, None, b"test: new_value\n", [])

    assert stat.S_IMODE(config_file.stat().st_mode) == 0o600
