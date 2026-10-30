"""Tests for config write history mode preservation."""

import stat
from pathlib import Path

from devops_cli.config.write_history import _copy


def test_copy_preserves_source_mode(tmp_path: Path) -> None:
    """Test that _copy preserves the mode of the source file."""
    # Create a source file with 0600 mode
    source_file = tmp_path / "source.yaml"
    source_file.write_text("test: value\n")
    source_file.chmod(0o600)  # Set to read/write for owner only

    # Verify the initial mode
    initial_mode = source_file.stat().st_mode
    assert stat.S_IMODE(initial_mode) == 0o600

    # Copy to a destination file with redaction (this triggers the problematic code path)
    dest_file = tmp_path / "dest.yaml"
    _copy(source_file, dest_file, redact=[("test",)])

    # Verify the mode is preserved
    final_mode = dest_file.stat().st_mode
    assert stat.S_IMODE(final_mode) == 0o600


def test_copy_preserves_source_mode_no_redaction(tmp_path: Path) -> None:
    """Test that _copy preserves the mode of the source file when no redaction is used."""
    # Create a source file with 0600 mode
    source_file = tmp_path / "source.yaml"
    source_file.write_text("test: value\n")
    source_file.chmod(0o600)  # Set to read/write for owner only

    # Verify the initial mode
    initial_mode = source_file.stat().st_mode
    assert stat.S_IMODE(initial_mode) == 0o600

    # Copy to a destination file without redaction (this uses shutil.copy2 directly)
    dest_file = tmp_path / "dest.yaml"
    _copy(source_file, dest_file, redact=[])

    # Verify the mode is preserved
    final_mode = dest_file.stat().st_mode
    assert stat.S_IMODE(final_mode) == 0o600
