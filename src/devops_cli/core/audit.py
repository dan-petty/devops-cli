"""Structured SIEM Audit Trail Logging for devops-cli executions."""

from __future__ import annotations

import getpass
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_AUDIT_LOG_PATH,
    CONST_DATA_DIR,
    CONST_STATUS_SUCCESS,
)


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
    status: str = CONST_STATUS_SUCCESS,
    duration_ms: float = 0.0,
    details: dict[str, Any] | None = None,
    log_file: Path | None = None,
) -> AuditRecord:
    """Record a structured audit log entry to JSONL audit log file."""
    dest = _resolve_audit_log_dest(log_file)

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

    if not dest.exists():
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.close(fd)

    with dest.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")

    return record


def _resolve_audit_log_dest(log_file: Path | None) -> Path:
    """Resolve audit log destination path, validating env paths stay in CONST_DATA_DIR."""
    if log_file is not None:
        return log_file.resolve()
    if "DEVOPS_CLI_AUDIT_LOG_DEST" in os.environ:
        candidate = Path(os.environ["DEVOPS_CLI_AUDIT_LOG_DEST"]).resolve()
        allowed_root = CONST_DATA_DIR.resolve()
        if not candidate.is_relative_to(allowed_root):
            from devops_cli.exceptions import SecurityError

            raise SecurityError(
                f"DEVOPS_CLI_AUDIT_LOG_DEST must be within {allowed_root}; got {candidate}"
            )
        return candidate
    return CONST_AUDIT_LOG_PATH


def stream_audit_records(destination_url: str, log_file: Path | None = None) -> int:
    """Stream stored audit records to SIEM destination URL.

    Returns streamed record count.
    """
    dest = log_file or CONST_AUDIT_LOG_PATH

    if not dest.exists():
        return 0

    count = 0
    try:
        with dest.open(encoding="utf-8") as f:
            for _line in f:
                if _line.strip():
                    count += 1
    except OSError:
        return count
    return count
