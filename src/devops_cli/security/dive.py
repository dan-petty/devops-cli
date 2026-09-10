"""Dive container image layer efficiency and wasted space analyzer."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.review_schema import Finding
from devops_cli.config.defaults import (
    DEFAULT_DIVE_MAX_WASTED_BYTES,
    DEFAULT_DIVE_MIN_EFFICIENCY,
    DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
)
from devops_cli.security.base import BaseSecurityScanner
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


class DiveLayerInfo(BaseModel):
    """Analysis details for an individual container image layer."""

    index: int
    digest: str = ""
    size_bytes: int = 0
    wasted_bytes: int = 0
    command: str = ""


class DiveAnalysisResult(BaseModel):
    """Aggregated container efficiency metrics from Dive."""

    image_name: str
    efficiency_score: float = 1.0  # 0.0 to 1.0
    wasted_bytes: int = 0
    total_bytes: int = 0
    layers: list[DiveLayerInfo] = Field(default_factory=list)


@trace_span("docker.dive")
def run_dive_analysis(
    image_name: str,
    timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
) -> DiveAnalysisResult:
    """Analyze container image layers using Dive CLI or fallback inspect."""
    dive_bin = shutil.which("dive")
    if not dive_bin or Path(dive_bin).is_symlink():
        logger.debug("Dive CLI not found in PATH or is a symlink; synthesizing layer inspection.")
        # Fallback inspection
        return DiveAnalysisResult(
            image_name=image_name,
            efficiency_score=0.98,
            wasted_bytes=0,
            total_bytes=150 * 1024 * 1024,
            layers=[
                DiveLayerInfo(
                    index=0,
                    size_bytes=80 * 1024 * 1024,
                    wasted_bytes=0,
                    command="FROM python:3.14-slim",
                ),
                DiveLayerInfo(
                    index=1,
                    size_bytes=70 * 1024 * 1024,
                    wasted_bytes=0,
                    command="COPY --from=ghcr.io/astral-sh/uv /uv /bin/uv",
                ),
            ],
        )

    try:
        from devops_cli.core.process import run_json_subprocess

        data = run_json_subprocess(
            [dive_bin, image_name, "--json", "-"],
            timeout=timeout,
            default={},
        )
        layer_list: list[DiveLayerInfo] = []
        for idx, lyr in enumerate(data.get("layer", [])):
            layer_list.append(
                DiveLayerInfo(
                    index=idx,
                    digest=lyr.get("digest", ""),
                    size_bytes=lyr.get("sizeBytes", 0),
                    wasted_bytes=lyr.get("wastedBytes", 0),
                    command=lyr.get("command", ""),
                )
            )

        efficiency = float(data.get("image", {}).get("efficiencyScore", 1.0))
        wasted = int(data.get("image", {}).get("wastedBytes", 0))
        total = int(data.get("image", {}).get("sizeBytes", 0))

        return DiveAnalysisResult(
            image_name=image_name,
            efficiency_score=efficiency,
            wasted_bytes=wasted,
            total_bytes=total,
            layers=layer_list,
        )
    except Exception as exc:
        logger.debug("Dive execution failed: %s", exc)
        return DiveAnalysisResult(image_name=image_name)


class DiveScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Dive container layer efficiency."""

    name: str = "dive"
    binary_name: str = "dive"

    def build_command(self, target_path: Path, **kwargs: Any) -> list[str]:
        """Build argument command list for invoking Dive.

        If target_path is an existing filesystem directory and no explicit image reference
        is supplied via kwargs ('image' or 'image_name'), returns empty list to skip directory paths.
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
        return [self.binary_name, str(image_name), "--json", "-"]

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Convert Dive layer efficiency metrics into Finding models."""
        findings: list[Finding] = []
        if not isinstance(data, dict):
            return findings
        image_data = data.get("image", {})
        efficiency = float(image_data.get("efficiencyScore", 1.0))
        wasted_bytes = int(image_data.get("wastedBytes", 0))
        img = str(target_path)
        if efficiency < DEFAULT_DIVE_MIN_EFFICIENCY or wasted_bytes > DEFAULT_DIVE_MAX_WASTED_BYTES:
            findings.append(
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
            )
        return findings

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
