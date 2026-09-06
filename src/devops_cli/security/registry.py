"""Centralized registry for security scanners and static linters."""

from __future__ import annotations

import logging
from pathlib import Path

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS
from devops_cli.security.base import BaseSecurityScanner

logger = logging.getLogger(__name__)


class ScannerRegistry:
    """Registry coordinating security scanner discovery and batch execution."""

    def __init__(self) -> None:
        self._scanners: dict[str, BaseSecurityScanner] = {}

    def register(self, scanner: BaseSecurityScanner) -> None:
        """Register a security scanner instance."""
        self._scanners[scanner.name] = scanner

    def get(self, name: str) -> BaseSecurityScanner | None:
        """Retrieve a registered scanner by name."""
        return self._scanners.get(name)

    def list_scanners(self) -> list[str]:
        """List names of all registered scanners."""
        return sorted(self._scanners.keys())

    def scan_all(
        self,
        target_path: Path,
        timeout: float = DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS,
    ) -> dict[str, list[Finding]]:
        """Run all registered scanners against target_path and collect findings."""
        results: dict[str, list[Finding]] = {}
        for name, scanner in self._scanners.items():
            try:
                results[name] = scanner.scan(target_path, timeout=timeout)
            except Exception as exc:
                logger.debug("Error running scanner '%s': %s", name, exc)
                results[name] = []
        return results


global_scanner_registry = ScannerRegistry()
