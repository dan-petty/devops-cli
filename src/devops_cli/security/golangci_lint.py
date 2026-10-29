"""golangci-lint static analyzer adapter with SARIF conversion (#603).

golangci-lint loads the packages of a module through the `go` command. In the review sandbox the
scan gives it the toolchain and the module cache of the host, read-only, and its caches outside the
tree, and lets the `go` command fetch no module and no toolchain (#2129). A module whose modules
are not in the module cache is then a coverage gap, not a failed scan.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Final, NamedTuple

from devops_cli.ai.review_schema import Finding
from devops_cli.config.commands import BIN_GO, BIN_GOLANGCI_LINT
from devops_cli.config.constants import (
    CONST_GO_BUILD_CACHE_ENV,
    CONST_GO_ENV_ARGS,
    CONST_GO_ENV_TIMEOUT_SECONDS,
    CONST_GO_HOST_ENV_VARIABLES,
    CONST_GO_NO_FETCH_ENV,
    CONST_GO_PROXY_OFF_ERROR,
    CONST_GOLANGCI_LINT_CACHE_DIR_NAME,
    CONST_GOLANGCI_LINT_CACHE_ENV,
    CONST_GOMODCACHE_ENV,
    CONST_GOROOT_ENV,
    CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG,
)
from devops_cli.config.defaults import DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS
from devops_cli.core.binaries import check_binary
from devops_cli.core.process import run_subprocess
from devops_cli.security.base import (
    BaseSecurityScanner,
    ScannerConfigFile,
    ScanOutcome,
    ToolCacheDir,
    ToolDataDir,
    _evaluate_preflight,
    tree_cache_dir,
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


class GoToolchain(NamedTuple):
    """The Go toolchain of the host and the module cache that it reads, as `go env` names them."""

    root: Path
    module_cache: Path


def host_go_toolchain() -> GoToolchain | str:
    """The toolchain and the module cache of the `go` on the PATH of the host, or the reason why
    `go env` named none (#2129).

    `go env` starts in the temporary directory with `GOTOOLCHAIN=local`, so the `go.mod` of no
    reviewed tree selects another toolchain, and no toolchain is fetched. The Go variables of the
    host environment reach it, so it names the module cache that `go mod download` fills here.
    """
    done = run_subprocess(
        [BIN_GO, *CONST_GO_ENV_ARGS],
        cwd=Path(tempfile.gettempdir()),
        env=dict(CONST_GO_NO_FETCH_ENV),
        extra_allowed_env=CONST_GO_HOST_ENV_VARIABLES,
        local_read=True,
        quiet=True,
        timeout=CONST_GO_ENV_TIMEOUT_SECONDS,
    )
    if done.returncode != 0:
        return f"go env exited with code {done.returncode}: {done.stderr.strip()}"
    try:
        names = json.loads(done.stdout)
        toolchain = GoToolchain(Path(names[CONST_GOROOT_ENV]), Path(names[CONST_GOMODCACHE_ENV]))
    except json.JSONDecodeError, KeyError, TypeError:
        toolchain = None
    if toolchain is None or not all(path.is_absolute() for path in toolchain):
        return f"go env named no absolute GOROOT and GOMODCACHE: {done.stdout.strip()}"
    return toolchain


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
        # What `go env` named before the scan that runs now. It depends only on the host, so two
        # scans on two threads write the same value.
        self._toolchain: GoToolchain | None = None

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
        if not check_binary(BIN_GO):
            return ScanOutcome("failed", [], f"Binary '{BIN_GO}' not found on PATH")
        toolchain = host_go_toolchain()
        if isinstance(toolchain, str):
            return ScanOutcome("failed", [], toolchain)
        self._toolchain = toolchain
        return super()._execute(target_path, timeout, isolated, **kwargs)

    def data_dirs(self) -> tuple[ToolDataDir, ...]:
        """The toolchain and the module cache that `go env` named, which the sandbox binds
        read-only when they exist (#2129). With no module cache, the `go` command finds a module
        neither in a cache nor on a proxy (`coverage_gap`)."""
        if self._toolchain is None:
            return ()
        root, module_cache = self._toolchain
        return (
            ToolDataDir(CONST_GOROOT_ENV, root, root),
            ToolDataDir(CONST_GOMODCACHE_ENV, module_cache, module_cache),
        )

    def cache_dirs(self, tree: Path) -> tuple[ToolCacheDir, ...]:
        """The Go build cache and the golangci-lint cache of `tree`, outside the tree (#2129). In the
        sandbox they would else fall in the private HOME, a small tmpfs that goes after each run."""
        caches = tree_cache_dir(CONST_GOLANGCI_LINT_CACHE_DIR_NAME, tree)
        return (
            ToolCacheDir(CONST_GO_BUILD_CACHE_ENV, caches / "go-build"),
            ToolCacheDir(CONST_GOLANGCI_LINT_CACHE_ENV, caches / "lint"),
        )

    def tool_env(self) -> dict[str, str]:
        """No fetch of a module or a toolchain, and the `go` of the toolchain first on the PATH
        (#2129). golangci-lint starts the `go` of the PATH, and the PATH of the sandbox holds only
        system directories. The PATH of the host follows, so the direct executor finds the
        programs that it found before. No GOFLAGS: the default of the `go` command reads a
        `vendor` directory when the module has one, else `go.mod`, and never writes the tree."""
        env = dict(CONST_GO_NO_FETCH_ENV)
        if self._toolchain is not None:
            path = os.environ.get("PATH", "")
            env["PATH"] = os.pathsep.join(filter(None, (str(self._toolchain.root / "bin"), path)))
        return env

    def coverage_gap(self, proc: subprocess.CompletedProcess[str], target_path: Any) -> str | None:
        """Why a run that stopped on a module that is not in the module cache did not scan
        `target_path` (#2129). The `go` command fetches no module, so the host must hold each
        module that the scanned module needs. The reason puts the cache and the action first,
        because a reason is cut at `CONST_MAX_ERROR_DETAIL_LENGTH`."""
        if proc.returncode == 0 or CONST_GO_PROXY_OFF_ERROR not in (proc.stderr or ""):
            return None
        module_cache = self._toolchain.module_cache if self._toolchain else CONST_GOMODCACHE_ENV
        return (
            f"The Go module cache {module_cache} lacks a module that the module needs, and the "
            "scan fetches no module (GOPROXY=off). Run `go mod download` in the module, then "
            "scan again."
        )

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
