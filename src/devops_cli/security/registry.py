"""Centralized registry for security scanners and static linters."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from devops_cli.config.defaults import DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome
from devops_cli.security.golangci_lint import GolangciLintScanner

logger = logging.getLogger(__name__)


def _create_default_scanners() -> list[BaseSecurityScanner]:
    """Instantiate the 14 built-in security scanners."""
    from devops_cli.security.bandit import BanditScanner
    from devops_cli.security.checkov import CheckovScanner
    from devops_cli.security.dive import DiveScanner
    from devops_cli.security.gitleaks import GitleaksScanner
    from devops_cli.security.golangci_lint import GolangciLintScanner
    from devops_cli.security.kubeconform import KubeconformScanner
    from devops_cli.security.kubelinter import KubelinterScanner
    from devops_cli.security.osv_scanner import OsvScanner
    from devops_cli.security.pluto import PlutoScanner
    from devops_cli.security.popeye import PopeyeScanner
    from devops_cli.security.semgrep import SemgrepScanner
    from devops_cli.security.tflint import TflintScanner
    from devops_cli.security.trivy import TrivyScanner
    from devops_cli.security.zizmor import ZizmorScanner

    return [
        BanditScanner(),
        CheckovScanner(),
        DiveScanner(),
        GitleaksScanner(),
        GolangciLintScanner(),
        KubeconformScanner(),
        KubelinterScanner(),
        OsvScanner(),
        PlutoScanner(),
        PopeyeScanner(),
        SemgrepScanner(),
        TflintScanner(),
        TrivyScanner(),
        ZizmorScanner(),
    ]


class ScannerRegistry:
    """Registry coordinating security scanner discovery and batch execution."""

    def __init__(self, auto_load_defaults: bool = False) -> None:
        self._scanners: dict[str, BaseSecurityScanner] = {}
        if auto_load_defaults:
            self._load_defaults()

    def _load_defaults(self) -> None:
        """Register the default 11 built-in scanners."""
        for scanner in _create_default_scanners():
            if scanner.name not in self._scanners:
                self._scanners[scanner.name] = scanner

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
        *,
        names: Sequence[str] | None = None,
        timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
        **kwargs: Any,
    ) -> dict[str, ScanOutcome]:
        """Run the named scanners, or every registered one, against target_path.

        A scanner that raises is recorded as failed with the error as its reason, which
        `ScanOutcome` masks and bounds, so one crash does not discard every other scanner's
        findings. Names that are not registered are skipped; callers check them first.
        """
        results: dict[str, ScanOutcome] = {}
        for name in self.list_scanners() if names is None else names:
            scanner = self.get(name)
            if scanner is None:
                continue
            try:
                results[name] = scanner.scan(target_path, timeout=timeout, **kwargs)
            except Exception as exc:
                logger.debug("Scanner '%s' failed: %s", name, exc)
                results[name] = ScanOutcome("failed", [], str(exc))
        return results


global_scanner_registry = ScannerRegistry(auto_load_defaults=True)

__all__ = [
    "GolangciLintScanner",
    "ScannerRegistry",
    "global_scanner_registry",
]
