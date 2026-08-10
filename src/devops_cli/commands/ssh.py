"""SSH key management commands."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.cli import new_typer

app = new_typer(
    help="SSH key generation, rotation, and GitHub registration.",
    no_args_is_help=True,
)
console = Console()

_GRACE_DAYS = 7


def _date_suffix() -> str:
    """Return today as YYYYMMMDD in uppercase, e.g. 2024JAN15."""
    return date.today().strftime("%Y%b%d").upper()


def _configure_git_signing(key_path: Path) -> None:
    """Point git's SSH commit signing at *key_path*."""
    for cmd in [
        ["git", "config", "--global", "gpg.format", "ssh"],
        ["git", "config", "--global", "user.signingkey", str(key_path)],
        ["git", "config", "--global", "commit.gpgsign", "true"],
        ["git", "config", "--global", "tag.gpgsign", "true"],
    ]:
        subprocess.run(cmd, check=True, capture_output=True)


@app.command()
def generate(
    key_dir: Annotated[Path | None, typer.Option("--key-dir")] = None,
    comment: Annotated[str, typer.Option("--comment", "-c")] = "",
) -> None:
    """Generate a new Ed25519 SSH key with today's date suffix."""
    from devops_cli.config import load_settings
    from devops_cli.crypto.ssh_keys import generate_ed25519_key

    settings = load_settings()
    kdir = key_dir or settings.ssh.key_dir
    key_path = kdir / f"id_ed25519-{_date_suffix()}"

    if key_path.exists():
        rprint(f"[yellow]Key already exists: {key_path}[/yellow]")
        raise typer.Exit(1)

    generate_ed25519_key(key_path, comment=comment or f"devops-cli-{date.today().isoformat()}")
    rprint(f"[green]Generated:[/green] {key_path}")
    rprint(f"[green]Public key:[/green] {key_path}.pub")
    rprint("\nRun [bold]devops ssh register[/bold] to add it to GitHub.")


@app.command()
def register(
    key_file: Annotated[
        Path | None, typer.Option("--key-file", "-k", help="Path to private key")
    ] = None,
    title: Annotated[str | None, typer.Option("--title")] = None,
) -> None:
    """Register an SSH key on GitHub for git access and commit signing."""
    from devops_cli.config import get_github_token, load_settings
    from devops_cli.crypto.ssh_keys import find_newest_key
    from devops_cli.github.ssh import register_key_on_github

    settings = load_settings()
    token = get_github_token(settings)
    if not token:
        rprint("[red]GitHub token not configured. Run 'devops config init'.[/red]")
        raise typer.Exit(1)

    if key_file is None:
        key_file = find_newest_key(settings.ssh.key_dir)
        if key_file is None:
            rprint("[red]No managed SSH key found. Run 'devops ssh generate' first.[/red]")
            raise typer.Exit(1)

    pub_path = key_file.with_name(f"{key_file.name}.pub")
    if not pub_path.exists():
        rprint(f"[red]Public key not found: {pub_path}[/red]")
        raise typer.Exit(1)

    pub_key = pub_path.read_text(encoding="utf-8").strip()
    key_title = title or f"devops-cli-{_date_suffix()}"

    register_key_on_github(token, pub_key, key_title)
    _configure_git_signing(key_file)
    rprint(f"[green]✓[/green] Registered [bold]{key_title}[/bold] on GitHub (auth + signing).")
    rprint(
        "[green]✓[/green] Configured [dim]gpg.format=ssh[/dim] and [dim]commit.gpgsign=true[/dim]."
    )


