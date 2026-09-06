"""System and workstation status endpoints."""

from __future__ import annotations

import platform
import shutil
import sys

from fastapi import APIRouter
from pydantic import BaseModel, Field

from devops_cli import __version__
from devops_cli.telemetry.tracer import get_tracer

router = APIRouter(prefix="/api/v1", tags=["Status"])


class ToolStatus(BaseModel):
    """Tool availability indicators."""

    installed: bool
    path: str | None = None


class SystemStatusResponse(BaseModel):
    """Workstation status response schema."""

    version: str = Field(default=__version__, description="DevOps CLI version")
    python_version: str = Field(..., description="Python interpreter version")
    platform: str = Field(..., description="Host OS platform")
    tools: dict[str, ToolStatus] = Field(..., description="Available CLI tools")
    telemetry_enabled: bool = Field(..., description="Whether OpenTelemetry is enabled")


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    summary="Workstation and toolchain status",
)
async def get_system_status() -> SystemStatusResponse:
    """Inspect workstation tool availability, Python runtime, and telemetry."""
    tools_to_check = [
        "uv",
        "docker",
        "kubectl",
        "helm",
        "minikube",
        "tofu",
        "terraform",
        "ollama",
        "gh",
    ]
    from pathlib import Path

    tool_status: dict[str, ToolStatus] = {}
    for tool in tools_to_check:
        tool_path = shutil.which(tool)
        masked_path: str | None = None
        if tool_path:
            p = Path(tool_path)
            if any(part in ("home", "Users", "root") for part in p.parts):
                masked_path = f"[bin]/{p.name}"
            else:
                masked_path = tool_path
        tool_status[tool] = ToolStatus(
            installed=tool_path is not None,
            path=masked_path,
        )

    tracer = get_tracer()

    return SystemStatusResponse(
        version=__version__,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        tools=tool_status,
        telemetry_enabled=tracer.enabled,
    )
