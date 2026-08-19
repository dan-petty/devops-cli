"""Devcontainer management commands."""

from __future__ import annotations

import json
import os
import re
import shutil
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
from devops_cli.config.metadata import get_project_python_version
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
    return get_project_python_version()


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
    project_name: Annotated[str | None, typer.Option("--name", "-n", help="Project name")] = None,
    python_version: Annotated[
        str, typer.Option("--python", help="Python version for base template")
    ] = _project_python_version(),
    image: Annotated[str | None, typer.Option("--image", "-i", help="Base container image")] = None,
    published: Annotated[
        bool,
        typer.Option(
            "--published",
            "-p",
            help="Use published GHCR image (ghcr.io/dan-petty/devops-cli/devcontainer:latest)",
        ),
    ] = False,
) -> None:
    """Scaffold .devcontainer/ in a repository using standard or published template."""
    dc_dir = repo_path / CONST_DEVCONTAINER_DIR_NAME
    dc_file = dc_dir / CONST_DEVCONTAINER_JSON_NAME

    if dc_file.exists():
        rprint(f"[yellow]devcontainer.json already exists: {dc_file}[/yellow]")
        raise typer.Exit(1)

    raw_name = project_name or repo_path.resolve().name
    # Strip characters unsafe in container names / shell contexts
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw_name)
    dc_dir.mkdir(parents=True, exist_ok=True)

    selected_image: str | None = image
    if published and not selected_image:
        selected_image = "ghcr.io/dan-petty/devops-cli/devcontainer:latest"

    env = _jinja_env()

    dc_file.write_text(
        env.get_template("devcontainer.json.j2").render(
            project_name=name, python_version=python_version, image=selected_image
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


def _strip_json_comments(text: str) -> str:
    """Strip single-line and multi-line comments from JSON text (JSONC support)."""
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text


def _validate_manifest_content(data: object, base_dir: Path) -> list[str]:
    """Validate parsed DevContainer manifest dictionary structure and referenced paths."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Manifest root must be a JSON object."]

    name = data.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        errors.append("Missing or empty required field: 'name'")

    has_image = "image" in data and isinstance(data["image"], str) and bool(data["image"].strip())
    has_build = "build" in data and (
        isinstance(data["build"], dict) or isinstance(data["build"], str)
    )
    has_dockerfile = "dockerFile" in data and isinstance(data["dockerFile"], str)

    if not (has_image or has_build or has_dockerfile):
        errors.append(
            "Manifest must specify a base container via 'image', 'build', or 'dockerFile'."
        )

    if has_build and isinstance(data["build"], dict):
        build_dict = data["build"]
        dockerfile = build_dict.get("dockerfile") or build_dict.get("dockerFile")
        if dockerfile and isinstance(dockerfile, str):
            dockerfile_path = (base_dir / dockerfile).resolve()
            if not dockerfile_path.exists():
                errors.append(f"Referenced build dockerfile does not exist: {dockerfile}")

    if has_dockerfile and isinstance(data["dockerFile"], str):
        df_path = (base_dir / data["dockerFile"]).resolve()
        if not df_path.exists():
            errors.append(f"Referenced dockerFile does not exist: {data['dockerFile']}")

    if "features" in data and not isinstance(data["features"], dict):
        errors.append("'features' must be a JSON object (mapping feature IDs to options).")

    if "mounts" in data and not isinstance(data["mounts"], list):
        errors.append("'mounts' must be a list of volume or bind mount definitions.")

    if "forwardPorts" in data and not isinstance(data["forwardPorts"], list):
        errors.append("'forwardPorts' must be a list of port numbers.")

    if "customizations" in data and not isinstance(data["customizations"], dict):
        errors.append("'customizations' must be a JSON object.")

    return errors


@app.command("validate")
def validate(
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace", "-w", help="Path to workspace directory containing .devcontainer"
        ),
    ] = Path("."),
    config_path: Annotated[
        Path | None, typer.Option("--config", "-c", help="Direct path to devcontainer.json")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Simulate DevContainer manifest validation")
    ] = False,
) -> None:
    """Validate .devcontainer/devcontainer.json manifest syntax and configuration schema."""
    ws = workspace.resolve()
    if config_path:
        dc_file = config_path.resolve()
    else:
        candidates = [
            ws / CONST_DEVCONTAINER_JSON_PATH,
            ws / CONST_DEVCONTAINER_JSON_NAME,
        ]
        dc_file = next((c for c in candidates if c.exists()), candidates[0])

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops devcontainer validate",
            action="validate_devcontainer_manifest",
            details={
                "workspace": str(ws),
                "manifest_path": str(dc_file),
                "exists": dc_file.exists(),
            },
        )
        return

    if not dc_file.exists():
        rprint(f"[red]DevContainer manifest not found: {dc_file}[/red]")
        raise typer.Exit(1)

    try:
        raw_text = dc_file.read_text(encoding="utf-8")
        clean_text = _strip_json_comments(raw_text)
        data = json.loads(clean_text)
    except Exception as exc:
        rprint(f"[red]Failed to parse DevContainer manifest JSON in {dc_file}: {exc}[/red]")
        raise typer.Exit(1)

    errors = _validate_manifest_content(data, dc_file.parent)
    if errors:
        rprint(f"[bold red]✗ DevContainer manifest validation failed for {dc_file}:[/bold red]")
        for err in errors:
            rprint(f"  [red]• {err}[/red]")
        raise typer.Exit(1)

    name = data.get("name", "unknown")
    base = data.get("image") or (
        data.get("build") if isinstance(data.get("build"), str) else "Dockerfile build"
    )
    n_features = len(data.get("features", {})) if isinstance(data.get("features"), dict) else 0
    n_mounts = len(data.get("mounts", [])) if isinstance(data.get("mounts"), list) else 0
    n_ports = len(data.get("forwardPorts", [])) if isinstance(data.get("forwardPorts"), list) else 0

    rprint(f"[bold green]✓ DevContainer manifest is valid:[/bold green] [cyan]{dc_file}[/cyan]")
    rprint(f"  [dim]Name:[/dim] [bold]{name}[/bold]")
    rprint(f"  [dim]Base:[/dim] {base}")
    rprint(f"  [dim]Features:[/dim] {n_features} configured")
    rprint(f"  [dim]Mounts:[/dim] {n_mounts} configured")
    rprint(f"  [dim]Forward Ports:[/dim] {n_ports} configured")


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

    # Update ~/.zshrc
    zshrc = Path.home() / ".zshrc"
    zshrc_content = zshrc.read_text(encoding="utf-8") if zshrc.exists() else ""

    zshrc_additions: list[str] = []
    if f'export PATH="{workspace_dir}/.venv/bin' not in zshrc_content:
        zshrc_additions.append(
            "\n# ── Environment & PATH ───────────────────────────────────────────────────────\n"
            f'export PATH="{workspace_dir}/.venv/bin:$HOME/.local/bin:$PATH"\n'
            "export UV_MALWARE_CHECK=1\n"
        )
        actions.append("Added PATH variables to ~/.zshrc")

    if "_DEVOPS_COMPLETE" not in zshrc_content:
        zshrc_additions.append(
            "\n# ── devops-cli shell completion & alias ──────────────────────────────────────\n"
            "if command -v devops &>/dev/null; then\n"
            '  eval "$(_DEVOPS_COMPLETE=source_zsh devops 2>/dev/null || true)"\n'
            "  alias dot='devops'\n"
            "fi\n"
        )
        actions.append("Added shell completion and dot alias to ~/.zshrc")

    if zshrc_additions and not dry_run:
        with zshrc.open("a", encoding="utf-8") as file_handle:
            for addition in zshrc_additions:
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
    if not vscode_mcp.exists() and (workspace_dir / "pyproject.toml").exists():
        vscode_dir = workspace_dir / ".vscode"
        if not dry_run:
            vscode_dir.mkdir(parents=True, exist_ok=True)
            env = _jinja_env()
            raw_name = workspace_dir.name
            name = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw_name)
            vscode_mcp.write_text(
                env.get_template("mcp.json.j2").render(project_name=name),
                encoding="utf-8",
            )
        actions.append(f"Scaffolded MCP configuration at {vscode_mcp}")

    if vscode_mcp.exists():
        for mcp_dest in (
            Path.home() / ".gemini" / "config" / "mcp_config.json",
            Path.home() / ".gemini" / "antigravity-ide" / "mcp_config.json",
        ):
            if not dry_run:
                mcp_dest.parent.mkdir(parents=True, exist_ok=True)
                raw_text = vscode_mcp.read_text(encoding="utf-8")
                synced_text = raw_text.replace("${workspaceFolder}", str(workspace_dir)).replace(
                    "${env:HOME}", str(Path.home())
                )
                mcp_dest.write_text(synced_text, encoding="utf-8")
            actions.append(f"Synced MCP configuration to {mcp_dest}")

        agents_dir = workspace_dir / ".agents"
        if agents_dir.exists():
            agents_mcp_dest = agents_dir / "mcp_config.json"
            if not dry_run:
                raw_text = vscode_mcp.read_text(encoding="utf-8")
                synced_text = raw_text.replace("${workspaceFolder}", str(workspace_dir)).replace(
                    "${env:HOME}", str(Path.home())
                )
                agents_mcp_dest.write_text(synced_text, encoding="utf-8")
            actions.append(f"Synced MCP configuration to {agents_mcp_dest}")

    # 5. Minikube autostart & K8s deploy status evaluation
    auto_start = os.getenv("DEVOPS_MINIKUBE_AUTOSTART", "true").lower() in ("true", "1")
    minikube_healthy = False
    if auto_start and shutil.which("minikube"):
        docker_available = False
        if shutil.which("docker"):
            doc_res = run_subprocess(["docker", "info"], check=False, quiet=True)
            docker_available = doc_res.returncode == 0

        if not docker_available:
            actions.append("Warning: Docker daemon is not running; skipping Minikube start")
        else:
            res = run_subprocess(
                ["minikube", "status", "--format", "{{.Host}}"],
                check=False,
                quiet=True,
            )
            is_running = res.returncode == 0 and "Running" in str(res.stdout)
            if not is_running:
                has_gpu = shutil.which("nvidia-smi") is not None
                started = False
                if has_gpu:
                    if not dry_run:
                        start_res = run_subprocess(
                            ["minikube", "start", "--driver=docker", "--gpus=all"],
                            check=False,
                            quiet=True,
                            timeout=300.0,
                        )
                        started = start_res.returncode == 0
                    else:
                        started = True
                    if started:
                        actions.append("Started Minikube cluster (--driver=docker --gpus=all)")

                if not started:
                    if not dry_run:
                        start_res = run_subprocess(
                            ["minikube", "start", "--driver=docker"],
                            check=False,
                            quiet=True,
                            timeout=300.0,
                        )
                        started = start_res.returncode == 0
                    else:
                        started = True
                    if started:
                        actions.append("Started Minikube cluster (--driver=docker)")
                    else:
                        actions.append("Warning: Failed to start Minikube cluster")

                minikube_healthy = started
                if started and not dry_run:
                    run_subprocess(["minikube", "update-context"], check=False, quiet=True)
            else:
                if not dry_run:
                    run_subprocess(["minikube", "update-context"], check=False, quiet=True)
                actions.append("Minikube cluster is already running")
                minikube_healthy = True

    auto_deploy = os.getenv("DEVOPS_K8S_AUTO_DEPLOY", "false").lower() in ("true", "1")
    if auto_deploy and shutil.which("minikube") and shutil.which("kubectl"):
        if minikube_healthy or dry_run:
            stack = os.getenv("DEVOPS_K8S_STACK", "infra")
            k8s_dir = workspace_dir / "k8s"
            if k8s_dir.exists() and (k8s_dir / "kustomization.yaml").exists():
                if not dry_run:
                    from devops_cli.commands.k8s import deploy_stack as k8s_deploy_stack

                    try:
                        k8s_deploy_stack(k8s_dir=k8s_dir, stack=stack)
                        actions.append(f"Auto-deployed Kubernetes stack ({stack})")
                    except Exception as exc:
                        actions.append(f"Auto-deploy failed for stack ({stack}): {exc}")
                else:
                    actions.append(f"Auto-deployed Kubernetes stack ({stack})")
        else:
            actions.append("Skipping Kubernetes auto-deploy: Minikube is not running")

    # 6. Pre-commit Git hook installation
    if (workspace_dir / ".pre-commit-config.yaml").exists() and (workspace_dir / ".git").exists():
        if not dry_run:
            res = run_subprocess(
                ["uv", "run", "pre-commit", "install"],
                cwd=workspace_dir,
                check=False,
                quiet=True,
            )
            if res.returncode == 0:
                actions.append("Installed pre-commit Git hooks (uv run pre-commit install)")
            else:
                actions.append("Warning: Failed to install pre-commit Git hooks")
        else:
            actions.append("Installed pre-commit Git hooks (uv run pre-commit install)")

    # 7. Git daemon background service
    auto_git_daemon = os.getenv("DEVOPS_GIT_DAEMON_AUTOSTART", "true").lower() in ("true", "1")
    if auto_git_daemon:
        actions.extend(_start_git_daemon(workspace_dir, dry_run=dry_run))

    return actions


def _git_daemon_pid_file() -> Path:
    """Return platform-safe path to git daemon pid file."""
    import tempfile

    return Path(tempfile.gettempdir()) / "git-daemon.pid"


def _is_git_daemon_running() -> bool:
    """Check if git daemon is running via pidfile or port 9418 socket check."""
    pid_file = _git_daemon_pid_file()
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            pass
    import socket

    try:
        with socket.create_connection(("127.0.0.1", 9418), timeout=0.2):
            return True
    except OSError:
        pass
    return False


def _start_git_daemon(workspace_dir: Path, *, dry_run: bool = False) -> list[str]:
    """Ensure background git daemon is running serving workspace repositories."""
    actions: list[str] = []
    if _is_git_daemon_running():
        actions.append("Git daemon is already running on port 9418")
        return actions

    if not shutil.which("git"):
        return actions

    raw_paths = os.getenv("DEVOPS_GIT_DAEMON_PATHS")
    if raw_paths:
        export_dirs = [Path(p.strip()) for p in raw_paths.split(",") if p.strip()]
    else:
        export_dirs = [workspace_dir / "k8s", workspace_dir / "repos"]

    for d in export_dirs:
        if not dry_run:
            d.mkdir(parents=True, exist_ok=True)

    pid_file = _git_daemon_pid_file()
    cmd = [
        "git",
        "daemon",
        "--reuseaddr",
        "--detach",
        f"--pid-file={pid_file}",
        "--export-all",
        *[str(d) for d in export_dirs],
    ]

    paths_str = ", ".join(str(d) for d in export_dirs)
    if not dry_run:
        res = run_subprocess(cmd, check=False, quiet=True)
        if res.returncode == 0:
            actions.append(f"Started background Git daemon on port 9418 ({paths_str})")
        else:
            actions.append(f"Failed to start Git daemon (exit {res.returncode}): {res.stderr}")
    else:
        actions.append(f"Started background Git daemon on port 9418 ({paths_str})")

    return actions


@app.command("post-create")
def post_create(
    workspace: Annotated[
        Path, typer.Option("--workspace", "-w", help="Path to workspace directory")
    ] = Path("."),
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Simulate execution without modifying files")
    ] = False,
) -> None:
    """Execute DevContainer post-create setup tasks (history, shell completions, config prep)."""
    ws = workspace.resolve()
    if dry_run or is_dry_run():
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
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Simulate execution without modifying files")
    ] = False,
) -> None:
    """Execute DevContainer post-start tasks (SSH keys, git defaults, kubeconfig, MCP sync)."""
    ws = workspace.resolve()
    if dry_run or is_dry_run():
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
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Simulate execution without modifying files")
    ] = False,
) -> None:
    """Run specified DevContainer lifecycle hook tasks natively in Python."""
    ws = workspace.resolve()
    do_create = post_create_flag or all_flag
    do_start = post_start_flag or all_flag
    if not (do_create or do_start):
        do_create = True
        do_start = True

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops devcontainer run-lifecycle",
            action="run_lifecycle",
            details={"workspace": str(ws), "post_create": do_create, "post_start": do_start},
        )
        return

    if do_create:
        post_create(workspace=ws, dry_run=False)
    if do_start:
        post_start(workspace=ws, dry_run=False)
