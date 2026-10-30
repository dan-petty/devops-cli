"""Tests for config file mode preservation."""

import stat
from pathlib import Path

from devops_cli.config.settings import _write_content


def test_write_content_preserves_existing_file_mode(tmp_path: Path) -> None:
    """Test that _write_content preserves the mode of an existing file."""
    # Create a config file with 0600 mode
    config_file = tmp_path / "config.yaml"
    config_file.write_text("test: value\n")
    config_file.chmod(0o600)  # Set to read/write for owner only

    # Verify the initial mode
    initial_mode = config_file.stat().st_mode
    assert stat.S_IMODE(initial_mode) == 0o600

    # Write new content
    new_content = b"test: new_value\n"
    _write_content(config_file, None, new_content)

    # Verify the mode is preserved
    final_mode = config_file.stat().st_mode
    assert stat.S_IMODE(final_mode) == 0o600


def test_write_content_sets_default_mode_for_new_file(tmp_path: Path) -> None:
    """Test that _write_content sets 0600 mode for a new file."""
    # Create path to a non-existent config file
    config_file = tmp_path / "new_config.yaml"

    # Write content to create the file
    new_content = b"test: value\n"
    _write_content(config_file, None, new_content)

    # Verify the new file has 0600 mode
    final_mode = config_file.stat().st_mode
    assert stat.S_IMODE(final_mode) == 0o600
