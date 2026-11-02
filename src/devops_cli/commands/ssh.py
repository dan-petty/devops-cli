"""SSH key management commands."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.constants import CONST_SSH_GRACE_DAYS
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_ssh_keys_table,
    print,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from devops_cli.security.sanitizer import mask_secrets

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
    """Point git's SSH commit signing at `key_path` and say so."""
    from devops_cli.crypto.ssh_keys import configure_git_signing

    configure_git_signing(key_path)
    print_success(MESSAGES.ssh.configured_signing, prefix=False)


# =============================================================================
# Command: devops ssh generate
# =============================================================================


@app.command()
@dry_run_class("no-external-request")
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Generate a new Ed25519 SSH key with prefix and YYYYMMDD date suffix."""
    from devops_cli.config.settings import load_settings
    from devops_cli.crypto.ssh_keys import (
        generate_ed25519_key,
        get_ssh_key_prefix,
    )

    settings = load_settings()
    target_key_dir = (key_dir or settings.ssh.key_dir).expanduser()
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

    if dry_run or is_dry_run():
        print_info(MESSAGES.ssh.generate_dry_run.format(key_path=key_path), prefix=False)
        return

    target_key_dir.mkdir(parents=True, exist_ok=True)
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


def _key_title(title: str | None, active_prefix: str, key_file: Path) -> str:
    """The title of the key on GitHub: `--title`, else the key name with the project prefix."""
    from devops_cli.crypto.ssh_keys import parse_key_prefix

    if title:
        return title
    if active_prefix and parse_key_prefix(key_file) is None:
        return f"{active_prefix}-{key_file.stem}"
    return key_file.stem


def _plan_register(
    key_file: Path | None, title: str | None, active_prefix: str, key_dir: Path
) -> None:
    """Print the requests of `ssh register`, and make none. The key is the one that the run
    would register: `--key-file`, else the newest managed key of the prefix, found in the key
    directory. When there is none, the key and its title are placeholders."""
    from devops_cli.crypto.ssh_keys import find_newest_key
    from devops_cli.github.ssh_plans import plan_register

    key_path = key_file.expanduser() if key_file else find_newest_key(key_dir, prefix=active_prefix)
    if key_path is None:
        plan = plan_register("<newest managed key>", title or "<key name>")
    else:
        plan = plan_register(key_path, _key_title(title, active_prefix, key_path))
    render_request_plan(
        MESSAGES.ssh.register_dry_run_heading, plan, [MESSAGES.ssh.key_placeholder_note]
    )


@app.command()
@dry_run_class("request-plan")
def register(
    key_file: Annotated[
        Path | None, typer.Option("--key-file", "-k", help=HELP.ssh.key_file)
    ] = None,
    title: Annotated[str | None, typer.Option("--title", help=HELP.options.title)] = None,
    prefix: Annotated[
        str | None,
        typer.Option(
            "--prefix",
            "-p",
            help=HELP.ssh.prefix,
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    from devops_cli.config.settings import load_settings
    from devops_cli.crypto.ssh_keys import find_newest_key, get_ssh_key_prefix
    from devops_cli.github.ssh import SSHRegistrationError, register_key_on_github

    settings = load_settings()
    active_prefix = (
        prefix if prefix is not None else (settings.ssh.key_prefix or get_ssh_key_prefix())
    )

    if dry_run or is_dry_run():
        _plan_register(key_file, title, active_prefix, settings.ssh.key_dir.expanduser())
        return

    if key_file is None:
        key_dir = settings.ssh.key_dir.expanduser()
        key_file = find_newest_key(key_dir, prefix=active_prefix)
        if key_file is None:
            print_error(
                MESSAGES.ssh.no_project_key.format(prefix=active_prefix, key_dir=key_dir),
                prefix=False,
            )
            raise typer.Exit(1)
    else:
        key_file = key_file.expanduser()

    pub_path = key_file.with_name(f"{key_file.name}.pub")
    if not pub_path.exists():
        print_error(MESSAGES.messages.public_key_not_found.format(pub_path=pub_path), prefix=False)
        raise typer.Exit(1)

    pub_key = pub_path.read_text(encoding="utf-8").strip()
    key_title = _key_title(title, active_prefix, key_file)

    try:
        register_key_on_github(pub_key, key_title)
    except SSHRegistrationError as exc:
        from devops_cli.security.sanitizer import mask_secrets

        masked_err = mask_secrets(str(exc))
        print_error(MESSAGES.messages.failed_to_register_key.format(error=masked_err), prefix=False)
        raise typer.Exit(1) from exc

    _configure_git_signing(key_file)
    print_success(f"Registered [bold]{key_title}[/bold] on GitHub (auth + signing).")
    print_success("Configured [dim]gpg.format=ssh[/dim] and [dim]commit.gpgsign=true[/dim].")


# =============================================================================
# Command: devops ssh rotate
# =============================================================================


def _rotated_key_path(key_dir: Path, active_prefix: str) -> Path:
    """The path of the key that a rotation today generates."""
    if active_prefix:
        return key_dir / f"{active_prefix}-id_ed25519-{_date_suffix()}"
    return key_dir / f"id_ed25519-{_date_suffix()}"


def _rotated_title(active_prefix: str) -> str:
    """The title on GitHub of the key that a rotation today registers."""
    return f"{active_prefix or 'devops-cli'}-{_date_suffix()}"


@app.command()
@dry_run_class("request-plan")
def rotate(
    key_dir: Annotated[Path | None, typer.Option("--key-dir", help=HELP.ssh.key_dir)] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help=HELP.ssh.force_rotate)] = False,
    prefix: Annotated[
        str | None,
        typer.Option(
            "--prefix",
            "-p",
            help=HELP.ssh.prefix,
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Rotate keys older than rotation_days (default 90).

    Generates, registers, and reports the old key.
    """
    from devops_cli.config.settings import load_settings
    from devops_cli.crypto.ssh_keys import (
        find_newest_key,
        generate_ed25519_key,
        get_key_age_days,
        get_ssh_key_prefix,
    )
    from devops_cli.github.ssh import SSHRegistrationError, register_key_on_github

    settings = load_settings()
    target_key_dir = (key_dir or settings.ssh.key_dir).expanduser()
    active_prefix = (
        prefix if prefix is not None else (settings.ssh.key_prefix or get_ssh_key_prefix())
    )

    if dry_run or is_dry_run():
        from devops_cli.github.ssh_plans import plan_rotate

        render_request_plan(
            MESSAGES.ssh.rotate_dry_run_heading,
            plan_rotate(
                _rotated_key_path(target_key_dir, active_prefix), _rotated_title(active_prefix)
            ),
            [MESSAGES.ssh.rotate_dry_run_note, MESSAGES.ssh.key_placeholder_note],
        )
        return

    newest = find_newest_key(target_key_dir, prefix=active_prefix)
    if newest is None:
        print_warning(
            MESSAGES.ssh.no_project_key.format(prefix=active_prefix, key_dir=target_key_dir),
            prefix=False,
        )
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

    new_key_path = _rotated_key_path(target_key_dir, active_prefix)
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

    pub_key = new_key_path.with_name(f"{new_key_path.name}.pub").read_text(encoding="utf-8").strip()
    try:
        register_key_on_github(pub_key, _rotated_title(active_prefix))
        _configure_git_signing(new_key_path)
        print_success(MESSAGES.ssh.registered_and_configured)
    except SSHRegistrationError as exc:
        if created_new:
            new_key_path.unlink(missing_ok=True)
            new_key_path.with_name(f"{new_key_path.name}.pub").unlink(missing_ok=True)
        safe_err = mask_secrets(str(exc))
        print_warning(
            f"GitHub key registration failed: {safe_err}. Check your GitHub token and network connectivity.",
            prefix=False,
        )
        print_warning(MESSAGES.ssh.cleaned_unregistered_keys, prefix=False)

    print_info(
        MESSAGES.ssh.grace_period_notice.format(name=newest.name, grace_days=CONST_SSH_GRACE_DAYS),
        prefix=False,
    )


