"""Tests for SIEM audit streaming and event logging."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.config.defaults import DEFAULT_DATA_DIR
from devops_cli.core.audit import _resolve_audit_log_dest, record_audit_event, stream_audit_records
from devops_cli.exceptions import SecurityError


def test_stream_audit_records(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "audit.jsonl"
    record_audit_event(
        command="devops k8s contexts",
        status="SUCCESS",
        log_file=log_file,
    )

    count = stream_audit_records("http://siem.example.test:8080", log_file=log_file)
    assert count == 1


def test_stream_audit_records_nonexistent(tmp_path: Path) -> None:
    """Non-existent audit file returns 0 streamed records."""
    assert (
        stream_audit_records("http://siem.example.test", log_file=tmp_path / "missing.jsonl") == 0
    )


def test_resolve_audit_log_dest_security_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_resolve_audit_log_dest rejects paths outside data_dir."""
    # Custom inside path
    allowed_file = DEFAULT_DATA_DIR / "audit_test.jsonl"
    monkeypatch.setenv("DEVOPS_CLI_AUDIT_LOG_DEST", str(allowed_file))
    assert _resolve_audit_log_dest(None) == allowed_file.resolve()

    # Outside path should raise SecurityError
    monkeypatch.setenv("DEVOPS_CLI_AUDIT_LOG_DEST", "/etc/passwd")
    with pytest.raises(SecurityError, match="must be within"):
        _resolve_audit_log_dest(None)


def test_resolve_audit_log_dest_and_stream_default_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify _resolve_audit_log_dest and stream_audit_records with default settings and OSError handling."""
    from unittest.mock import MagicMock, patch

    monkeypatch.delenv("DEVOPS_CLI_AUDIT_LOG_DEST", raising=False)

    # 1. Relative destination path in settings
    mock_settings = MagicMock()
    mock_settings.data.audit_log_path = Path(".data/audit.jsonl")

    with (
        patch("devops_cli.config.settings.load_settings", return_value=mock_settings),
        patch("devops_cli.core.repo.find_top_level_repo_root", return_value=tmp_path),
    ):
        resolved = _resolve_audit_log_dest(None)
        assert resolved == (tmp_path / ".data" / "audit.jsonl").resolve()

        # Stream with log_file=None (resolved from settings)
        count = stream_audit_records("http://siem.example.test")
        assert count == 0

    # 2. OSError handling during stream
    test_file = tmp_path / "test_audit.jsonl"
    test_file.write_text('{"event": "test"}\n', encoding="utf-8")
    with patch.object(Path, "open", side_effect=OSError("Read error")):
        count_err = stream_audit_records("http://siem.example.test", log_file=test_file)
        assert count_err == 0