@app.command()
def rotate(
    key_dir: Annotated[Path | None, typer.Option("--key-dir")] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Rotate even if not yet due")
    ] = False,
) -> None:
    """Rotate keys older than rotation_days (default 90).

    Generates, registers, and reports the old key.
    """
    from devops_cli.config import get_github_token, load_settings
    from devops_cli.crypto.ssh_keys import find_newest_key, generate_ed25519_key, get_key_age_days
    from devops_cli.github.ssh import register_key_on_github

    settings = load_settings()
    kdir = key_dir or settings.ssh.key_dir

    newest = find_newest_key(kdir)
    if newest is None:
        rprint("[yellow]No managed SSH keys found. Run 'devops ssh generate' first.[/yellow]")
        raise typer.Exit(0)

    age = get_key_age_days(newest)
    if age < settings.ssh.rotation_days and not force:
        rprint(
            f"[green]Key is {age} days old "
            f"(rotation at {settings.ssh.rotation_days}d). No rotation needed.[/green]"
        )
        raise typer.Exit(0)

    rprint(f"[yellow]Key is {age} days old — rotating...[/yellow]")

    new_key_path = kdir / f"id_ed25519-{_date_suffix()}"
    if new_key_path.exists():
        rprint(f"[yellow]New key already exists: {new_key_path}[/yellow]")
    else:
        generate_ed25519_key(new_key_path, comment=f"devops-cli-{date.today().isoformat()}")
        rprint(f"[green]✓[/green] Generated: {new_key_path}")

    token = get_github_token(settings)
    if token:
        pub_key = (
            new_key_path.with_name(f"{new_key_path.name}.pub").read_text(encoding="utf-8").strip()
        )
        register_key_on_github(token, pub_key, f"devops-cli-{_date_suffix()}")
        _configure_git_signing(new_key_path)
        rprint("[green]✓[/green] Registered new key and updated git signing config.")
    else:
        rprint(
            "[yellow]No GitHub token — run 'devops ssh register' after configuring token.[/yellow]"
        )

    rprint(
        f"\n[dim]Old key {newest.name} remains active for {_GRACE_DAYS} grace days. "
        f"Delete manually when ready: rm {newest} {newest}.pub[/dim]"
    )


@app.command("list")
def list_keys(
    key_dir: Annotated[Path | None, typer.Option("--key-dir")] = None,
) -> None:
    """List all managed SSH keys with their age and rotation status."""
    from devops_cli.config import load_settings
    from devops_cli.crypto.ssh_keys import get_key_age_days, list_managed_keys

    settings = load_settings()
    kdir = key_dir or settings.ssh.key_dir
    keys = list_managed_keys(kdir)

    if not keys:
        rprint("[yellow]No managed SSH keys found (expected: id_ed25519-YYYYMMMDD).[/yellow]")
        raise typer.Exit(0)

    rot = settings.ssh.rotation_days
    table = Table(title="Managed SSH Keys")
    table.add_column("Key", style="cyan")
    table.add_column("Age (days)", justify="right")
    table.add_column("Status")

    for key_path in sorted(keys):
        age = get_key_age_days(key_path)
        if age > rot + _GRACE_DAYS:
            status = "[red]overdue for deletion[/red]"
        elif age > rot:
            status = "[yellow]grace period[/yellow]"
        elif age > rot - 7:
            status = "[yellow]rotation soon[/yellow]"
        else:
            status = "[green]active[/green]"
        table.add_row(key_path.name, str(age), status)

    console.print(table)


@app.command()
def status(
    key_dir: Annotated[Path | None, typer.Option("--key-dir")] = None,
) -> None:
    """Show the active SSH key and days until rotation."""
    from devops_cli.config import load_settings
    from devops_cli.crypto.ssh_keys import find_newest_key, get_key_age_days

    settings = load_settings()
    kdir = key_dir or settings.ssh.key_dir
    rot = settings.ssh.rotation_days

    newest = find_newest_key(kdir)
    if newest is None:
        rprint("[yellow]No managed SSH keys found. Run 'devops ssh generate'.[/yellow]")
        raise typer.Exit(0)

    age = get_key_age_days(newest)
    days_left = rot - age

    rprint(f"Active key:  [bold cyan]{newest.name}[/bold cyan]")
    rprint(f"Age:         [bold]{age}[/bold] days")
    if days_left > 7:
        rprint(f"Rotation:    [green]{days_left} days remaining[/green]")
    elif days_left > 0:
        rprint(f"Rotation:    [yellow]{days_left} days remaining[/yellow]")
    else:
        rprint(f"Rotation:    [red]overdue by {-days_left} days — run 'devops ssh rotate'[/red]")
