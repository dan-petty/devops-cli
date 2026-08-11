"""SSH key management commands."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.core.cli import new_typer

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
    from devops_cli.core.process import run_subprocess

    for cmd in [
        ["git", "config", "--global", "gpg.format", "ssh"],
        ["git", "config", "--global", "user.signingkey", str(key_path)],
        ["git", "config", "--global", "commit.gpgsign", "true"],
        ["git", "config", "--global", "tag.gpgsign", "true"],
    ]:
        run_subprocess(cmd, check=True)


@app.command()
def generate(
    key_dir: Annotated[Path | None, typer.Option("--key-dir")] = None,
    comment: Annotated[str, typer.Option("--comment", "-c")] = "",
) -> None:
    """Generate a new Ed25519 SSH key with today's date suffix."""
    from devops_cli.config.settings import load_settings
    from devops_cli.crypto.ssh_keys import generate_ed25519_key
    from devops_cli.dry_run import CommandDryRunResult, is_dry_run

    if is_dry_run():
        res = CommandDryRunResult(
            command="devops ssh generate",
            action="generate_ed25519_ssh_key",
            details={"key_dir": str(key_dir) if key_dir else None, "comment": comment},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    settings = load_settings()
    target_key_dir = key_dir or settings.ssh.key_dir
    target_key_dir.mkdir(parents=True, exist_ok=True)
    key_path = target_key_dir / f"id_ed25519-{_date_suffix()}"

    from devops_cli.lang import MESSAGES

    if key_path.exists():
        rprint(f"[yellow]{MESSAGES.messages.key_already_exists.format(key_path=key_path)}[/yellow]")
        raise typer.Exit(1)

    generate_ed25519_key(key_path, comment=comment or f"devops-cli-{date.today().isoformat()}")
    rprint(f"[green]{MESSAGES.messages.generated_key.format(key_path=key_path)}[/green]")
    pub_path = key_path.with_name(f"{key_path.name}.pub")
    rprint(f"[green]{MESSAGES.messages.public_key_path.format(pub_path=pub_path)}[/green]")
    rprint("\nRun [bold]devops ssh register[/bold] to add it to GitHub.")


@app.command()
def register(
    key_file: Annotated[
        Path | None, typer.Option("--key-file", "-k", help="Path to private key")
    ] = None,
    title: Annotated[str | None, typer.Option("--title")] = None,
) -> None:
    from devops_cli.config.settings import get_github_token, load_settings
    from devops_cli.crypto.ssh_keys import find_newest_key
    from devops_cli.dry_run import CommandDryRunResult, is_dry_run
    from devops_cli.github.ssh import SSHRegistrationError, register_key_on_github
    from devops_cli.lang import MESSAGES

    if is_dry_run():
        res = CommandDryRunResult(
            command="devops ssh register",
            action="register_ssh_key_on_github",
            details={"key_file": str(key_file) if key_file else None, "title": title},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    settings = load_settings()
    token = get_github_token(settings)

    if key_file is None:
        key_file = find_newest_key(settings.ssh.key_dir)
        if key_file is None:
            rprint(f"[red]{MESSAGES.messages.no_ssh_key_found}[/red]")
            raise typer.Exit(1)

    pub_path = key_file.with_name(f"{key_file.name}.pub")
    if not pub_path.exists():
        rprint(f"[red]{MESSAGES.messages.public_key_not_found.format(pub_path=pub_path)}[/red]")
        raise typer.Exit(1)

    pub_key = pub_path.read_text(encoding="utf-8").strip()
    key_title = title or f"devops-cli-{_date_suffix()}"

    try:
        register_key_on_github(pub_key, key_title, token=token)
    except SSHRegistrationError as exc:
        from devops_cli.commands.review import _mask_secrets_in_content
        from devops_cli.lang import MESSAGES

        masked_err = _mask_secrets_in_content(str(exc))
        rprint(f"[red]{MESSAGES.messages.failed_to_register_key.format(error=masked_err)}[/red]")
        rprint(f"[yellow]{MESSAGES.messages.gh_auth_refresh_tip}[/yellow]")
        raise typer.Exit(1)

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
    from devops_cli.config.settings import get_github_token, load_settings
    from devops_cli.crypto.ssh_keys import find_newest_key, generate_ed25519_key, get_key_age_days
    from devops_cli.dry_run import CommandDryRunResult, is_dry_run
    from devops_cli.github.ssh import SSHRegistrationError, register_key_on_github

    if is_dry_run():
        res = CommandDryRunResult(
            command="devops ssh rotate",
            action="rotate_ssh_keys",
            details={"key_dir": str(key_dir) if key_dir else None, "force": force},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    settings = load_settings()
    target_key_dir = key_dir or settings.ssh.key_dir

    newest = find_newest_key(target_key_dir)
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

    new_key_path = target_key_dir / f"id_ed25519-{_date_suffix()}"
    created_new = False
    if new_key_path.exists():
        rprint(f"[yellow]New key already exists: {new_key_path}[/yellow]")
    else:
        generate_ed25519_key(new_key_path, comment=f"devops-cli-{date.today().isoformat()}")
        created_new = True
        rprint(f"[green]✓[/green] Generated: {new_key_path}")

    token = get_github_token(settings)
    pub_key = new_key_path.with_name(f"{new_key_path.name}.pub").read_text(encoding="utf-8").strip()
    try:
        register_key_on_github(pub_key, f"devops-cli-{_date_suffix()}", token=token)
        _configure_git_signing(new_key_path)
        rprint("[green]✓[/green] Registered new key and updated git signing config.")
    except SSHRegistrationError as exc:
        if created_new:
            new_key_path.unlink(missing_ok=True)
            new_key_path.with_name(f"{new_key_path.name}.pub").unlink(missing_ok=True)
        rprint(f"[yellow]GitHub key registration failed:[/yellow] {exc}")
        rprint("[yellow]Cleaned up un-registered key files. Fix auth and re-run rotation.[/yellow]")

    rprint(
        f"\n[dim]Old key {newest.name} remains active for {_GRACE_DAYS} grace days. "
        f"Delete manually when ready: rm {newest} {newest}.pub[/dim]"
    )


@app.command("audit")
@app.command("list")
def list_keys(
    key_dir: Annotated[Path | None, typer.Option("--key-dir")] = None,
) -> None:
    """List all managed SSH keys with their age and rotation status."""
    from devops_cli.config.settings import load_settings
    from devops_cli.crypto.ssh_keys import list_managed_keys_info
    from devops_cli.dry_run import CommandDryRunResult, is_dry_run

    if is_dry_run():
        res = CommandDryRunResult(
            command="devops ssh list",
            action="audit_ssh_keys",
            details={},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    settings = load_settings()
    target_key_dir = key_dir or settings.ssh.key_dir
    keys = list_managed_keys_info(target_key_dir)

    if not keys:
        rprint("[yellow]No managed SSH keys found (expected: id_ed25519-YYYYMMMDD).[/yellow]")
        raise typer.Exit(0)

    rotation_days = settings.ssh.rotation_days
    table = Table(title="Managed SSH Keys")
    table.add_column("Key", style="cyan")
    table.add_column("Age (days)", justify="right")
    table.add_column("Status")

    for key in keys:
        age = key.age_days if key.age_days is not None else 0
        if age > rotation_days + _GRACE_DAYS:
            status_text = "[red]overdue for deletion[/red]"
        elif age > rotation_days:
            status_text = "[yellow]grace period[/yellow]"
        elif age > rotation_days - 7:
            status_text = "[yellow]rotation soon[/yellow]"
        else:
            status_text = "[green]active[/green]"
        table.add_row(key.path.name, str(age), status_text)

    console.print(table)


@app.command()
def status(
    key_dir: Annotated[Path | None, typer.Option("--key-dir")] = None,
) -> None:
    """Show the active SSH key and days until rotation."""
    from devops_cli.config.settings import load_settings
    from devops_cli.crypto.ssh_keys import find_newest_key, get_key_age_days
    from devops_cli.dry_run import CommandDryRunResult, is_dry_run

    if is_dry_run():
        res = CommandDryRunResult(
            command="devops ssh status",
            action="get_ssh_key_status",
            details={},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    settings = load_settings()
    target_key_dir = key_dir or settings.ssh.key_dir
    rotation_days = settings.ssh.rotation_days

    newest = find_newest_key(target_key_dir)
    if newest is None:
        rprint("[yellow]No managed SSH keys found. Run 'devops ssh generate'.[/yellow]")
        raise typer.Exit(0)

    age = get_key_age_days(newest)
    days_left = rotation_days - age

    rprint(f"Active key:  [bold cyan]{newest.name}[/bold cyan]")
    rprint(f"Age:         [bold]{age}[/bold] days")
    if days_left > 7:
        rprint(f"Rotation:    [green]{days_left} days remaining[/green]")
    elif days_left > 0:
        rprint(f"Rotation:    [yellow]{days_left} days remaining[/yellow]")
    else:
        rprint(f"Rotation:    [red]overdue by {-days_left} days — run 'devops ssh rotate'[/red]")
