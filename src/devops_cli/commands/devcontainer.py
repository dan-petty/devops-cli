"""Devcontainer management commands."""

from __future__ import annotations

import json
import os
import re
import shutil
import tomllib
from pathlib import Path
from typing import Annotated

import typer
from jinja2 import Environment, FileSystemLoader, select_autoescape
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.config.constants import (
    CONST_DEVCONTAINER_DIR_NAME,
    CONST_DEVCONTAINER_IMAGE_PREFIX,
    CONST_DEVCONTAINER_JSON_NAME,
    CONST_DEVCONTAINER_JSON_PATH,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer, repo_label
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.git.operations import iter_workspace_repos

app = new_typer(help="Manage devcontainer configurations.", no_args_is_help=True)
console = Console()

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _project_python_version() -> str:
    pyproject = _PROJECT_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return "3.14"
    with pyproject.open("rb") as file_handle:
        data = tomllib.load(file_handle)
    requires_python: str = str(data.get("project", {}).get("requires-python") or "")
    if not requires_python:
        return "3.14"
    match = re.search(r"^>=?\s*([\d.]+)", requires_python)
    if match:
        return match.group(1)
    return requires_python


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


@app.command()
def init(
    repo_path: Annotated[Path, typer.Argument(help="Path to the repository")] = Path("."),
    project_name: Annotated[str | None, typer.Option("--name", "-n")] = None,
    python_version: Annotated[str, typer.Option("--python")] = _project_python_version(),
) -> None:
    """Scaffold .devcontainer/ in a repository using the standard template."""
    dc_dir = repo_path / CONST_DEVCONTAINER_DIR_NAME
    dc_file = dc_dir / CONST_DEVCONTAINER_JSON_NAME

    if dc_file.exists():
        rprint(f"[yellow]devcontainer.json already exists: {dc_file}[/yellow]")
        raise typer.Exit(1)

    raw_name = project_name or repo_path.resolve().name
    # Strip characters unsafe in container names / shell contexts
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw_name)
    dc_dir.mkdir(parents=True, exist_ok=True)

    env = _jinja_env()

    dc_file.write_text(
        env.get_template("devcontainer.json.j2").render(
            project_name=name, python_version=python_version
        ),
        encoding="utf-8",
    )

    rprint(f"[green]Created:[/green] {dc_file}")

    vscode_dir = repo_path / ".vscode"
    mcp_file = vscode_dir / "mcp.json"
    if not mcp_file.exists():
        vscode_dir.mkdir(parents=True, exist_ok=True)
        mcp_file.write_text(
            env.get_template("mcp.json.j2").render(project_name=name),
            encoding="utf-8",
        )
        rprint(f"[green]Created:[/green] {mcp_file}")


