"""golangci-lint static analyzer adapter with SARIF conversion (#603)."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Final

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_GOLANGCI_LINT
from devops_cli.config.constants import CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG
from devops_cli.config.defaults import DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS
from devops_cli.core.binaries import check_binary
from devops_cli.security.base import (
    BaseSecurityScanner,
    ScannerConfigFile,
    ScanOutcome,
    _evaluate_preflight,
)
from devops_cli.security.normalization import to_finding
from devops_cli.security.sarif import SarifError, from_sarif

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)

DEFAULT_LINTERS: Final[tuple[str, ...]] = ("errcheck", "govet", "staticcheck")
OPTIONAL_LINTERS: Final[tuple[str, ...]] = ("contextcheck",)


def _has_go_targets(target_path: Any) -> bool:
    """Return True if target_path references Go files or a go.mod module."""
    if isinstance(target_path, (str, Path)):
        p = Path(target_path)
        if not p.exists():
            return p.suffix == ".go" or p.name == "go.mod"
        if p.is_file():
            return p.suffix == ".go" or p.name == "go.mod"
        if (p / "go.mod").is_file():
            return True
        try:
            return next(p.rglob("*.go"), None) is not None
        except OSError as exc:
            logger.debug("Failed checking Go targets in %s: %s", p, exc)
            return False
    if isinstance(target_path, (list, tuple, set)):
        return any(_has_go_targets(item) for item in target_path)
    return False


class GolangciLintScanner(BaseSecurityScanner):
    """Declarative scanner adapter running golangci-lint with SARIF ingestion."""

    name: str = "golangci-lint"
    binary_name: str = BIN_GOLANGCI_LINT
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = False

    DEFAULT_LINTERS: ClassVar[tuple[str, ...]] = DEFAULT_LINTERS
    OPTIONAL_LINTERS: ClassVar[tuple[str, ...]] = OPTIONAL_LINTERS

    isolation_files: ClassVar[tuple[ScannerConfigFile, ...]] = (
        ScannerConfigFile("-c", ".golangci.yml", CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG),
    )

    def __init__(
        self,
        tool_executor: ToolExecutor | None = None,
        *,
        linters: Sequence[str] | None = None,
        enable_contextcheck: bool = False,
    ) -> None:
        super().__init__(tool_executor=tool_executor)
        self.linters: list[str] = (
            list(linters) if linters is not None else list(self.DEFAULT_LINTERS)
        )
        self.enable_contextcheck: bool = enable_contextcheck
        if enable_contextcheck and "contextcheck" not in self.linters:
            self.linters.append("contextcheck")

    def is_applicable(self, target_path: Any, **kwargs: Any) -> tuple[bool, str]:
        """Verify target holds Go source code or a go.mod file."""
        if _has_go_targets(target_path):
            return True, ""
        return False, "No Go source files or go.mod found in target"

    def _execute(
        self, target_path: Any, timeout: float, isolated: bool, **kwargs: Any
    ) -> ScanOutcome:
        """Run pre-flight checks and verify Go toolchain presence before execution."""
        preflight = _evaluate_preflight(self, target_path, **kwargs)
        if preflight is not None:
            return preflight
        if not check_binary("go"):
            return ScanOutcome("failed", [], "Binary 'go' not found on PATH")
        return super()._execute(target_path, timeout, isolated, **kwargs)

    def build_command(
        self,
        target_path: Any = None,
        *,
        config_file: Path | None = None,
        linters: Sequence[str] | None = None,
        enable_contextcheck: bool | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking golangci-lint."""
        cmd = [self.binary_name, "run", "--out-format", "sarif"]
        if config_file is not None and Path(config_file).exists():
            cmd.extend(["--config", str(config_file)])
        active_linters = list(linters) if linters is not None else list(self.linters)
        if enable_contextcheck or (enable_contextcheck is None and self.enable_contextcheck):
            if "contextcheck" not in active_linters:
                active_linters.append("contextcheck")
        if active_linters:
            cmd.append("--disable-all")
            for linter in active_linters:
                cmd.extend(["--enable", linter])
        return cmd

    def parse_output(self, data: Any, target_path: Any) -> list[Finding]:
        """Parse raw golangci-lint SARIF payload into Finding models."""
        if not data:
            return []
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.debug("Failed decoding golangci-lint output as JSON: %s", exc)
                return []
        if not isinstance(data, dict):
            return []
        try:
            normalized = from_sarif(data)
            return [to_finding(item) for item in normalized]
        except SarifError as exc:
            logger.debug("Failed parsing golangci-lint SARIF document: %s", exc)
            return []


def run_golangci_lint_scan(
    target_path: Any,
    timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
    *,
    tool_executor: ToolExecutor | None = None,
    linters: Sequence[str] | None = None,
    enable_contextcheck: bool = False,
    **kwargs: Any,
) -> ScanOutcome:
    """Convenience entry point for executing golangci-lint static scan."""
    scanner = GolangciLintScanner(
        tool_executor=tool_executor,
        linters=linters,
        enable_contextcheck=enable_contextcheck,
    )
    return scanner.scan(target_path, timeout=timeout, **kwargs)


__all__ = [
    "DEFAULT_LINTERS",
    "OPTIONAL_LINTERS",
    "GolangciLintScanner",
    "run_golangci_lint_scan",
]
