"""SSH key management commands."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.constants import CONST_SSH_GRACE_DAYS
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_status_badge,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    render_dry_run_result,
)

app = new_typer(
    help=HELP.ssh.app,
    no_args_is_help=True,
)


# =============================================================================
# SSH Key Formatting & Git Signing Helpers
# =============================================================================


def _date_suffix() -> str:
    """Return today as YYYYMMDD, e.g. 20260831."""
    return date.today().strftime("%Y%m%d")


def _configure_git_signing(key_path: Path) -> None:
    """Point git's SSH commit signing at *key_path*."""
    from devops_cli.core.process import run_subprocess

    for cmd in [
        ["git", "config", "--global", "gpg.format", "ssh"],
        ["git", "config", "--global", "user.signingkey", str(key_path)],
        ["git", "config", "--global", "commit.gpgsign", "true"],
    ]:
        run_subprocess(cmd, quiet=True)
    print_success(MESSAGES.ssh.configured_signing, prefix=False)


# =============================================================================
# Command: devops ssh generate
# =============================================================================


@app.command()
def generate(
    key_dir: Annotated[Path | None, typer.Option("--key-dir", help=HELP.ssh.key_dir)] = None,
    comment: Annotated[str, typer.Option("--comment", "-c", help=HELP.ssh.comment)] = "",
    prefix: Annotated[
        str | None,
        typer.Option(
            "--prefix",
            "-p",
            help="Optional prefix for the SSH key name (defaults to config setting, devcontainer name, or basename pwd).",
        ),
    ] = None,
) -> None:
    """Generate a new Ed25519 SSH key with prefix and YYYYMMDD date suffix."""
    from devops_cli.config.settings import load_settings
    from devops_cli.crypto.ssh_keys import (
        generate_ed25519_key,
        get_ssh_key_prefix,
    )
    from devops_cli.dry_run import is_dry_run

    if is_dry_run():
        render_dry_run_result(
            command="devops ssh generate",
            action="generate_ed25519_ssh_key",
            details={
                "key_dir": str(key_dir) if key_dir else None,
                "comment": comment,
                "prefix": prefix,
            },
        )
        return

    settings = load_settings()
    target_key_dir = (key_dir or settings.ssh.key_dir).expanduser()
    target_key_dir.mkdir(parents=True, exist_ok=True)
    active_prefix = (
        prefix if prefix is not None else (settings.ssh.key_prefix or get_ssh_key_prefix())
    )
    filename = (
        f"{active_prefix}-id_ed25519-{_date_suffix()}"
        if active_prefix
        else f"id_ed25519-{_date_suffix()}"
    )
    key_path = target_key_dir / filename

    if key_path.exists():
        print_warning(MESSAGES.messages.key_already_exists.format(key_path=key_path), prefix=False)
        raise typer.Exit(1)

    default_comment = (
        f"{active_prefix}-{date.today().isoformat()}"
        if active_prefix
        else f"devops-cli-{date.today().isoformat()}"
    )
    generate_ed25519_key(key_path, comment=comment or default_comment)
    print_success(MESSAGES.messages.generated_key.format(key_path=key_path), prefix=False)
    pub_path = key_path.with_name(f"{key_path.name}.pub")
    print_success(MESSAGES.messages.public_key_path.format(pub_path=pub_path), prefix=False)
    print_info(MESSAGES.ssh.register_tip, prefix=False)


# =============================================================================
# Command: devops ssh register
# =============================================================================


