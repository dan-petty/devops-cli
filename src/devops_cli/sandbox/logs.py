"""Streaming diagnostic log aggregator and multi-language panic detector."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from devops_cli.config.defaults import DEFAULT_SANDBOX_INCIDENTS_DIR
from devops_cli.core.paths import validate_no_path_traversal
from devops_cli.sandbox.models import (
    PanicIncident,
    PanicType,
    SandboxLogLine,
)

logger = logging.getLogger(__name__)

# RFC3339 / ISO8601 Docker log timestamp pattern
_DOCKER_TS_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s+(.*)$"
)

# Multi-language panic and crash detection patterns
_RE_PY_START: Final[re.Pattern[str]] = re.compile(r"^Traceback \(most recent call last\):")
_RE_PY_FRAME: Final[re.Pattern[str]] = re.compile(
    r"^\s+(?:File \".*\", line \d+|[A-Za-z0-9_.]+\(.*\)|<.*>|\^|\.\.\.)"
)
_RE_PY_ERR: Final[re.Pattern[str]] = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Interrupt|Exit|AssertionError)):(?:\s*(.*))?$"
)

_RE_GO_START: Final[re.Pattern[str]] = re.compile(r"^(?:panic:\s*(.*)|fatal error:\s*(.*))")
_RE_GO_FRAME: Final[re.Pattern[str]] = re.compile(
    r"^(?:goroutine \d+|[a-zA-Z0-9_./\-]+(?:\.[a-zA-Z0-9_]+)+\(.*\)|(?:\t|\s+)/.*:\d+)"
)

_RE_JAVA_START: Final[re.Pattern[str]] = re.compile(
    r"^(?:(?:Exception in thread \"[^\"]*\"|Caused by:)\s*([a-zA-Z0-9_.]+(?:Exception|Error))|([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+(?:Exception|Error)))(?::\s*(.*))?$"
)
_RE_JAVA_FRAME: Final[re.Pattern[str]] = re.compile(
    r"^\s+at\s+[a-zA-Z0-9_.$]+\(.*\)|^\s+\.\.\.\s+\d+\s+more"
)

_RE_RUST_START: Final[re.Pattern[str]] = re.compile(
    r"^thread '.*' panicked at (?:'(.*)'|([^,]+)), (.*)"
)
_RE_RUST_FRAME: Final[re.Pattern[str]] = re.compile(
    r"^(?:stack backtrace:|\s*\d+:\s+0x[0-9a-fA-F]+|\s*at\s+.*)"
)

_RE_SEGFAULT: Final[re.Pattern[str]] = re.compile(
    r"^(?:Segmentation fault(?:\s*\(core dumped\))?|SIGSEGV|SIGABRT|SIGBUS|SIGILL|Aborted(?:\s*\(core dumped\))?|Bus error|Illegal instruction)"
)


def parse_docker_log_line(raw: str | bytes, default_stream: str = "stdout") -> SandboxLogLine:
    """Parse raw log line, extracting optional RFC3339 timestamp prefix."""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else raw
    line_clean = text.rstrip("\r\n")
    match = _DOCKER_TS_REGEX.match(line_clean)
    if match:
        return SandboxLogLine(
            timestamp=match.group(1),
            content=match.group(2),
            stream=default_stream,
        )
    return SandboxLogLine(
        timestamp=None,
        content=line_clean,
        stream=default_stream,
    )


def resolve_incident_dir(base_dir: Path | None = None) -> Path:
    """Determine incident directory respecting DEVOPS_CLI_DATA_DIR and path traversal safety."""
    if base_dir is not None:
        target = validate_no_path_traversal(base_dir, label="Incident base dir")
        return Path(target)
    env_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    if env_dir:
        validated_env = validate_no_path_traversal(env_dir, label="DEVOPS_CLI_DATA_DIR")
        return Path(validated_env) / "sandbox" / "incidents"
    return DEFAULT_SANDBOX_INCIDENTS_DIR


def archive_incident(incident: PanicIncident, base_dir: Path | None = None) -> Path:
    """Atomically archive structured panic incident record in JSON format."""
    validate_no_path_traversal(incident.incident_id, label="Incident ID")
    target_dir = resolve_incident_dir(base_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    incident_path = target_dir / f"{incident.incident_id}.json"
    validate_no_path_traversal(incident_path.name, label="Incident filename")

    payload = incident.model_dump()
    payload["archived_path"] = str(incident_path)
    incident.archived_path = str(incident_path)

    incident_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return incident_path


def _create_incident_record(
    instance_id: str,
    container_id: str,
    panic_type: PanicType,
    message: str,
    stacktrace: list[str],
    stream: str,
    timestamp: str | None,
    archive: bool,
    base_dir: Path | None,
) -> PanicIncident:
    """Helper to instantiate and optionally archive a PanicIncident."""
    inc_id = f"incident-{uuid.uuid4().hex[:8]}"
    ts = timestamp or datetime.now(UTC).isoformat()
    incident = PanicIncident(
        incident_id=inc_id,
        instance_id=instance_id,
        container_id=container_id,
        panic_type=panic_type,
        message=message[:256],
        stacktrace=stacktrace,
        timestamp=ts,
        log_stream=stream,
    )
    if archive:
        try:
            archive_incident(incident, base_dir=base_dir)
        except Exception as exc:
            logger.warning("Failed to archive incident %s: %s", inc_id, exc)
    return incident


def _extract_go_panic_message(match: re.Match[str], raw: str) -> str:
    """Extract message from Go panic header."""
    return (match.group(1) or match.group(2) or raw).strip()


def _extract_java_panic_message(match: re.Match[str]) -> str:
    """Extract message from Java exception header."""
    err_name = match.group(1) or match.group(2)
    err_msg = match.group(3)
    return f"{err_name}: {err_msg}" if err_msg else err_name


def _extract_rust_panic_message(match: re.Match[str], raw: str) -> str:
    """Extract message from Rust panic header."""
    return (match.group(1) or match.group(2) or raw).strip()


class PanicDetector:
    """Streaming multi-language panic detector state machine."""

    def __init__(
        self,
        instance_id: str,
        container_id: str,
        archive: bool = True,
        base_dir: Path | None = None,
    ) -> None:
        self.instance_id = instance_id
        self.container_id = container_id
        self.archive = archive
        self.base_dir = base_dir

        self.current_type: PanicType | None = None
        self.current_message: str = ""
        self.current_stacktrace: list[str] = []
        self.current_stream: str = "stderr"
        self.current_timestamp: str | None = None

    def _flush_current(self) -> PanicIncident | None:
        """Complete and return current in-progress panic incident if active."""
        if not self.current_type or not self.current_stacktrace:
            self._reset_state()
            return None

        incident = _create_incident_record(
            instance_id=self.instance_id,
            container_id=self.container_id,
            panic_type=self.current_type,
            message=self.current_message or self.current_stacktrace[0],
            stacktrace=list(self.current_stacktrace),
            stream=self.current_stream,
            timestamp=self.current_timestamp,
            archive=self.archive,
            base_dir=self.base_dir,
        )
        self._reset_state()
        return incident

    def _reset_state(self) -> None:
        """Reset state machine buffers."""
        self.current_type = None
        self.current_message = ""
        self.current_stacktrace = []
        self.current_stream = "stderr"
        self.current_timestamp = None

    def _check_single_line_crash(self, line: SandboxLogLine) -> PanicIncident | None:
        """Check if line matches standalone segfault or fatal abort."""
        if _RE_SEGFAULT.search(line.content):
            return _create_incident_record(
                instance_id=self.instance_id,
                container_id=self.container_id,
                panic_type=PanicType.SEGFAULT,
                message=line.content,
                stacktrace=[line.content],
                stream=line.stream,
                timestamp=line.timestamp,
                archive=self.archive,
                base_dir=self.base_dir,
            )
        return None

    def _check_panic_start(self, line: SandboxLogLine) -> PanicType | None:
        """Identify if a line initiates a multi-line panic or stacktrace."""
        c = line.content
        if _RE_PY_START.search(c):
            return PanicType.PYTHON_TRACEBACK
        if match := _RE_GO_START.search(c):
            self.current_message = _extract_go_panic_message(match, c)
            return PanicType.GO_PANIC
        if match := _RE_JAVA_START.search(c):
            self.current_message = _extract_java_panic_message(match)
            return PanicType.JAVA_STACKTRACE
        if match := _RE_RUST_START.search(c):
            self.current_message = _extract_rust_panic_message(match, c)
            return PanicType.RUST_PANIC
        return None

    def _is_frame_continuation(self, content: str) -> bool:
        """Determine if line belongs to the active panic's stacktrace."""
        if not self.current_type:
            return False
        if not content.strip():
            return True
        if self.current_type == PanicType.PYTHON_TRACEBACK:
            return content.startswith((" ", "\t")) or bool(_RE_PY_ERR.match(content))
        if self.current_type == PanicType.GO_PANIC:
            return bool(_RE_GO_FRAME.match(content))
        if self.current_type == PanicType.JAVA_STACKTRACE:
            return bool(_RE_JAVA_FRAME.match(content))
        if self.current_type == PanicType.RUST_PANIC:
            return bool(_RE_RUST_FRAME.match(content))
        return False

    def feed_line(self, line: SandboxLogLine) -> PanicIncident | None:
        """Process a log line through the detector, yielding an incident if finalized."""
        # 1. Standalone single-line crash check
        single_crash = self._check_single_line_crash(line)
        if single_crash:
            flushed = self._flush_current()
            line.is_panic = True
            line.panic_type = PanicType.SEGFAULT
            return flushed or single_crash

        # 2. Check if this initiates a new multi-line panic
        new_panic_type = self._check_panic_start(line)
        if new_panic_type is not None:
            flushed = self._flush_current()
            self.current_type = new_panic_type
            self.current_stacktrace = [line.content]
            self.current_stream = line.stream
            self.current_timestamp = line.timestamp
            line.is_panic = True
            line.panic_type = new_panic_type
            return flushed

        # 3. Check continuation of current panic
        if self.current_type and self._is_frame_continuation(line.content):
            self.current_stacktrace.append(line.content)
            line.is_panic = True
            line.panic_type = self.current_type
            if self.current_type == PanicType.PYTHON_TRACEBACK and _RE_PY_ERR.match(line.content):
                self.current_message = line.content
                return self._flush_current()
            return None

        # 4. Non-matching line while panic was in progress -> flush
        if self.current_type:
            return self._flush_current()

        return None

    def flush(self) -> list[PanicIncident]:
        """Flush and return any remaining unfinalized incident."""
        incident = self._flush_current()
        return [incident] if incident else []


def detect_panics(
    lines: list[str],
    instance_id: str = "sandbox",
    container_id: str = "docker",
    archive: bool = False,
    base_dir: Path | None = None,
) -> list[PanicIncident]:
    """Batch convenience function to extract all panic incidents from log strings."""
    detector = PanicDetector(
        instance_id=instance_id,
        container_id=container_id,
        archive=archive,
        base_dir=base_dir,
    )
    incidents: list[PanicIncident] = []
    for raw in lines:
        parsed = parse_docker_log_line(raw)
        if inc := detector.feed_line(parsed):
            incidents.append(inc)
    incidents.extend(detector.flush())
    return incidents


__all__ = [
    "PanicDetector",
    "archive_incident",
    "detect_panics",
    "parse_docker_log_line",
    "resolve_incident_dir",
]
