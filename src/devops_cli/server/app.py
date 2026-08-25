"""FastAPI application factory for DevOps CLI REST service."""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from devops_cli import __version__
from devops_cli.server.routes.health import router as health_router
from devops_cli.server.routes.status import router as status_router
from devops_cli.server.routes.telemetry import router as telemetry_router
from devops_cli.server.routes.workspace import router as workspace_router
from devops_cli.telemetry.tracer import get_tracer


def create_app(
    *,
    title: str = "DevOps CLI REST & OpenAPI Service",
    description: str = (
        "Asynchronous REST API and OpenAPI service engine for workstation automation, "
        "Kubernetes management, AI code reviews, and distributed telemetry."
    ),
    docs_url: str | None = "/docs",
    redoc_url: str | None = "/redoc",
    openapi_url: str | None = "/openapi.json",
) -> FastAPI:
    """Create and configure a production-ready FastAPI application."""
    app = FastAPI(
        title=title,
        description=description,
        version=__version__,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_process_time_and_trace(request: Request, call_next: Any) -> Any:
        start_time = time.perf_counter()
        span_name = f"HTTP {request.method} {request.url.path}"
        headers_dict = dict(request.headers)
        tracer = get_tracer()

        with tracer.span(
            span_name,
            attributes={
                "http.request.method": request.method,
                "url.full": str(request.url),
                "url.path": request.url.path,
                "url.scheme": request.url.scheme,
                "server.address": request.url.hostname or "localhost",
                "server.port": request.url.port or 8000,
                "user_agent.original": request.headers.get("user-agent", ""),
            },
            parent_context=headers_dict,
        ) as handle:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            response.headers["X-Process-Time"] = f"{process_time:.4f}s"
            response.headers["X-DevOps-Version"] = __version__
            handle.set_attribute("http.response.status_code", response.status_code)
            handle.set_attribute("http.status_code", response.status_code)
            return response

    @app.get("/", include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse(
            {
                "service": "DevOps CLI REST API",
                "version": __version__,
                "docs": "/docs",
                "redoc": "/redoc",
                "health": "/health",
                "status": "/api/v1/status",
                "metrics": "/metrics",
            }
        )

    # Register API routers
    app.include_router(health_router)
    app.include_router(status_router)
    app.include_router(workspace_router)
    app.include_router(telemetry_router)

    return app
