"""A command module whose commands keep a fixed dry-run state, for the tests of the dry-run
proxy (#2260).

The proxy tests need a command with no dry-run class and no `--dry-run`, and one with the
`no-external-request` class. A real command leaves that state when its item lands, so the
tests use these two stubs instead. The `shaped` command declares `--dry-run`, so a test can give
it each shape of argv: options with values, positionals, `--`, and a nested group. Each command
prints a line when it runs, so a test sees whether the proxy ran the command or only printed a
preview, and what the command got.
"""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.dry_run.decorator import dry_run_class


def plain(port: int = typer.Option(8000, "--port")) -> None:
    """A command with no dry-run class and no `--dry-run`."""
    typer.echo(f"plain ran on port {port}")


@dry_run_class("no-external-request")
def marked() -> None:
    """A command that makes no external request."""
    typer.echo("marked ran")


@dry_run_class("request-plan")
def shaped(
    words: Annotated[list[str] | None, typer.Argument()] = None,
    name: Annotated[str, typer.Option("--name", "-n")] = "",
    force: Annotated[bool, typer.Option("--force")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """A command that declares `--dry-run` and prints each value it gets."""
    typer.echo(f"shaped dry_run={dry_run} name={name} force={force} words={words or []}")


def _stub_app() -> typer.Typer:
    """The stub group: `plain`, `marked` and `shaped`, and `shaped` again in the group `nested`."""
    stub = typer.Typer()
    stub.command("plain")(plain)
    stub.command("marked")(marked)
    stub.command("shaped")(shaped)
    nested = typer.Typer()
    nested.command("shaped")(shaped)
    stub.add_typer(nested, name="nested")
    return stub


app = _stub_app()
