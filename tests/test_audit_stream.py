"""Tests for SIEM audit streaming."""

from __future__ import annotations

from pathlib import Path

from devops_cli.core.audit import record_audit_event, stream_audit_records


def test_stream_audit_records(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "audit.jsonl"
    record_audit_event(
        command="devops k8s contexts",
        status="SUCCESS",
        log_file=log_file,
    )

    count = stream_audit_records("http://siem.lan:8080", log_file=log_file)
    assert count == 1
