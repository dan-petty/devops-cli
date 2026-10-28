"""FastAPI REST & OpenAPI Service Engine command implementation."""

from __future__ import annotations

import json
from functools import partial
from typing import TYPE_CHECKING

import typer

from devops_cli import __version__
from devops_cli.config.defaults import (
    DEFAULT_LOG_LEVEL,
    DEFAULT_REST_HOST,
    DEFAULT_REST_PORT,
    DEFAULT_SERVER_WORKERS,
)
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
)

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings

app = new_typer(
    help=HELP.serve.app,
    rich_markup_mode="rich",
)


def _require_github_app(settings: Settings) -> None:
    """Exit 1 unless the Service can act as its GitHub App: the App's settings are set and the
    environment holds the App's private key (ADR 0015)."""
    from devops_cli.config.constants import CONST_GITHUB_APP_PRIVATE_KEY_ENV
    from devops_cli.core.process import acts_as_github_app

    app_config = settings.service.github_app
    missing = [
        option
        for option, value in (
            ("service.github_app.app_id", app_config.app_id),
            ("service.github_app.installation_id", app_config.installation_id),
            ("service.github_app.slug", app_config.slug),
        )
        if not value
    ]
    if missing:
        print_error(
            MESSAGES.serve.github_app_unset.format(settings=", ".join(missing)), prefix=False
        )
        raise typer.Exit(code=1)
    if not acts_as_github_app():
        print_error(
            MESSAGES.serve.github_app_key_missing.format(
                login=app_config.bot_login, key_env=CONST_GITHUB_APP_PRIVATE_KEY_ENV
            ),
            prefix=False,
            safe=True,
        )
        raise typer.Exit(code=1)


def _validate_service_mode(
    reload: bool,
    workers: int,
    settings: Settings,
) -> dict[str, str]:
    """Validate options and managed credentials for continuous service mode."""
    if reload:
        print_error("Service mode does not support auto-reload (--reload).", prefix=False)
        raise typer.Exit(code=2)
    if workers > 1:
        print_error(
            "Service mode does not support multiple worker processes (--workers > 1).", prefix=False
        )
        raise typer.Exit(code=2)

    if not settings.service.repos:
        print_error(
            "Configuration error: service.repos must configure at least one target repository.",
            prefix=False,
        )
        raise typer.Exit(code=1)
    _require_github_app(settings)

    from devops_cli.config.settings import get_service_webhook_secrets

    raw_secrets = get_service_webhook_secrets(settings)
    if not raw_secrets:
        print_error(
            "Configuration error: managed credential 'service.webhook_secrets' is missing or empty.",
            prefix=False,
        )
        raise typer.Exit(code=1)
    try:
        parsed = json.loads(raw_secrets)
        if not isinstance(parsed, dict):
            raise ValueError("Must be a JSON object")
        return {str(k): str(v) for k, v in parsed.items()}
    except Exception:
        print_error(
            "Configuration error: managed credential 'service.webhook_secrets' must be a valid JSON object.",
            prefix=False,
        )
        raise typer.Exit(code=1) from None


# =============================================================================
# Command: devops serve
# =============================================================================


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    host: str = typer.Option(
        DEFAULT_REST_HOST,
        "--host",
        "-h",
        help=HELP.serve.host,
    ),
    port: int = typer.Option(
        DEFAULT_REST_PORT,
        "--port",
        "-p",
        help=HELP.serve.port,
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        "-r",
        help=HELP.serve.reload,
    ),
    workers: int = typer.Option(
        DEFAULT_SERVER_WORKERS,
        "--workers",
        "-w",
        help=HELP.serve.workers,
    ),
    log_level: str = typer.Option(
        DEFAULT_LOG_LEVEL,
        "--log-level",
        "-l",
        help=HELP.serve.log_level,
    ),
    docs: bool = typer.Option(
        True,
        "--docs/--no-docs",
        help=HELP.serve.docs,
    ),
    service: bool = typer.Option(
        False,
        "--service",
        "-s",
        help=HELP.serve.service,
    ),
) -> None:
    """Start the asynchronous FastAPI REST service and OpenAPI engine."""
    if ctx.invoked_subcommand is not None:
        return

    import uvicorn

    if service:
        from devops_cli.config.settings import load_settings
        from devops_cli.roadmap.run import SERVICE_JOBS, identity_refused
        from devops_cli.server.json_logs import service_log_config
        from devops_cli.server.service import create_service_app

        settings = load_settings()
        parsed_secrets = _validate_service_mode(reload=reload, workers=workers, settings=settings)

        # uvicorn calls this factory after it applies log_config, so the warnings building the app
        # logs (a managed repository with no webhook secret) are JSON too.
        uvicorn.run(
            partial(
                create_service_app,
                jobs=SERVICE_JOBS,
                settings=settings,
                secrets=parsed_secrets,
                identity_refused=identity_refused,
            ),
            factory=True,
            host=host,
            port=port,
            log_config=service_log_config(log_level),
        )
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
