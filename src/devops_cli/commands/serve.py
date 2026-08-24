"""FastAPI REST & OpenAPI Service Engine command implementation."""

from __future__ import annotations

import typer
import uvicorn
from rich.console import Console

from devops_cli import __version__
from devops_cli.core.cli import new_typer
from devops_cli.server.app import create_app

app = new_typer(
    help="FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics.",
    rich_markup_mode="rich",
)

console = Console()


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Network interface host to bind the HTTP server.",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="TCP port to listen on.",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        "-r",
        help="Enable auto-reload on code changes (development mode).",
    ),
    workers: int = typer.Option(
        1,
        "--workers",
        "-w",
        help="Number of worker processes.",
    ),
    log_level: str = typer.Option(
        "info",
        "--log-level",
        "-l",
        help="Logging level (debug, info, warning, error).",
    ),
    docs: bool = typer.Option(
        True,
        "--docs/--no-docs",
        help="Enable or disable Swagger UI (/docs) and ReDoc (/redoc).",
    ),
) -> None:
    """Start the asynchronous FastAPI REST service and OpenAPI engine."""
    if ctx.invoked_subcommand is not None:
        return

    console.print(
        f"[bold green]Starting DevOps CLI REST & OpenAPI Service v{__version__}[/bold green]"
    )
    console.print(f"  [cyan]•[/cyan] Listening on: [bold]http://{host}:{port}[/bold]")
    if docs:
        console.print(
            f"  [cyan]•[/cyan] Swagger UI:  [link=http://{host}:{port}/docs]http://{host}:{port}/docs[/link]"
        )
        console.print(
            f"  [cyan]•[/cyan] ReDoc:       [link=http://{host}:{port}/redoc]http://{host}:{port}/redoc[/link]"
        )
        console.print(
            f"  [cyan]•[/cyan] OpenAPI JSON:[link=http://{host}:{port}/openapi.json]http://{host}:{port}/openapi.json[/link]"
        )
    console.print(
        f"  [cyan]•[/cyan] Health:      [link=http://{host}:{port}/health]http://{host}:{port}/health[/link]"
    )
    console.print(
        f"  [cyan]•[/cyan] Metrics:     [link=http://{host}:{port}/metrics]http://{host}:{port}/metrics[/link]\n"
    )

    docs_url = "/docs" if docs else None
    redoc_url = "/redoc" if docs else None
    openapi_url = "/openapi.json" if docs else None

    fastapi_app = create_app(
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    if reload:
        # In reload mode, pass module string
        uvicorn.run(
            "devops_cli.server.app:create_app",
            factory=True,
            host=host,
            port=port,
            reload=True,
            log_level=log_level.lower(),
        )
    else:
        uvicorn.run(
            fastapi_app,
            host=host,
            port=port,
            workers=workers,
            log_level=log_level.lower(),
        )
