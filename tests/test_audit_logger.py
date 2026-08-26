"""Tests for SIEM audit trail logger and log destination resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.core.audit import _resolve_audit_log_dest, record_audit_event
from devops_cli.exceptions import SecurityError


def test_record_audit_event(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "audit.jsonl"
    record = record_audit_event(
        command="devops k8s contexts",
        status="SUCCESS",
        duration_ms=45.2,
        details={"cluster": "minikube"},
        log_file=log_file,
    )

    assert record.command == "devops k8s contexts"
    assert record.status == "SUCCESS"
    assert record.details == {"cluster": "minikube"}
    assert log_file.exists()

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["command"] == "devops k8s contexts"
    assert data["status"] == "SUCCESS"


def test_resolve_audit_log_dest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _resolve_audit_log_dest boundaries and safety checks."""
    (tmp_path / ".data").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    monkeypatch.setenv("DEVOPS_CLI_AUDIT_LOG_DEST", str(tmp_path / ".data" / "custom.jsonl"))
    dest = _resolve_audit_log_dest(None)
    assert dest == tmp_path / ".data" / "custom.jsonl"

    monkeypatch.setenv("DEVOPS_CLI_AUDIT_LOG_DEST", "/etc/passwd")
    with pytest.raises((ValueError, SecurityError), match="must be within"):
        _resolve_audit_log_dest(None)

    monkeypatch.delenv("DEVOPS_CLI_AUDIT_LOG_DEST", raising=False)
    assert _resolve_audit_log_dest(None) is not None


def test_stream_audit_records(tmp_path: Path) -> None:
    """Verify stream_audit_records counts."""
    from devops_cli.core.audit import stream_audit_records

    # Missing file returns 0
    assert stream_audit_records("http://example.com/siem", tmp_path / "nonexistent.jsonl") == 0

    log_file = tmp_path / "audit.jsonl"
    record_audit_event("devops repos list", log_file=log_file)
    record_audit_event("devops repos sync", log_file=log_file)

    count = stream_audit_records("http://example.com/siem", log_file)
    assert count == 2
