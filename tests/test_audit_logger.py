"""Tests for SIEM audit trail logger and log destination resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.core.audit import _resolve_audit_log_dest, record_audit_event


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
    monkeypatch.setenv("DEVOPS_CLI_AUDIT_LOG_DEST", str(tmp_path / ".data" / "custom.jsonl"))
    monkeypatch.setattr("devops_cli.core.audit.CONST_DATA_DIR", tmp_path / ".data")
    dest = _resolve_audit_log_dest(None)
    assert dest == tmp_path / ".data" / "custom.jsonl"

    monkeypatch.setenv("DEVOPS_CLI_AUDIT_LOG_DEST", "/etc/passwd")
    with pytest.raises(ValueError, match="must be within"):
        _resolve_audit_log_dest(None)