@app.command()
def register(
    key_file: Annotated[
        Path | None, typer.Option("--key-file", "-k", help=HELP.ssh.key_file)
    ] = None,
    title: Annotated[str | None, typer.Option("--title", help=HELP.options.title)] = None,
) -> None:
    from devops_cli.config.settings import get_github_token, load_settings
    from devops_cli.crypto.ssh_keys import find_newest_key, get_ssh_key_prefix
    from devops_cli.dry_run import is_dry_run
    from devops_cli.github.ssh import SSHRegistrationError, register_key_on_github

    if is_dry_run():
        render_dry_run_result(
            command="devops ssh register",
            action="register_ssh_key_on_github",
            details={"key_file": str(key_file) if key_file else None, "title": title},
        )
        return

    settings = load_settings()
    token = get_github_token(settings)

    if key_file is None:
        key_file = find_newest_key(settings.ssh.key_dir.expanduser())
        if key_file is None:
            print_error(MESSAGES.messages.no_ssh_key_found, prefix=False)
            raise typer.Exit(1)
    else:
        key_file = key_file.expanduser()

    pub_path = key_file.with_name(f"{key_file.name}.pub")
    if not pub_path.exists():
        print_error(MESSAGES.messages.public_key_not_found.format(pub_path=pub_path), prefix=False)
        raise typer.Exit(1)

    pub_key = pub_path.read_text(encoding="utf-8").strip()
    active_prefix = settings.ssh.key_prefix or get_ssh_key_prefix()
    key_title = title or f"{key_file.stem if key_file else active_prefix}-{_date_suffix()}"

    try:
        register_key_on_github(pub_key, key_title, token=token)
    except SSHRegistrationError as exc:
        from devops_cli.ai.review.sanitization import _mask_secrets_in_content

        masked_err = _mask_secrets_in_content(str(exc))
        print_error(MESSAGES.messages.failed_to_register_key.format(error=masked_err), prefix=False)
        print_warning(MESSAGES.messages.gh_auth_refresh_tip, prefix=False)
        raise typer.Exit(1)

    _configure_git_signing(key_file)
    print_success(f"Registered [bold]{key_title}[/bold] on GitHub (auth + signing).")
    print_success("Configured [dim]gpg.format=ssh[/dim] and [dim]commit.gpgsign=true[/dim].")


# =============================================================================
# Command: devops ssh rotate
# =============================================================================


@app.command()
def rotate(
    key_dir: Annotated[Path | None, typer.Option("--key-dir", help=HELP.ssh.key_dir)] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help=HELP.ssh.force_rotate)] = False,
    prefix: Annotated[
        str | None,
        typer.Option(
            "--prefix",
            "-p",
            help="Optional prefix for the SSH key name (defaults to config setting, devcontainer name, or basename pwd).",
        ),
    ] = None,
) -> None:
    """Rotate keys older than rotation_days (default 90).

    Generates, registers, and reports the old key.
    """
    from devops_cli.config.settings import get_github_token, load_settings
    from devops_cli.crypto.ssh_keys import (
        find_newest_key,
        generate_ed25519_key,
        get_key_age_days,
        get_ssh_key_prefix,
    )
    from devops_cli.dry_run import is_dry_run
    from devops_cli.github.ssh import SSHRegistrationError, register_key_on_github

    if is_dry_run():
        render_dry_run_result(
            command="devops ssh rotate",
            action="rotate_ssh_keys",
            details={
                "key_dir": str(key_dir) if key_dir else None,
                "force": force,
                "prefix": prefix,
            },
        )
        return

    settings = load_settings()
    target_key_dir = (key_dir or settings.ssh.key_dir).expanduser()

    newest = find_newest_key(target_key_dir)
    if newest is None:
        print_warning(MESSAGES.ssh.no_managed_keys, prefix=False)
        raise typer.Exit(0)

    age = get_key_age_days(newest)
    if age < settings.ssh.rotation_days and not force:
        print_success(
            f"Key is {age} days old (rotation at {settings.ssh.rotation_days}d). "
            "No rotation needed.",
            prefix=False,
        )
        raise typer.Exit(0)

    print_warning(f"Key is {age} days old — rotating...", prefix=False)

    active_prefix = (
        prefix if prefix is not None else (settings.ssh.key_prefix or get_ssh_key_prefix())
    )
    filename = (
        f"{active_prefix}-id_ed25519-{_date_suffix()}"
        if active_prefix
        else f"id_ed25519-{_date_suffix()}"
    )
    new_key_path = target_key_dir / filename
    created_new = False
    if new_key_path.exists():
        print_warning(f"New key already exists: {new_key_path}", prefix=False)
    else:
        default_comment = (
            f"{active_prefix}-{date.today().isoformat()}"
            if active_prefix
            else f"devops-cli-{date.today().isoformat()}"
        )
        generate_ed25519_key(new_key_path, comment=default_comment)
        created_new = True
        print_success(f"Generated: {new_key_path}")

    token = get_github_token(settings)
    pub_key = new_key_path.with_name(f"{new_key_path.name}.pub").read_text(encoding="utf-8").strip()
    try:
        register_key_on_github(
            pub_key, f"{active_prefix or 'devops-cli'}-{_date_suffix()}", token=token
        )
        _configure_git_signing(new_key_path)
        print_success(MESSAGES.ssh.registered_and_configured)
    except SSHRegistrationError as exc:
        if created_new:
            new_key_path.unlink(missing_ok=True)
            new_key_path.with_name(f"{new_key_path.name}.pub").unlink(missing_ok=True)
        print_warning(f"GitHub key registration failed: {exc}", prefix=False)
        print_warning(MESSAGES.ssh.cleaned_unregistered_keys, prefix=False)

    print_info(
        f"\nOld key {newest.name} remains active for {CONST_SSH_GRACE_DAYS} grace days. "
        "Remove manually from GitHub when ready.",
        prefix=False,
    )


