"""Declarative base class for security and static analysis scanners."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, NamedTuple
from unittest.mock import NonCallableMock

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_SCANNER_STDOUT_EXCERPT_CHARS,
)
from devops_cli.config.defaults import DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS
from devops_cli.core.binaries import check_binary
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import state as dry_run_state
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def _has_builtin_patterns(scanner: Any) -> bool:
    """Check if scanner defines or enables built-in fallback patterns."""
    if getattr(scanner, "has_builtin_patterns", False):
        return True
    fb = getattr(scanner.__class__, "fallback_scan", None)
    return fb is not None and getattr(fb, "__qualname__", "") != "BaseSecurityScanner.fallback_scan"


def _parse_json_or_ndjson(raw_stdout: str) -> tuple[bool, Any]:
    """Parse stdout as standard single JSON document or multi-line NDJSON records."""
    text = raw_stdout.strip()
    if not text:
        return False, None
    try:
        return True, json.loads(text)
    except Exception:
        pass

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False, None

    records: list[Any] = []
    for ln in lines:
        try:
            records.append(json.loads(ln))
        except Exception:
            return False, None
    return True, records


def _cut(text: str, limit: int) -> str:
    """Return text cut to limit characters, ending in … when it was cut."""
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def masked_reason(reason: str) -> str:
    """Return a failure reason masked, then cut to `CONST_MAX_ERROR_DETAIL_LENGTH`.

    Masking comes first: cutting first can leave part of a secret the masking patterns no longer
    match.
    """
    return _cut(mask_secrets(reason), CONST_MAX_ERROR_DETAIL_LENGTH)


class ScanOutcome(list[Finding]):
    """The outcome of executing a security scanner.

    The reason reaches SARIF notifications, the CLI and review.md, and often quotes a scanner's
    output or an exception, so `masked_reason` masks and bounds it here, for every producer.
    """

    def __init__(
        self,
        status: str,
        findings: list[Finding] | None = None,
        reason: str = "",
    ) -> None:
        items = list(findings) if findings is not None else []
        super().__init__(items)
        self.status: str = status
        self.findings: list[Finding] = items
        self.reason: str = masked_reason(reason)
        # When the scanner started and finished, in UTC; set by `BaseSecurityScanner.scan`.
        self.started_utc: str | None = None
        self.ended_utc: str | None = None

    def __repr__(self) -> str:
        return f"ScanOutcome(status={self.status!r}, findings={self.findings!r}, reason={self.reason!r})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ScanOutcome):
            return (self.status, self.findings, self.reason) == (
                other.status,
                other.findings,
                other.reason,
            )
        return super().__eq__(other)


def _evaluate_preflight(
    scanner: BaseSecurityScanner, target_path: Any, **kwargs: Any
) -> ScanOutcome | None:
    """Evaluate dry-run, applicability, and binary presence prior to command execution."""
    if scanner._is_dry_run():
        applicable, reason = scanner.is_applicable(target_path, **kwargs)
        if not applicable:
            return ScanOutcome("not_applicable", [], reason)
        return ScanOutcome(
            "dry-run",
            scanner.dry_run_scan(target_path, **kwargs),
            "Dry-run simulation mode active",
        )

    applicable, reason = scanner.is_applicable(target_path, **kwargs)
    if not applicable:
        logger.debug(
            "Scanner '%s' not applicable to target %s: %s",
            scanner.name,
            target_path,
            reason,
        )
        return ScanOutcome(
            "not_applicable",
            [],
            reason or f"Scanner {scanner.name} is not applicable to target",
        )

    if not scanner._check_binary():
        if _has_builtin_patterns(scanner):
            logger.debug(
                "Scanner binary '%s' not found; executing built-in fallback patterns.",
                scanner.binary_name,
            )
            return ScanOutcome(
                "built-in patterns",
                scanner.fallback_scan(target_path),
                f"Binary '{scanner.binary_name}' not found; used built-in patterns",
            )
        logger.debug("Scanner binary '%s' not found on PATH.", scanner.binary_name)
        return ScanOutcome(
            "unavailable",
            [],
            f"Binary '{scanner.binary_name}' not found on PATH",
        )

    return None


def _one_line(text: str, limit: int) -> str:
    """Return text on one line, each run of whitespace a single space, cut to limit characters."""
    return _cut(" ".join(text.split()), limit)


def _non_json_failure_reason(proc: Any) -> str:
    """Say how the scanner exited, and when it printed something other than JSON, quote its start.

    The output is masked before the quote is cut from it, so the cut cannot split a secret;
    `ScanOutcome` masks and bounds the whole reason.
    """
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if not stdout:
        return f"Scanner exited with code {proc.returncode}: {stderr}"
    reason = (
        f"Scanner exited with code {proc.returncode}; output was not JSON, starting "
        f'"{_one_line(mask_secrets(stdout), CONST_SCANNER_STDOUT_EXCERPT_CHARS)}"'
    )
    if stderr:
        reason = f"{reason}; stderr: {stderr}"
    return " ".join(reason.split())


def _handle_non_json_output(
    scanner: BaseSecurityScanner, proc: Any, target_path: Any
) -> ScanOutcome:
    """Handle scanner execution result when stdout does not contain valid JSON."""
    if proc.returncode != 0:
        if _has_builtin_patterns(scanner):
            return ScanOutcome(
                "built-in patterns",
                scanner.fallback_scan(target_path),
                f"Scanner exited with code {proc.returncode}; used built-in patterns",
            )
        return ScanOutcome("failed", [], _non_json_failure_reason(proc))
    raw_findings = scanner.parse_output(proc.stdout, target_path)
    if raw_findings:
        return ScanOutcome("ran", raw_findings)
    if _has_builtin_patterns(scanner):
        return ScanOutcome(
            "built-in patterns",
            scanner.fallback_scan(target_path),
            "Non-JSON output; used built-in patterns",
        )
    return ScanOutcome("ran", [])


def _handle_json_output(
    scanner: BaseSecurityScanner,
    data: Any,
    returncode: int,
    stderr: str,
    target_path: Any,
) -> ScanOutcome:
    """Handle scanner execution result with parsed JSON payload."""
    findings = scanner.parse_output(data, target_path)
    if not findings and returncode != 0:
        if _has_builtin_patterns(scanner):
            fb = scanner.fallback_scan(target_path)
            if fb:
                return ScanOutcome(
                    "built-in patterns",
                    fb,
                    f"Scanner exited with code {returncode}; used built-in patterns",
                )
        return ScanOutcome("failed", [], f"Scanner exited with code {returncode}: {stderr.strip()}")
    return ScanOutcome("ran", findings)


def _utc_now() -> str:
    """Return the current UTC time in SARIF's millisecond date-time form."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _is_mocked(module_name: str | None, attr_name: str) -> Any:
    """Return mock object if attribute on module is a NonCallableMock, else None."""
    if not module_name:
        return None
    mod = sys.modules.get(module_name)
    if mod is None:
        return None
    target = getattr(mod, attr_name, None)
    return target if isinstance(target, NonCallableMock) else None


