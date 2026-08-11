"""Structured SIEM Audit Trail Logging for devops-cli executions."""

from __future__ import annotations

import getpass
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import CONST_DATA_DIR


class AuditRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: str
    command: str
    user: str
    status: str
    duration_ms: float
    details: dict[str, Any]


def record_audit_event(
    command: str,
    status: str = "SUCCESS",
    duration_ms: float = 0.0,
    details: dict[str, Any] | None = None,
    log_file: Path | None = None,
) -> AuditRecord:
    """Record a structured audit log entry to JSONL audit log file."""
    dest = log_file or (
        Path(os.environ["DEVOPS_CLI_AUDIT_LOG_DEST"])
        if "DEVOPS_CLI_AUDIT_LOG_DEST" in os.environ
        else CONST_DATA_DIR / "logs" / "audit.jsonl"
    )

    dest.parent.mkdir(parents=True, exist_ok=True)

    user = getpass.getuser()
    now_str = datetime.now(UTC).isoformat()

    record = AuditRecord(
        timestamp=now_str,
        command=command,
        user=user,
        status=status,
        duration_ms=duration_ms,
        details=details or {},
    )

    with dest.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")

    return record
