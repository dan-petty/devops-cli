"""FastAPI REST & OpenAPI Service Engine command implementation."""

from __future__ import annotations

import typer

from devops_cli import __version__
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_info,
    print_success,
)

app = new_typer(
    help=HELP.serve.app,
    rich_markup_mode="rich",
)


# =============================================================================
# Command: devops serve
# =============================================================================


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

    print_success(
        MESSAGES.serve.starting_service.format(version=__version__),
        prefix=False,
    )
    print_info(MESSAGES.serve.listening_on.format(host=host, port=port), prefix=False)
    if docs:
        print_info(
            MESSAGES.serve.swagger_ui.format(host=host, port=port),
            prefix=False,
        )
        print_info(
            MESSAGES.serve.redoc.format(host=host, port=port),
            prefix=False,
        )
        print_info(
            MESSAGES.serve.openapi_json.format(host=host, port=port),
            prefix=False,
        )
    print_info(
        MESSAGES.serve.health_endpoint.format(host=host, port=port),
        prefix=False,
    )
    print_info(
        MESSAGES.serve.metrics_endpoint.format(host=host, port=port),
        prefix=False,
    )

    docs_url = "/docs" if docs else None
    redoc_url = "/redoc" if docs else None
    openapi_url = "/openapi.json" if docs else None

    import uvicorn

    from devops_cli.server.app import create_app

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
