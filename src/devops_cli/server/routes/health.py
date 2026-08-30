"""Health check and liveness probe endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel, Field

from devops_cli import __version__

router = APIRouter(tags=["Health"])

_START_TIME = time.time()


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(default="ok", description="Service health status")
    service: str = Field(default="devops-cli", description="Service identifier")
    version: str = Field(default=__version__, description="DevOps CLI version")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    timestamp: float = Field(default_factory=time.time, description="Current epoch timestamp")


@router.get("/health", response_model=HealthResponse, summary="Service health status")
@router.get("/healthz", response_model=HealthResponse, summary="Kubernetes liveness probe")
async def get_health() -> HealthResponse:
    """Return health status and uptime metrics."""
    return HealthResponse(
        status="ok",
        service="devops-cli",
        version=__version__,
        uptime_seconds=round(time.time() - _START_TIME, 2),
        timestamp=time.time(),
    )
