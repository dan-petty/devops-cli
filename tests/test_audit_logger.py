"""Tests for SIEM audit trail logger."""

from __future__ import annotations

import json
from pathlib import Path

from devops_cli.core.audit import record_audit_event


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
