"""A command module whose commands stay unclassified or mark-only, for the tests of the dry-run
proxy (#2260).

The proxy tests need a command with no dry-run class and no `--dry-run`, and one with the
`no-external-request` class. A real command leaves that state when its item lands, so the
tests use these two stubs instead. Each command prints a line when it runs, so a test sees
whether the proxy ran the command or only printed a preview.
"""

from __future__ import annotations

import typer

from devops_cli.dry_run.decorator import dry_run_class

app = typer.Typer()


@app.command("plain")
def plain(port: int = typer.Option(8000, "--port")) -> None:
    """A command with no dry-run class and no `--dry-run`."""
    typer.echo(f"plain ran on port {port}")


@app.command("marked")
@dry_run_class("no-external-request")
def marked() -> None:
    """A command that makes no external request."""
    typer.echo("marked ran")
