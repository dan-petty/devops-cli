"""Tests for SIEM audit streaming and event logging."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_DATA_DIR
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
    """_resolve_audit_log_dest rejects paths outside CONST_DATA_DIR."""
    # Custom inside path
    allowed_file = CONST_DATA_DIR / "audit_test.jsonl"
    monkeypatch.setenv("DEVOPS_CLI_AUDIT_LOG_DEST", str(allowed_file))
    assert _resolve_audit_log_dest(None) == allowed_file.resolve()

    # Outside path should raise SecurityError
    monkeypatch.setenv("DEVOPS_CLI_AUDIT_LOG_DEST", "/etc/passwd")
    with pytest.raises(SecurityError, match="must be within"):
        _resolve_audit_log_dest(None)