# =============================================================================
# Command: devops ssh audit / list
# =============================================================================


@app.command("audit")
@app.command("list")
@dry_run_class("no-external-request")
def list_keys(
    key_dir: Annotated[Path | None, typer.Option("--key-dir", help=HELP.ssh.key_dir)] = None,
    prefix: Annotated[
        str | None,
        typer.Option(
            "--prefix",
            "-p",
            help=HELP.ssh.prefix,
        ),
    ] = None,
    all_projects: Annotated[bool, typer.Option("--all", help=HELP.ssh.list_all)] = False,
) -> None:
    """List the managed SSH keys of the project prefix with their age and rotation status."""
    from devops_cli.config.settings import load_settings
    from devops_cli.crypto.ssh_keys import list_managed_keys_info

    if all_projects and prefix is not None:
        raise typer.BadParameter(MESSAGES.ssh.all_with_prefix)

    settings = load_settings()
    from devops_cli.crypto.ssh_keys import get_ssh_key_prefix

    active_prefix = (
        prefix if prefix is not None else (settings.ssh.key_prefix or get_ssh_key_prefix())
    )
    target_key_dir = (key_dir or settings.ssh.key_dir).expanduser()
    keys = list_managed_keys_info(target_key_dir, prefix=None if all_projects else active_prefix)

    if not keys:
        if all_projects:
            print_warning(MESSAGES.ssh.no_managed_keys_pattern, prefix=False)
        else:
            print_warning(
                MESSAGES.ssh.no_project_key.format(prefix=active_prefix, key_dir=target_key_dir),
                prefix=False,
            )
            print_info(MESSAGES.ssh.list_all_tip, prefix=False)
        raise typer.Exit(0)

    rotation_days = settings.ssh.rotation_days
    print(format_ssh_keys_table(keys, rotation_days))


# =============================================================================
# Command: devops ssh status
# =============================================================================


@app.command()
@dry_run_class("no-external-request")
def status(
    key_dir: Annotated[Path | None, typer.Option("--key-dir", help=HELP.ssh.key_dir)] = None,
    prefix: Annotated[
        str | None,
        typer.Option(
            "--prefix",
            "-p",
            help=HELP.ssh.prefix,
        ),
    ] = None,
) -> None:
    """Show the active SSH key and days until rotation."""
    from devops_cli.config.settings import load_settings
    from devops_cli.crypto.ssh_keys import find_newest_key, get_key_age_days, get_ssh_key_prefix

    settings = load_settings()
    target_key_dir = (key_dir or settings.ssh.key_dir).expanduser()
    rotation_days = settings.ssh.rotation_days
    active_prefix = (
        prefix if prefix is not None else (settings.ssh.key_prefix or get_ssh_key_prefix())
    )

    newest = find_newest_key(target_key_dir, prefix=active_prefix)
    if newest is None:
        print_warning(
            MESSAGES.ssh.no_project_key.format(prefix=active_prefix, key_dir=target_key_dir),
            prefix=False,
        )
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
