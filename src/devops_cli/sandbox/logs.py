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
from devops_cli.core.paths import safe_resolve_subpath, validate_no_path_traversal
from devops_cli.core.repo import main_worktree_root, resolve_data_path
from devops_cli.exceptions.sandbox import SandboxError
from devops_cli.exceptions.security import SecurityError
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
    r"^(?:stack backtrace:|\s*\d+:\s+.*|\s*at\s+.*)"
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
    """Determine incident directory respecting DEVOPS_CLI_DATA_DIR and path traversal safety; a
    relative data directory is under the main worktree, shared by every worktree."""
    from devops_cli.core.paths import is_forbidden_system_path

    if base_dir is not None:
        target = validate_no_path_traversal(base_dir, label="Incident base dir")
        resolved = Path(target).resolve()
        if is_forbidden_system_path(resolved):
            raise SecurityError(f"Incident base dir {resolved} resolves to a forbidden system path")
        if Path(base_dir).is_symlink():
            raise SecurityError(f"Incident base dir must not be a symlink: {base_dir}")
        return resolved
    env_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    if env_dir:
        validated_env = Path(validate_no_path_traversal(env_dir, label="DEVOPS_CLI_DATA_DIR"))
        anchored_env = (
            validated_env if validated_env.is_absolute() else main_worktree_root() / validated_env
        )
        resolved_env = anchored_env.resolve()
        if is_forbidden_system_path(resolved_env):
            raise SecurityError(
                f"DEVOPS_CLI_DATA_DIR {resolved_env} resolves to a forbidden system path"
            )
        if anchored_env.is_symlink():
            raise SecurityError(f"DEVOPS_CLI_DATA_DIR must not be a symlink: {env_dir}")
        return resolved_env / "sandbox" / "incidents"
    return resolve_data_path(DEFAULT_SANDBOX_INCIDENTS_DIR)


def archive_incident(incident: PanicIncident, base_dir: Path | None = None) -> Path:
    """Atomically archive structured panic incident record in JSON format."""
    clean_id = incident.incident_id.strip()
    if not clean_id or "/" in clean_id or "\\" in clean_id:
        raise SecurityError(
            f"Invalid incident ID: must be a plain basename, got {incident.incident_id!r}"
        )
    validate_no_path_traversal(clean_id, label="Incident ID")
    target_dir = resolve_incident_dir(base_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(target_dir, 0o700)
    except OSError:
        pass

    incident_filename = f"{clean_id}.json"
    incident_path = safe_resolve_subpath(target_dir, incident_filename, allow_symlinks=False)

    payload = incident.model_dump()
    payload["archived_path"] = str(incident_path)
    incident.archived_path = str(incident_path)

    tmp_path = target_dir / f".tmp.{clean_id}.{uuid.uuid4().hex[:6]}"
    try:
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass
        os.replace(tmp_path, incident_path)
        try:
            os.chmod(incident_path, 0o600)
        except OSError as exc:
            if incident_path.exists():
                incident_path.unlink(missing_ok=True)
            raise SandboxError(
                f"Failed to apply secure permissions to incident archive '{incident_path.name}': {exc}",
                instance_id=incident.instance_id,
                container_id=incident.container_id,
            ) from exc
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
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
            incident.archive_error = str(exc)[:256]
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

    def _check_panic_start(self, line: SandboxLogLine) -> tuple[PanicType, str] | None:
        """Identify if a line initiates a multi-line panic or stacktrace without mutating state."""
        c = line.content
        if _RE_PY_START.search(c):
            return PanicType.PYTHON_TRACEBACK, ""
        if match := _RE_GO_START.search(c):
            return PanicType.GO_PANIC, _extract_go_panic_message(match, c)
        if match := _RE_JAVA_START.search(c):
            return PanicType.JAVA_STACKTRACE, _extract_java_panic_message(match)
        if match := _RE_RUST_START.search(c):
            return PanicType.RUST_PANIC, _extract_rust_panic_message(match, c)
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

    def _handle_single_crash(
        self, line: SandboxLogLine, single_crash: PanicIncident
    ) -> list[PanicIncident]:
        res: list[PanicIncident] = []
        if flushed := self._flush_current():
            res.append(flushed)
        res.append(single_crash)
        line.is_panic = True
        line.panic_type = PanicType.SEGFAULT
        return res

    def _start_new_panic(
        self, line: SandboxLogLine, new_panic: tuple[PanicType, str]
    ) -> list[PanicIncident]:
        new_type, new_message = new_panic
        res = [flushed] if (flushed := self._flush_current()) else []
        self.current_type = new_type
        self.current_message = new_message
        self.current_stacktrace = [line.content]
        self.current_stream = line.stream
        self.current_timestamp = line.timestamp
        line.is_panic = True
        line.panic_type = new_type
        return res

    def _continue_panic(self, line: SandboxLogLine) -> list[PanicIncident]:
        self.current_stacktrace.append(line.content)
        line.is_panic = True
        line.panic_type = self.current_type
        if self.current_type == PanicType.PYTHON_TRACEBACK and _RE_PY_ERR.match(line.content):
            self.current_message = line.content
            return [flushed] if (flushed := self._flush_current()) else []
        return []

    def feed_line(self, line: SandboxLogLine) -> list[PanicIncident]:
        """Process a log line through the detector, yielding any finalized incidents."""
        if single_crash := self._check_single_line_crash(line):
            return self._handle_single_crash(line, single_crash)

        if new_panic := self._check_panic_start(line):
            return self._start_new_panic(line, new_panic)

        if self.current_type and self._is_frame_continuation(line.content):
            return self._continue_panic(line)

        return [flushed] if self.current_type and (flushed := self._flush_current()) else []

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
        incidents.extend(detector.feed_line(parsed))
    incidents.extend(detector.flush())
    return incidents


__all__ = [
    "PanicDetector",
    "archive_incident",
    "detect_panics",
    "parse_docker_log_line",
    "resolve_incident_dir",
]
