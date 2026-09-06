"""Declarative base class for security and static analysis scanners."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS
from devops_cli.core.binaries import check_binary
from devops_cli.core.process import run_json_subprocess
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


class BaseSecurityScanner(ABC):
    """Abstract base class for declarative security and static analysis tools."""

    name: str = "base_scanner"
    binary_name: str = "scanner"

    @abstractmethod
    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        """Build argument command list for invoking the scanner binary."""

    @abstractmethod
    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Parse structured JSON output into normalized Finding objects."""

    def fallback_scan(self, target_path: Path) -> list[Finding]:
        """Execute heuristic fallback inspection when the external binary is unavailable."""
        return []

    def scan(
        self,
        target_path: Path,
        timeout: float = DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
        **kwargs: Any,
    ) -> list[Finding]:
        """Execute scanner with binary pre-flight checking, timeouts, and fallback recovery."""
        if not check_binary(self.binary_name):
            logger.debug(
                "Scanner binary '%s' not found; executing fallback scan.", self.binary_name
            )
            return self.fallback_scan(target_path)

        cmd = self.build_command(target_path, **kwargs)
        cwd_dir = target_path if target_path.is_dir() else target_path.parent

        @trace_span(f"security.{self.name}")
        def _run() -> list[Finding]:
            try:
                data = run_json_subprocess(
                    cmd, cwd=cwd_dir, timeout=timeout, default={}, check=False
                )
                return self.parse_output(data, target_path)
            except Exception as exc:
                logger.debug("Scanner '%s' failed: %s; running fallback.", self.name, exc)
                return self.fallback_scan(target_path)

        return _run()
