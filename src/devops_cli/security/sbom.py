"""Software Bill of Materials (SBOM) generation via Aqua Trivy (#1439)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from devops_cli.config.commands import build_trivy_sbom_cmd
from devops_cli.config.defaults import (
    DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
    DEFAULT_TRIVY_SEVERITIES,
)
from devops_cli.exceptions.tools import DependencyError, ToolExecutionError
from devops_cli.security.trivy import TrivyScanner

if TYPE_CHECKING:
    from devops_cli.ai.review_schema import Finding
    from devops_cli.security.tool_executor import ToolExecutor


class TrivySbomScanner(TrivyScanner):
    """Aqua Trivy SBOM generator using the security scanner base."""

    def build_command(
        self,
        target_path: Path,
        scan_type: str | None = None,
        severity: str = DEFAULT_TRIVY_SEVERITIES,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Trivy SBOM generation."""
        format_type = str(kwargs.get("format_type", "cyclonedx"))
        return build_trivy_sbom_cmd(target_path, format_type=format_type)

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """SBOM generation produces raw documents rather than review findings."""
        return []

    def run_sbom(
        self,
        target_path: Path,
        format_type: str = "cyclonedx",
        timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
    ) -> str:
        """Execute Trivy to generate an SBOM document through the scanner base."""
        if not self._check_binary():
            raise DependencyError(tool_name=self.binary_name)

        cmd = self.build_command(target_path, format_type=format_type)
        cwd = self._resolve_cwd(target_path)
        proc = self._run_tool(cmd, cwd, target_path, timeout)
        if proc.returncode != 0:
            raise ToolExecutionError(
                f"Trivy SBOM generation failed with code {proc.returncode}: {proc.stderr.strip()}",
                tool_name=self.binary_name,
                exit_code=proc.returncode or 1,
            )
        return str(proc.stdout or "")


def run_trivy_sbom(
    target: Path,
    format_type: str = "cyclonedx",
    *,
    tool_executor: ToolExecutor | None = None,
    timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS,
) -> str:
    """Generate an SBOM document using Trivy through the scanner base."""
    scanner = TrivySbomScanner(tool_executor=tool_executor)
    return scanner.run_sbom(target, format_type=format_type, timeout=timeout)


__all__ = [
    "TrivySbomScanner",
    "run_trivy_sbom",
]