@app.command()
def update(
    repo_path: Annotated[Path, typer.Argument(help="Path to the repository")] = Path("."),
    python_version: Annotated[str, typer.Option("--python")] = _project_python_version(),
) -> None:
    """Update the Python image version in an existing devcontainer.json."""
    dc_file = repo_path / CONST_DEVCONTAINER_JSON_PATH
    if not dc_file.exists():
        rprint(f"[red]No devcontainer.json found: {dc_file}[/red]")
        raise typer.Exit(1)

    try:
        data = json.loads(dc_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        rprint(f"[red]Invalid JSON in {dc_file}: {exc}[/red]")
        raise typer.Exit(1)
    data["image"] = f"{CONST_DEVCONTAINER_IMAGE_PREFIX}{python_version}"
    dc_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    rprint(f"[green]Updated image → python:{python_version}[/green]")


@app.command("list")
def list_devcontainers(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
) -> None:
    """List repos with their devcontainer status."""
    if is_dry_run():
        render_dry_run_result(
            command="devops devcontainer list",
            action="list_devcontainers",
            details={"repos": []},
        )
        return

    settings = load_settings()
    root = base_dir or settings.repos.base_dir

    if not root.exists():
        rprint(f"[yellow]Repos directory not found: {root}[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Devcontainer Status")
    table.add_column("Repository", style="cyan")
    table.add_column(CONST_DEVCONTAINER_JSON_NAME)

    for repo_dir in iter_workspace_repos(root):
        dc_ok = (repo_dir / CONST_DEVCONTAINER_JSON_PATH).exists()
        table.add_row(
            repo_label(repo_dir),
            "[green]✓ configured[/green]" if dc_ok else "[yellow]✗ missing[/yellow]",
        )

    console.print(table)


def _run_post_create_lifecycle(workspace_dir: Path, *, dry_run: bool = False) -> list[str]:
    """Execute DevContainer post-create setup tasks in pure Python."""
    actions: list[str] = []

    # 1. Persistent bash history
    hist_file = Path.home() / ".bash_history"
    if not dry_run:
        hist_file.touch(mode=0o600, exist_ok=True)
    actions.append(f"Configured persistent bash history at {hist_file}")

    # Update ~/.bashrc
    bashrc = Path.home() / ".bashrc"
    bashrc_content = bashrc.read_text(encoding="utf-8") if bashrc.exists() else ""

    bashrc_additions: list[str] = []
    if "HISTFILE=~/.bash_history" not in bashrc_content:
        bashrc_additions.append(
            "\n# ── Persistent bash history ──────────────────────────────────────────────────\n"
            "export HISTFILE=~/.bash_history\n"
            "export HISTSIZE=10000\n"
            "export HISTFILESIZE=20000\n"
            "shopt -s histappend\n"
            'PROMPT_COMMAND="history -a${PROMPT_COMMAND:+; $PROMPT_COMMAND}"\n'
            f'export PATH="{workspace_dir}/.venv/bin:$HOME/.local/bin:$PATH"\n'
            "export UV_MALWARE_CHECK=1\n"
        )
        actions.append("Added persistent history and PATH variables to ~/.bashrc")

    if "_DEVOPS_COMPLETE" not in bashrc_content:
        bashrc_additions.append(
            "\n# ── devops-cli shell completion & alias ──────────────────────────────────────\n"
            "if command -v devops &>/dev/null; then\n"
            '  eval "$(_DEVOPS_COMPLETE=source_bash devops 2>/dev/null || true)"\n'
            "  alias dot='devops'\n"
            "fi\n"
        )
        actions.append("Added shell completion and dot alias to ~/.bashrc")

    if bashrc_additions and not dry_run:
        with bashrc.open("a", encoding="utf-8") as file_handle:
            for addition in bashrc_additions:
                file_handle.write(addition)

    # 2. Config directory prep
    gemini_cfg = Path.home() / ".gemini" / "config"
    if not dry_run:
        gemini_cfg.mkdir(parents=True, exist_ok=True)
    actions.append(f"Ensured config directory exists at {gemini_cfg}")

    devops_cfg = os.getenv("DEVOPS_CLI_CONFIG")
    if devops_cfg and not Path(devops_cfg).exists():
        actions.append(f"Warning: Specified DEVOPS_CLI_CONFIG file does not exist: {devops_cfg}")

    return actions


def _run_post_start_lifecycle(workspace_dir: Path, *, dry_run: bool = False) -> list[str]:
    """Execute DevContainer post-start lifecycle tasks in pure Python."""
    actions: list[str] = []

    # 1. Git defaults
    if not dry_run:
        run_subprocess(
            ["git", "config", "--global", "push.autoSetupRemote", "true"],
            check=False,
            quiet=True,
        )
    actions.append("Configured git push.autoSetupRemote=true")

    # 2. SSH key permissions & commit signing
    ssh_dir = Path.home() / ".ssh"
    if ssh_dir.exists():
        if not dry_run:
            ssh_dir.chmod(0o700)
            for item in ssh_dir.iterdir():
                if item.is_file():
                    if item.name.startswith("id_") and not item.name.endswith(".pub"):
                        item.chmod(0o600)
                    elif item.name.endswith(".pub"):
                        item.chmod(0o644)
        actions.append(f"Hardened SSH key permissions in {ssh_dir}")

        keys = sorted(
            [p for p in ssh_dir.glob("id_*") if not p.name.endswith(".pub")],
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )
        if keys:
            newest = keys[0]
            if not dry_run:
                run_subprocess(
                    ["git", "config", "--global", "gpg.format", "ssh"],
                    check=False,
                    quiet=True,
                )
                run_subprocess(
                    ["git", "config", "--global", "user.signingkey", str(newest)],
                    check=False,
                    quiet=True,
                )
            actions.append(f"Configured Git SSH commit signing with key {newest.name}")

    # 3. Kubeconfig initialization
    kube_dir = Path.home() / ".kube"
    kube_file = kube_dir / "config"
    if not dry_run:
        kube_dir.mkdir(parents=True, exist_ok=True)
        if not kube_file.exists():
            kube_skeleton = (
                "apiVersion: v1\n"
                "kind: Config\n"
                "clusters: []\n"
                "contexts: []\n"
                'current-context: ""\n'
                "preferences: {}\n"
                "users: []\n"
            )
            kube_file.write_text(kube_skeleton, encoding="utf-8")
            kube_file.chmod(0o600)
    actions.append(f"Initialized kubeconfig file at {kube_file}")

    # 4. MCP configuration sync
    vscode_mcp = workspace_dir / ".vscode" / "mcp.json"
    if vscode_mcp.exists():
        mcp_dest = Path.home() / ".gemini" / "config" / "mcp_config.json"
        if not dry_run:
            mcp_dest.parent.mkdir(parents=True, exist_ok=True)
            raw_text = vscode_mcp.read_text(encoding="utf-8")
            synced_text = raw_text.replace("${workspaceFolder}", str(workspace_dir))
            mcp_dest.write_text(synced_text, encoding="utf-8")
        actions.append(f"Synced MCP configuration to {mcp_dest}")

    # 5. Minikube autostart & K8s deploy status evaluation
    auto_start = os.getenv("DEVOPS_MINIKUBE_AUTOSTART", "true").lower() in ("true", "1")
    if auto_start and shutil.which("minikube"):
        actions.append("Evaluated Minikube autostart status")

    return actions


@app.command("post-create")
def post_create(
    workspace: Annotated[
        Path, typer.Option("--workspace", "-w", help="Path to workspace directory")
    ] = Path("."),
) -> None:
    """Execute DevContainer post-create setup tasks (history, shell completions, config prep)."""
    ws = workspace.resolve()
    if is_dry_run():
        render_dry_run_result(
            command="devops devcontainer post-create",
            action="post_create_lifecycle",
            details={"workspace": str(ws)},
        )
        return

    rprint(f"[cyan]Running DevContainer post-create setup for {ws}...[/cyan]")
    actions = _run_post_create_lifecycle(ws, dry_run=False)
    for action in actions:
        rprint(f"  [green]✓[/green] {action}")
    rprint("[bold green]✓ DevContainer post-create setup ready.[/bold green]")


@app.command("post-start")
def post_start(
    workspace: Annotated[
        Path, typer.Option("--workspace", "-w", help="Path to workspace directory")
    ] = Path("."),
) -> None:
    """Execute DevContainer post-start tasks (SSH keys, git defaults, kubeconfig, MCP sync)."""
    ws = workspace.resolve()
    if is_dry_run():
        render_dry_run_result(
            command="devops devcontainer post-start",
            action="post_start_lifecycle",
            details={"workspace": str(ws)},
        )
        return

    rprint(f"[cyan]Running DevContainer post-start lifecycle for {ws}...[/cyan]")
    actions = _run_post_start_lifecycle(ws, dry_run=False)
    for action in actions:
        rprint(f"  [green]✓[/green] {action}")
    rprint("[bold green]✓ DevContainer post-start lifecycle complete.[/bold green]")


@app.command("run-lifecycle")
def run_lifecycle(
    workspace: Annotated[
        Path, typer.Option("--workspace", "-w", help="Path to workspace directory")
    ] = Path("."),
    post_create_flag: Annotated[
        bool, typer.Option("--post-create", help="Execute post-create setup tasks")
    ] = False,
    post_start_flag: Annotated[
        bool, typer.Option("--post-start", help="Execute post-start lifecycle tasks")
    ] = False,
    all_flag: Annotated[
        bool, typer.Option("--all", "-a", help="Execute all DevContainer lifecycle tasks")
    ] = False,
) -> None:
    """Run specified DevContainer lifecycle hook tasks natively in Python."""
    ws = workspace.resolve()
    do_create = post_create_flag or all_flag
    do_start = post_start_flag or all_flag
    if not (do_create or do_start):
        do_create = True
        do_start = True

    if is_dry_run():
        render_dry_run_result(
            command="devops devcontainer run-lifecycle",
            action="run_lifecycle",
            details={"workspace": str(ws), "post_create": do_create, "post_start": do_start},
        )
        return

    if do_create:
        post_create(workspace=ws)
    if do_start:
        post_start(workspace=ws)

