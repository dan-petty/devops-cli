"""Dive container image layer efficiency and wasted space analyzer."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_DIVE_MAX_WASTED_BYTES,
    DEFAULT_DIVE_MIN_EFFICIENCY,
    DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)

# `ran`: dive analyzed the image. `unavailable`: no dive binary it will run. `failed`: dive
# ran but errored, timed out or wrote no readable export.
DiveStatus = Literal["ran", "unavailable", "failed"]


class DiveLayerInfo(BaseModel):
    """One image layer as dive's JSON export describes it."""

    index: int
    digest: str = ""
    size_bytes: int = 0
    command: str = ""


class DiveAnalysisResult(BaseModel):
    """Dive's efficiency metrics for an image, or the reason there are none.

    Only a `ran` result carries measurements; any other status leaves them empty.
    """

    image_name: str
    status: DiveStatus
    reason: str = ""
    efficiency_score: float = 0.0  # 0.0 to 1.0
    wasted_bytes: int = 0
    total_bytes: int = 0
    layers: list[DiveLayerInfo] = Field(default_factory=list)


def _parse_dive_export(image_name: str, export: dict[str, Any]) -> DiveAnalysisResult:
    """Read the analysis from dive's JSON export (wagoodman/dive `export.Export`)."""
    image = export["image"]
    return DiveAnalysisResult(
        image_name=image_name,
        status="ran",
        efficiency_score=image["efficiencyScore"],
        wasted_bytes=image["inefficientBytes"],
        total_bytes=image["sizeBytes"],
        layers=[
            DiveLayerInfo(
                index=layer["index"],
                digest=layer["digestId"],
                size_bytes=layer["sizeBytes"],
                command=layer["command"],
            )
            for layer in export["layer"]
        ],
    )


def _run_dive_export(dive_bin: str, image_name: str, timeout: float) -> DiveAnalysisResult:
    """Run dive with its JSON export pointed at a private file, then read that file.

    `--json` names a file dive writes, never stdout: a `-` would create a file named `-`.
    """
    failed = DiveAnalysisResult(image_name=image_name, status="failed")
    with tempfile.TemporaryDirectory(prefix="devops-dive-") as export_dir:
        export_path = Path(export_dir) / "dive-export.json"
        try:
            proc = run_subprocess(
                [dive_bin, image_name, "--json", str(export_path)], timeout=timeout, check=False
            )
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "").strip()[:256]
                return failed.model_copy(
                    update={"reason": f"dive exited with code {proc.returncode}: {detail}"}
                )
            if not export_path.is_file():
                return failed.model_copy(update={"reason": "dive wrote no JSON export"})
            export = json.loads(export_path.read_text(encoding="utf-8"))
            return _parse_dive_export(image_name, export)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
            logger.debug("Dive analysis of %s failed: %s", image_name, exc)
            return failed.model_copy(update={"reason": f"dive failed: {str(exc)[:256]}"})


@trace_span("docker.dive")
def run_dive_analysis(
    image_name: str,
    timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
) -> DiveAnalysisResult:
    """Analyze an image's layers with dive, or say why it could not: never a made-up result."""
    dive_bin = shutil.which("dive")
    if not dive_bin:
        return DiveAnalysisResult(
            image_name=image_name, status="unavailable", reason="dive is not on PATH"
        )
    if Path(dive_bin).is_symlink():
        return DiveAnalysisResult(
            image_name=image_name,
            status="unavailable",
            reason=f"dive at {dive_bin} is a symlink, which is not executed",
        )
    return _run_dive_export(dive_bin, image_name, timeout)


class DiveScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Dive container layer efficiency."""

    name: str = "dive"
    binary_name: str = "dive"
    gating: ClassVar[bool] = False
    has_builtin_patterns: ClassVar[bool] = False

    def is_applicable(self, target_path: Path, **kwargs: Any) -> tuple[bool, str]:
        """Determine if target represents a container image rather than a filesystem directory."""
        image_name = kwargs.get("image") or kwargs.get("image_name")
        if image_name:
            return True, ""
        if isinstance(target_path, Path):
            if target_path.exists() and target_path.is_dir():
                return (
                    False,
                    f"Dive requires container image target; skipping directory {target_path}",
                )
        elif isinstance(target_path, str):
            p = Path(target_path)
            if p.exists() and p.is_dir():
                return (
                    False,
                    f"Dive requires container image target; skipping directory {target_path}",
                )
        return True, ""

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        """Name dive and the image it analyzes, from kwargs ('image' or 'image_name') or the target.

        Returns an empty list for a filesystem directory with no image, to skip it.
        """
        image_name = kwargs.get("image") or kwargs.get("image_name")
        if not image_name:
            if target_path.exists() and target_path.is_dir():
                logger.debug(
                    "Dive scanner requires container image target; skipping filesystem directory %s",
                    target_path,
                )
                return []
            image_name = str(target_path)
        return [self.binary_name, str(image_name)]

    def _run_scanner_command(
        self, cmd: list[str], cwd_dir: Path, target_path: Any, timeout: float
    ) -> ScanOutcome:
        """Run dive through `run_dive_analysis`, since dive writes its analysis to a file."""
        analysis = run_dive_analysis(cmd[1], timeout=timeout)
        if analysis.status != "ran":
            return ScanOutcome(analysis.status, [], analysis.reason)
        return ScanOutcome("ran", self.parse_output(analysis, target_path))

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Flag a completed dive analysis that misses the efficiency or wasted-space threshold."""
        if not isinstance(data, DiveAnalysisResult):
            return []
        efficiency, wasted_bytes, img = data.efficiency_score, data.wasted_bytes, data.image_name
        if (
            efficiency >= DEFAULT_DIVE_MIN_EFFICIENCY
            and wasted_bytes <= DEFAULT_DIVE_MAX_WASTED_BYTES
        ):
            return []
        return [
            Finding(
                severity="MEDIUM",
                location=f"{img}:efficiency",
                title=f"[DIVE:layer-inefficiency] Efficiency Score {efficiency:.2f}",
                description=(
                    f"Image {img} has an efficiency score of {efficiency:.2f} with "
                    f"{wasted_bytes} wasted bytes across layers."
                ),
                fix="Combine consecutive RUN commands and prune build caches to optimize image layers.",
            )
        ]

    def dry_run_scan(self, target_path: Path, **kwargs: Any) -> list[Finding]:
        """Return simulated Dive layer inspection findings."""
        return [
            Finding(
                severity="LOW",
                location=f"{target_path}:dry-run",
                title="[DIVE] [DRY-RUN] Simulated Container Layer Efficiency Audit",
                description="Dive layer efficiency simulation mode active.",
                fix="No action required (dry-run mode)",
            )
        ]


def run_dive_scan(
    target: Path | str = DEFAULT_CURRENT_PATH,
    **kwargs: Any,
) -> ScanOutcome:
    """Execute Dive container layer scanner and return scan outcome."""
    scanner = DiveScanner()
    tgt = Path(target) if isinstance(target, str) else target
    return scanner.scan(tgt, **kwargs)
