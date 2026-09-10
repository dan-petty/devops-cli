"""Declarative base class for security and static analysis scanners."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS
from devops_cli.core.binaries import check_binary
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import state as dry_run_state
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


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


class BaseSecurityScanner(ABC):
    """Abstract base class for declarative security and static analysis tools."""

    name: str = "base_scanner"
    binary_name: str = "scanner"

    @abstractmethod
    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        """Build argument command list for invoking the scanner binary."""

    @abstractmethod
    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Parse raw scanner JSON/structure payload into Finding models."""

    def fallback_scan(self, target_path: Path) -> list[Finding]:
        """Execute fallback scan logic when primary binary is unavailable."""
        return []

    def dry_run_scan(self, target_path: Path, **kwargs: Any) -> list[Finding]:
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

    def _resolve_cwd(self, target_path: Path) -> Path:
        """Safely resolve working directory for subprocess execution."""
        try:
            if isinstance(target_path, Path) and target_path.exists():
                return target_path if target_path.is_dir() else target_path.parent
        except Exception:
            pass
        return Path.cwd()

    def scan(
        self,
        target_path: Path,
        timeout: float = DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
        **kwargs: Any,
    ) -> list[Finding]:
        """Execute scanner with binary pre-flight checking, timeouts, and fallback recovery."""
        if dry_run_state.is_dry_run():
            return self.dry_run_scan(target_path, **kwargs)

        if not check_binary(self.binary_name):
            logger.debug(
                "Scanner binary '%s' not found; executing fallback scan.", self.binary_name
            )
            return self.fallback_scan(target_path)

        cmd = self.build_command(target_path, **kwargs)
        if not cmd:
            return []

        cwd_dir = self._resolve_cwd(target_path)

        @trace_span(f"security.{self.name}")
        def _run() -> list[Finding]:
            try:
                proc = run_subprocess(cmd, cwd=cwd_dir, timeout=timeout, check=False)
                is_valid_json, data = _parse_json_or_ndjson(proc.stdout)
                if not is_valid_json:
                    if proc.returncode != 0:
                        logger.debug(
                            "Scanner '%s' returned code %d with non-JSON output; invoking fallback.",
                            self.name,
                            proc.returncode,
                        )
                        return self.fallback_scan(target_path)
                    raw_findings = self.parse_output(proc.stdout, target_path)
                    return raw_findings if raw_findings else self.fallback_scan(target_path)

                findings = self.parse_output(data, target_path)
                if not findings and proc.returncode != 0:
                    logger.debug(
                        "Scanner '%s' exited %d with zero findings; checking fallback.",
                        self.name,
                        proc.returncode,
                    )
                    fallback_findings = self.fallback_scan(target_path)
                    if fallback_findings:
                        return fallback_findings
                return findings
            except Exception as exc:
                logger.debug("Scanner '%s' failed: %s; running fallback.", self.name, exc)
                return self.fallback_scan(target_path)

        return _run()