class ScannerConfigFile(NamedTuple):
    """A config or ignore file devops-cli hands a scanner, and the flag that names it."""

    flag: str
    name: str
    text: str


class BaseSecurityScanner(ABC):
    """Abstract base class for declarative security and static analysis tools."""

    name: str = "base_scanner"
    binary_name: str = "scanner"
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False
    # The files an isolated scan hands the scanner in place of the config and ignore files it
    # would read from its working directory or the scanned tree (#972).
    isolation_files: ClassVar[tuple[ScannerConfigFile, ...]] = ()

    @abstractmethod
    def build_command(self, target_path: Any, **kwargs: Any) -> list[str]:
        """Build argument command list for invoking the scanner binary."""

    @abstractmethod
    def parse_output(self, data: Any, target_path: Any) -> list[Finding]:
        """Parse raw scanner JSON/structure payload into Finding models."""

    def is_applicable(self, target_path: Any, **kwargs: Any) -> tuple[bool, str]:
        """Determine if scanner applies to the given target and kwargs.

        Returns (True, "") if applicable, or (False, reason) if not applicable.
        """
        return True, ""

    def fallback_scan(self, target_path: Any) -> list[Finding]:
        """Execute fallback scan logic when primary binary is unavailable."""
        return []

    def dry_run_scan(self, target_path: Any, **kwargs: Any) -> list[Finding]:
        """Return simulated findings for dry-run simulation mode."""
        return [
            Finding(
                severity="LOW",
                location=f"{target_path}:simulation",
                title=f"[{self.name.upper()}] [DRY-RUN] Simulated Security Scan",
                description=f"Simulation mode active for {self.name} scanner.",
                fix="No action required (simulation mode)",
            )
        ]

    def _is_dry_run(self) -> bool:
        """Determine whether dry-run mode is active, honoring module-level test mocks."""
        for mod_name in (
            "devops_cli.dry_run.state",
            "devops_cli.security.base",
            self.__class__.__module__,
        ):
            mock_dr = _is_mocked(mod_name, "is_dry_run")
            if mock_dr is not None:
                return bool(mock_dr())
        return dry_run_state.is_dry_run()

    def _check_binary(self) -> bool:
        """Verify binary presence on PATH, honoring module-level test mocks."""
        for mod_name in ("devops_cli.security.base", self.__class__.__module__):
            mock_cb = _is_mocked(mod_name, "check_binary")
            if mock_cb is not None:
                return bool(mock_cb(self.binary_name))
        for mod_name in ("devops_cli.security.base", self.__class__.__module__):
            if _is_mocked(mod_name, "run_subprocess") is not None:
                return True
        return check_binary(self.binary_name)

    def _run_subprocess(self, cmd: list[str], **kwargs: Any) -> Any:
        """Execute subprocess command, honoring module-level test mocks."""
        for mod_name in ("devops_cli.security.base", self.__class__.__module__):
            mock_proc = _is_mocked(mod_name, "run_subprocess")
            if mock_proc is not None:
                return mock_proc(cmd, **kwargs)
        return run_subprocess(cmd, **kwargs)

    def _resolve_cwd(self, target_path: Any) -> Path:
        """Safely resolve working directory for subprocess execution."""
        try:
            if isinstance(target_path, Path) and target_path.exists():
                return target_path if target_path.is_dir() else target_path.parent
            if isinstance(target_path, list) and target_path:
                file_strs = [
                    str(Path(p).resolve())
                    for p in target_path
                    if isinstance(p, (str, Path)) and Path(p).exists()
                ]
                if file_strs:
                    common = Path(os.path.commonpath(file_strs))
                    return common if common.is_dir() else common.parent
        except Exception:
            pass
        return Path.cwd()

    def _run_scanner_command(
        self,
        cmd: list[str],
        cwd_dir: Path,
        target_path: Any,
        timeout: float,
    ) -> ScanOutcome:
        """Execute scanner command subprocess with output parsing and fallback handling."""

        @trace_span(f"security.{self.name}")
        def _run() -> ScanOutcome:
            try:
                proc = self._run_subprocess(cmd, cwd=cwd_dir, timeout=timeout, check=False)
                is_valid_json, data = _parse_json_or_ndjson(proc.stdout)
                if not is_valid_json:
                    return _handle_non_json_output(self, proc, target_path)
                return _handle_json_output(
                    self, data, proc.returncode, proc.stderr or "", target_path
                )
            except Exception as exc:
                logger.debug("Scanner '%s' failed: %s; running fallback.", self.name, exc)
                if _has_builtin_patterns(self):
                    return ScanOutcome(
                        "built-in patterns",
                        self.fallback_scan(target_path),
                        f"Scanner error: {exc}; used built-in patterns",
                    )
                return ScanOutcome("failed", [], f"Scanner execution failed: {exc}")

        return _run()

    def scan(
        self,
        target_path: Any,
        timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
        *,
        isolated: bool = False,
        **kwargs: Any,
    ) -> ScanOutcome:
        """Execute scanner with applicability pre-flight checking, timeouts, and fallback recovery.

        An `isolated` scan takes nothing from the scanned tree: a review's (#972).
        """
        started = _utc_now()
        outcome = self._execute(target_path, timeout, isolated, **kwargs)
        outcome.started_utc, outcome.ended_utc = started, _utc_now()
        return outcome

    def _execute(
        self, target_path: Any, timeout: float, isolated: bool, **kwargs: Any
    ) -> ScanOutcome:
        """Run the pre-flight checks, then the scanner command."""
        preflight = _evaluate_preflight(self, target_path, **kwargs)
        if preflight is not None:
            return preflight

        cmd = self.build_command(target_path, **kwargs)
        if not cmd:
            return ScanOutcome("not_applicable", [], f"Empty command generated for {self.name}")

        if not isolated:
            return self._run_scanner_command(
                cmd, self._resolve_cwd(target_path), target_path, timeout
            )
        with tempfile.TemporaryDirectory(prefix=f"devops-scan-{self.name}-") as scan_dir:
            workdir = Path(scan_dir)
            isolated_cmd = [*cmd, *self._hand_isolation_files(workdir)]
            return self._run_scanner_command(isolated_cmd, workdir, target_path, timeout)

    def _hand_isolation_files(self, workdir: Path) -> list[str]:
        """Write the scanner's isolation files into `workdir`, returning the flags that name them.

        An isolated scan runs in `workdir`, a temporary directory outside the scanned tree, so
        the scanner finds no config or ignore file of the tree's in its working directory, and
        each it would look for in the tree is named explicitly: devops-cli's own (#972).
        """
        flags: list[str] = []
        for config_file in self.isolation_files:
            path = workdir / config_file.name
            path.write_text(config_file.text, encoding="utf-8")
            flags.extend((config_file.flag, str(path)))
        return flags


__all__ = ["BaseSecurityScanner", "ScanOutcome", "ScannerConfigFile"]