# =============================================================================
# Command: devops ssh audit / list
# =============================================================================


@app.command("audit")
@app.command("list")
def list_keys(
    key_dir: Annotated[Path | None, typer.Option("--key-dir", help=HELP.ssh.key_dir)] = None,
) -> None:
    """List all managed SSH keys with their age and rotation status."""
    from devops_cli.config.settings import load_settings
    from devops_cli.crypto.ssh_keys import list_managed_keys_info
    from devops_cli.dry_run import is_dry_run

    if is_dry_run():
        render_dry_run_result(
            command="devops ssh list",
            action="audit_ssh_keys",
            details={},
        )
        return

    settings = load_settings()
    target_key_dir = (key_dir or settings.ssh.key_dir).expanduser()
    keys = list_managed_keys_info(target_key_dir)

    if not keys:
        print_warning(MESSAGES.ssh.no_managed_keys_pattern, prefix=False)
        raise typer.Exit(0)

    rotation_days = settings.ssh.rotation_days
    rows: list[list[str]] = []

    for key in keys:
        age = key.age_days if key.age_days is not None else 0
        if age > rotation_days + CONST_SSH_GRACE_DAYS:
            status_text = format_status_badge("overdue for deletion")
        elif age > rotation_days:
            status_text = format_status_badge("grace period", warn_color="yellow")
        elif age > rotation_days - 7:
            status_text = format_status_badge("rotation soon", warn_color="yellow")
        else:
            status_text = format_status_badge("active")
        rows.append([key.path.name, str(age), status_text])

    print_table(
        title="Managed SSH Keys",
        columns=[("Key", "cyan"), ("Age (days)", "right"), "Status"],
        rows=rows,
    )


# =============================================================================
# Command: devops ssh status
# =============================================================================


@app.command()
def status(
    key_dir: Annotated[Path | None, typer.Option("--key-dir", help=HELP.ssh.key_dir)] = None,
) -> None:
    """Show the active SSH key and days until rotation."""
    from devops_cli.config.settings import load_settings
    from devops_cli.crypto.ssh_keys import find_newest_key, get_key_age_days
    from devops_cli.dry_run import is_dry_run

    if is_dry_run():
        render_dry_run_result(
            command="devops ssh status",
            action="get_ssh_key_status",
            details={},
        )
        return

    settings = load_settings()
    target_key_dir = (key_dir or settings.ssh.key_dir).expanduser()
    rotation_days = settings.ssh.rotation_days

    newest = find_newest_key(target_key_dir)
    if newest is None:
        print_warning(MESSAGES.ssh.no_managed_keys, prefix=False)
        raise typer.Exit(0)

    age = get_key_age_days(newest)
    days_left = rotation_days - age

    print_info(f"Active key:  [bold cyan]{newest.name}[/bold cyan]", prefix=False)
    print_info(f"Age:         [bold]{age}[/bold] days", prefix=False)
    if days_left > 7:
        print_success(f"Rotation:    {days_left} days remaining", prefix=False)
    elif days_left > 0:
        print_warning(f"Rotation:    {days_left} days remaining", prefix=False)
    else:
        print_error(
            f"Rotation:    overdue by {-days_left} days — run 'devops ssh rotate'", prefix=False
        )
