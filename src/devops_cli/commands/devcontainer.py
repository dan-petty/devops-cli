"""Devcontainer management commands."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Annotated

import typer
from jinja2 import Environment, FileSystemLoader, select_autoescape

from devops_cli.ai.instruction_generator import scaffold_agent_instructions
from devops_cli.config.constants import (
    CONST_AGENTS_MD_FILENAME,
    CONST_DEVCONTAINER_DIR_NAME,
    CONST_DEVCONTAINER_IMAGE_PREFIX,
    CONST_DEVCONTAINER_JSON_NAME,
    CONST_DEVCONTAINER_JSON_PATH,
    CONST_DEVCONTAINER_PUBLISHED_IMAGE,
    CONST_MCP_JSON_NAME,
    CONST_PYPROJECT_FILENAME,
    CONST_ROOT_DIR,
    CONST_SYSTEM_TEMP_DIRS,
    CONST_VSCODE_DIR_NAME,
)
from devops_cli.config.defaults import DEFAULT_CURRENT_PATH
from devops_cli.config.metadata import get_project_python_version
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer, repo_label
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.git.operations import iter_workspace_repos
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    write_json_file,
    write_text_file,
)

logger = logging.getLogger(__name__)

app = new_typer(help=HELP.devcontainer.app, no_args_is_help=True)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


# =============================================================================
# Template & Environment Helpers
# =============================================================================


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


# =============================================================================
# Command: devops devcontainer init
# =============================================================================


@app.command()
def init(
    repo_path: Annotated[
        Path, typer.Argument(help=HELP.devcontainer.repo_path)
    ] = DEFAULT_CURRENT_PATH,
    project_name: Annotated[
        str | None, typer.Option("--name", "-n", help=HELP.devcontainer.project_name)
    ] = None,
    python_version: Annotated[
        str, typer.Option("--python", help=HELP.devcontainer.python_version)
    ] = _project_python_version(),
    image: Annotated[
        str | None,
        typer.Option(
            "--image",
            "-i",
            help=HELP.devcontainer.image,
        ),
    ] = None,
    published: Annotated[
        bool,
        typer.Option(
            "--published",
            "-p",
            help=HELP.devcontainer.published,
        ),
    ] = True,
    home_volume: Annotated[
        str | None,
        typer.Option(
            "--home-volume",
            help=HELP.devcontainer.volume_name,
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help=HELP.devcontainer.overwrite,
        ),
    ] = False,
) -> None:
    """Scaffold .devcontainer/ using the published DevOps CLI devcontainer image."""
    dc_dir = repo_path / CONST_DEVCONTAINER_DIR_NAME
    dc_file = dc_dir / CONST_DEVCONTAINER_JSON_NAME

    if dc_file.exists() and not force:
        print_warning(MESSAGES.devcontainer.already_exists.format(path=dc_file), prefix=False)
        raise typer.Exit(1)

    raw_name = project_name or repo_path.resolve().name
    # Strip characters unsafe in container names / shell contexts
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw_name)
    dc_dir.mkdir(parents=True, exist_ok=True)

    if image:
        selected_image = image
        is_published = selected_image.startswith("ghcr.io/dan-petty/devops-cli/devcontainer")
    else:
        selected_image = CONST_DEVCONTAINER_PUBLISHED_IMAGE
        is_published = True

    resolved_home_vol = home_volume or f"{name}-home"

    env = _jinja_env()

    rendered = env.get_template("devcontainer.json.j2").render(
        project_name=name,
        python_version=python_version,
        image=selected_image,
        published=is_published,
        home_volume=resolved_home_vol,
    )
    write_text_file(dc_file, rendered.strip() + "\n")
    print_success(MESSAGES.devcontainer.created_file.format(path=dc_file))

    vscode_dir = repo_path / CONST_VSCODE_DIR_NAME
    mcp_file = vscode_dir / CONST_MCP_JSON_NAME
    if not mcp_file.exists() or force:
        write_text_file(
            mcp_file,
            env.get_template("mcp.json.j2").render(project_name=name),
        )
        print_success(MESSAGES.devcontainer.created_file.format(path=mcp_file))

    # Scaffold AI agent instruction files (AGENTS.md, CLAUDE.md, .github/copilot-instructions.md)
    agent_files = scaffold_agent_instructions(repo_path, force=force, template=True)
    for af in agent_files:
        print_success(MESSAGES.devcontainer.created_file.format(path=af))


# =============================================================================
# Command: devops devcontainer update
# =============================================================================


@app.command()
def update(
    repo_path: Annotated[
        Path, typer.Argument(help=HELP.devcontainer.repo_path)
    ] = DEFAULT_CURRENT_PATH,
    python_version: Annotated[
        str, typer.Option("--python", help=HELP.devcontainer.python_version)
    ] = _project_python_version(),
) -> None:
    """Update the Python image version in an existing devcontainer.json."""
    dc_file = repo_path / CONST_DEVCONTAINER_JSON_PATH
    if not dc_file.exists():
        print_error(MESSAGES.devcontainer.no_manifest_found.format(path=dc_file))
        raise typer.Exit(1)

    try:
        data = json.loads(dc_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print_error(ERRORS.devcontainer.invalid_json.format(path=dc_file, exc=exc))
        raise typer.Exit(1)
    data["image"] = f"{CONST_DEVCONTAINER_IMAGE_PREFIX}{python_version}"
    write_json_file(dc_file, data)
    print_success(MESSAGES.devcontainer.updated_image.format(version=python_version))


# =============================================================================
# Validation Logic
# =============================================================================


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


# =============================================================================
# Command: devops devcontainer validate
# =============================================================================


@app.command("validate")
def validate(
    workspace: Annotated[
        Path,
        typer.Option("--workspace", "-w", help=HELP.devcontainer.workspace_dir),
    ] = DEFAULT_CURRENT_PATH,
    config_path: Annotated[
        Path | None, typer.Option("--config", "-c", help=HELP.devcontainer.config_file)
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.devcontainer.validate_dry_run)
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
        print_error(ERRORS.devcontainer.manifest_not_found.format(path=dc_file), prefix=False)
        raise typer.Exit(1)

    try:
        raw_text = dc_file.read_text(encoding="utf-8")
        clean_text = _strip_json_comments(raw_text)
        data = json.loads(clean_text)
    except Exception as exc:
        print_error(ERRORS.devcontainer.parse_failed.format(path=dc_file, exc=exc), prefix=False)
        raise typer.Exit(1)

    errors = _validate_manifest_content(data, dc_file.parent)
    if errors:
        print_error(
            MESSAGES.devcontainer.manifest_validation_failed.format(path=dc_file),
            prefix=False,
        )
        for err in errors:
            print_error(f"  • {err}", prefix=False)
        raise typer.Exit(1)

    name = data.get("name", "unknown")
    base = data.get("image") or (
        data.get("build") if isinstance(data.get("build"), str) else "Dockerfile build"
    )
    n_features = len(data.get("features", {})) if isinstance(data.get("features"), dict) else 0
    n_mounts = len(data.get("mounts", [])) if isinstance(data.get("mounts"), list) else 0
    n_ports = len(data.get("forwardPorts", [])) if isinstance(data.get("forwardPorts"), list) else 0

    print_success(f"DevContainer manifest is valid: {dc_file}")
    print_info(f"  Name: {name}", prefix=False)
    print_info(f"  Base: {base}", prefix=False)
    print_info(f"  Features: {n_features} configured", prefix=False)
    print_info(f"  Mounts: {n_mounts} configured", prefix=False)
    print_info(f"  Forward Ports: {n_ports} configured", prefix=False)


# =============================================================================
# Command: devops devcontainer list
# =============================================================================


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
        print_warning(MESSAGES.repos.repos_dir_not_found.format(root=root), prefix=False)
        raise typer.Exit(0)

    rows = [
        [
            repo_label(repo_dir),
            MESSAGES.devcontainer.status_configured
            if (repo_dir / CONST_DEVCONTAINER_JSON_PATH).exists()
            else MESSAGES.devcontainer.status_missing,
        ]
        for repo_dir in iter_workspace_repos(root)
    ]

    print_table(
        title=MESSAGES.devcontainer.status_table_title,
        columns=[(MESSAGES.devcontainer.col_repository, "cyan"), CONST_DEVCONTAINER_JSON_NAME],
        rows=rows,
    )


# =============================================================================
# Lifecycle Task Helpers
# =============================================================================


def _parse_mount_spec(mount: str | dict[str, str], workspace_dir: Path) -> tuple[Path, str] | None:
    """Parse a single mount definition into resolved target path and mount type."""
    if isinstance(mount, str):
        parts = [p.strip() for p in mount.split(",")]
        kv = dict(p.split("=", 1) for p in parts if "=" in p)
        raw_target = kv.get("target") or kv.get("dst") or kv.get("destination")
        mount_type = kv.get("type", "volume")
    elif isinstance(mount, dict):
        raw_target = mount.get("target") or mount.get("dst") or mount.get("destination")
        mount_type = mount.get("type", "volume")
    else:
        return None

    if not raw_target or not isinstance(raw_target, str):
        return None

    resolved = (
        raw_target.replace("${containerWorkspaceFolder}", str(workspace_dir))
        .replace("${workspaceFolder}", str(workspace_dir))
        .replace("${containerWorkspaceFolderBasename}", workspace_dir.name)
        .replace("${workspaceFolderBasename}", workspace_dir.name)
        .replace("${env:HOME}", str(Path.home()))
        .replace("${localEnv:HOME}", str(Path.home()))
        .replace("${localEnv:USERPROFILE}", str(Path.home()))
    )
    if resolved.startswith("~"):
        resolved = str(Path.home() / resolved[1:].lstrip("/"))

    return Path(resolved).resolve(), mount_type


def _extract_dc_mounts(dc_file: Path, workspace_dir: Path) -> list[tuple[Path, str]]:
    """Extract mount specs from a devcontainer.json configuration."""
    results: list[tuple[Path, str]] = []
    try:
        clean_text = _strip_json_comments(dc_file.read_text(encoding="utf-8"))
        data = json.loads(clean_text)
        mounts = data.get("mounts", [])
        if isinstance(mounts, list):
            for m in mounts:
                parsed = _parse_mount_spec(m, workspace_dir)
                if parsed:
                    results.append(parsed)
    except Exception as exc:
        logger.debug("Failed to extract mounts from %s: %s", dc_file, exc)
    return results


def _extract_mount_targets(workspace_dir: Path) -> list[tuple[Path, str]]:
    """Extract resolved volume mount target paths and types from devcontainer manifest and standard dirs."""
    targets: list[tuple[Path, str]] = []
    seen: set[Path] = set()

    candidates = [
        workspace_dir / CONST_DEVCONTAINER_JSON_PATH,
        workspace_dir / CONST_DEVCONTAINER_JSON_NAME,
    ]
    dc_file = next((c for c in candidates if c.exists()), None)
    if dc_file:
        for parsed in _extract_dc_mounts(dc_file, workspace_dir):
            if parsed[0] not in seen:
                seen.add(parsed[0])
                targets.append(parsed)

    # Standard devcontainer cache / environment directories in workspace
    for name in (
        ".venv",
        ".data",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".uv",
    ):
        p = (workspace_dir / name).resolve()
        if p not in seen:
            seen.add(p)
            targets.append((p, "volume"))

    return targets


def _chown_recursive_as_root(target_path: Path, uid: int, gid: int) -> None:
    """Recursively chown directory tree when running as root."""
    try:
        os.chown(str(target_path), uid, gid)
        if not target_path.is_dir():
            return
        for root, dirs, files in os.walk(target_path):
            for d in dirs:
                os.chown(os.path.join(root, d), uid, gid)
            for f in files:
                os.chown(os.path.join(root, f), uid, gid)
    except OSError as exc:
        logger.debug("Failed to chown %s: %s", target_path, exc)


def _ensure_path_ownership(target_path: Path) -> None:
    """Ensure target path and subpaths are owned by current process user."""
    get_uid = getattr(os, "getuid", None)
    get_gid = getattr(os, "getgid", None)
    if get_uid is None or get_gid is None:
        return

    current_uid = get_uid()
    current_gid = get_gid()

    try:
        stat_info = target_path.stat()
        if stat_info.st_uid == current_uid and stat_info.st_gid == current_gid:
            return
    except OSError:
        return

    if current_uid == 0:
        _chown_recursive_as_root(target_path, current_uid, current_gid)
    elif shutil.which("sudo"):
        run_subprocess(
            ["sudo", "chown", "-R", f"{current_uid}:{current_gid}", str(target_path)],
            check=False,
            quiet=True,
        )


def _safe_chmod_path(target_path: Path, mode: int, sudo_mode_str: str) -> None:
    """Apply chmod with sudo fallback on PermissionError."""
    try:
        target_path.chmod(mode)
    except PermissionError, OSError:
        if shutil.which("sudo"):
            run_subprocess(
                ["sudo", "chmod", sudo_mode_str, str(target_path)], check=False, quiet=True
            )


def _safe_mkdir_path(target_path: Path) -> None:
    """Create directory with sudo fallback on PermissionError."""
    try:
        target_path.mkdir(parents=True, exist_ok=True)
    except PermissionError, OSError:
        if shutil.which("sudo"):
            run_subprocess(["sudo", "mkdir", "-p", str(target_path)], check=False, quiet=True)


def _ensure_mount_permissions(
    target_path: Path, mount_type: str, *, dry_run: bool = False
) -> str | None:
    """Ensure directory creation, ownership, and mode permissions for a volume mount."""
    if target_path in CONST_SYSTEM_TEMP_DIRS:  # nosec B108
        if not dry_run:
            _safe_chmod_path(target_path, 0o1777, "1777")
        return MESSAGES.devcontainer.temp_dir_permissions_configured.format(path=target_path)

    if target_path.name == ".ssh" or str(target_path).endswith("/.ssh"):
        if not dry_run and target_path.exists():
            _ensure_path_ownership(target_path)
            _chmod_ssh_dir_and_keys(target_path)
        return f"Hardened SSH key permissions in {target_path}"

    if not dry_run:
        if not target_path.exists():
            _safe_mkdir_path(target_path)
        if target_path.exists():
            _ensure_path_ownership(target_path)
            _safe_chmod_path(target_path, 0o755, "755")

    return MESSAGES.devcontainer.mount_permissions_configured.format(path=target_path)


def _setup_volume_mount_permissions(workspace_dir: Path, *, dry_run: bool = False) -> list[str]:
    """Ensure all devcontainer volume mounts and workspace cache directories have proper permissions."""
    actions: list[str] = []
    targets = _extract_mount_targets(workspace_dir)
    for target_path, mount_type in targets:
        if target_path == CONST_ROOT_DIR:
            continue
        msg = _ensure_mount_permissions(target_path, mount_type, dry_run=dry_run)
        if msg:
            actions.append(msg)
    return actions


def _run_post_create_lifecycle(workspace_dir: Path, *, dry_run: bool = False) -> list[str]:
    """Execute DevContainer post-create setup tasks in pure Python."""
    actions: list[str] = []

    # 1. Volume mount permissions & ownership
    actions.extend(_setup_volume_mount_permissions(workspace_dir, dry_run=dry_run))

    # 2. Bootstrap uv & tools if not present
    if shutil.which("uv") is None and not dry_run:
        run_subprocess(
            ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
            check=False,
            quiet=True,
        )
        actions.append("Installed standalone uv binary into $HOME/.local/bin")

    # 3. Persistent bash history
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

    # 4. Config directory prep
    gemini_cfg = Path.home() / ".gemini" / "config"
    if not dry_run:
        gemini_cfg.mkdir(parents=True, exist_ok=True)
    actions.append(f"Ensured config directory exists at {gemini_cfg}")

    # 5. Agent instructions initialization
    agents_file = workspace_dir / CONST_AGENTS_MD_FILENAME
    if not agents_file.exists():
        if not dry_run:
            created = scaffold_agent_instructions(workspace_dir, force=False, template=True)
            if created:
                file_names = ", ".join(p.name for p in created)
                actions.append(
                    f"Scaffolded AI agent instructions ({file_names}) in {workspace_dir}"
                )
        else:
            actions.append(f"Scaffolded AI agent instructions (AGENTS.md) in {workspace_dir}")

    devops_cfg = os.getenv("DEVOPS_CLI_CONFIG")
    if devops_cfg and not Path(devops_cfg).exists():
        actions.append(f"Warning: Specified DEVOPS_CLI_CONFIG file does not exist: {devops_cfg}")

    return actions


def _chmod_ssh_dir_and_keys(ssh_dir: Path) -> None:
    """Set secure 0700 permissions on .ssh directory and 0600 on private keys."""
    try:
        ssh_dir.chmod(0o700)
        for key_path in ssh_dir.iterdir():
            if not key_path.is_file():
                continue
            if key_path.name.endswith(".pub"):
                key_path.chmod(0o644)
            else:
                key_path.chmod(0o600)
    except Exception as exc:
        logger.debug("Failed to set SSH permissions: %s", exc)


def _start_minikube_cluster(dry_run: bool) -> tuple[bool, str]:
    """Start Minikube cluster with GPU support if nvidia-smi is available, otherwise CPU."""
    has_gpu = bool(shutil.which("nvidia-smi"))
    start_cmd = ["minikube", "start", "--driver=docker"]
    if has_gpu:
        start_cmd.append("--gpus=all")
    if not dry_run:
        start_res = run_subprocess(start_cmd, check=False, quiet=True)
        if start_res.returncode == 0:
            gpu_str = " (--driver=docker --gpus=all)" if has_gpu else " (--driver=docker)"
            return True, f"Started Minikube cluster{gpu_str}"
        return False, "Warning: Failed to start Minikube cluster"
    gpu_str = " (--driver=docker --gpus=all)" if has_gpu else " (--driver=docker)"
    return True, f"Started Minikube cluster{gpu_str}"


def _auto_deploy_k8s_stack(workspace_dir: Path, stack: str, dry_run: bool) -> str | None:
    """Auto-deploy Kubernetes stack via devops k8s deploy-stack."""
    if not dry_run:
        res = run_subprocess(
            ["devops", "k8s", "deploy-stack", stack],
            cwd=workspace_dir,
            check=False,
            quiet=True,
        )
        if res.returncode == 0:
            return f"Auto-deployed Kubernetes stack '{stack}'"
        return f"Warning: Failed to auto-deploy Kubernetes stack '{stack}'"
    return f"Auto-deployed Kubernetes stack '{stack}'"


def _run_post_start_lifecycle(workspace_dir: Path, *, dry_run: bool = False) -> list[str]:
    """Execute DevContainer post-start lifecycle tasks in pure Python."""
    actions: list[str] = []

    # 1. Volume mount permissions & ownership
    actions.extend(_setup_volume_mount_permissions(workspace_dir, dry_run=dry_run))

    # 2. Git defaults
    if not dry_run:
        run_subprocess(
            ["git", "config", "--global", "push.autoSetupRemote", "true"],
            check=False,
            quiet=True,
        )
        run_subprocess(
            ["git", "config", "--global", "init.defaultBranch", "main"],
            check=False,
            quiet=True,
        )
    actions.append("Configured git push.autoSetupRemote=true and init.defaultBranch=main")

    # 3. SSH key permissions & commit signing
    ssh_dir = Path.home() / ".ssh"
    if ssh_dir.exists():
        if not dry_run:
            _chmod_ssh_dir_and_keys(ssh_dir)

        from devops_cli.crypto.ssh_keys import find_newest_key

        newest = find_newest_key(ssh_dir)
        if newest is None:
            # Fallback to any unmanaged private key matching id_ if no managed key exists
            fallback_keys = sorted(
                [
                    p
                    for p in ssh_dir.iterdir()
                    if p.is_file()
                    and not p.name.endswith(".pub")
                    and "id_" in p.name
                    and p.name
                    not in {"config", "known_hosts", "authorized_keys", "allowed_signers"}
                ],
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True,
            )
            if fallback_keys:
                newest = fallback_keys[0]

        if newest:
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
                run_subprocess(
                    ["git", "config", "--global", "commit.gpgsign", "true"],
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
            write_text_file(kube_file, kube_skeleton, mode=0o600)
    actions.append(f"Initialized kubeconfig file at {kube_file}")

    # 4. MCP configuration sync
    vscode_mcp = workspace_dir / CONST_VSCODE_DIR_NAME / CONST_MCP_JSON_NAME
    if not vscode_mcp.exists() and (workspace_dir / CONST_PYPROJECT_FILENAME).exists():
        if not dry_run:
            env = _jinja_env()
            raw_name = workspace_dir.name
            name = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw_name)
            write_text_file(
                vscode_mcp,
                env.get_template("mcp.json.j2").render(project_name=name),
            )
        actions.append(f"Scaffolded MCP configuration at {vscode_mcp}")

    if vscode_mcp.exists():
        for mcp_dest in (
            Path.home() / ".gemini" / "config" / "mcp_config.json",
            Path.home() / ".gemini" / "antigravity-ide" / "mcp_config.json",
        ):
            if not dry_run:
                raw_text = vscode_mcp.read_text(encoding="utf-8")
                synced_text = raw_text.replace("${workspaceFolder}", str(workspace_dir)).replace(
                    "${env:HOME}", str(Path.home())
                )
                write_text_file(mcp_dest, synced_text)
            actions.append(f"Synced MCP configuration to {mcp_dest}")

        agents_dir = workspace_dir / ".agents"
        if agents_dir.exists():
            agents_mcp_dest = agents_dir / "mcp_config.json"
            if not dry_run:
                raw_text = vscode_mcp.read_text(encoding="utf-8")
                synced_text = raw_text.replace("${workspaceFolder}", str(workspace_dir)).replace(
                    "${env:HOME}", str(Path.home())
                )
                write_text_file(agents_mcp_dest, synced_text)
            actions.append(f"Synced MCP configuration to {agents_mcp_dest}")

    # 5. AI Agent instructions initialization
    agents_file = workspace_dir / CONST_AGENTS_MD_FILENAME
    if not agents_file.exists():
        if not dry_run:
            created = scaffold_agent_instructions(workspace_dir, force=False, template=True)
            if created:
                file_names = ", ".join(p.name for p in created)
                actions.append(
                    f"Scaffolded AI agent instructions ({file_names}) in {workspace_dir}"
                )
        else:
            actions.append(f"Scaffolded AI agent instructions (AGENTS.md) in {workspace_dir}")

    # 6. Minikube autostart & K8s deploy status evaluation
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
                healthy, action_msg = _start_minikube_cluster(dry_run)
                actions.append(action_msg)
                minikube_healthy = healthy
                if healthy and not dry_run:
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
            result = _auto_deploy_k8s_stack(workspace_dir, stack, dry_run)
            if result:
                actions.append(result)
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
        except OSError, ValueError:
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


# =============================================================================
# Command: devops devcontainer post-create
# =============================================================================


@app.command("post-create")
def post_create(
    workspace: Annotated[
        Path, typer.Option("--workspace", "-w", help=HELP.options.workspace_dir)
    ] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
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

    print_info(MESSAGES.devcontainer.post_create_start.format(workspace=ws), prefix=False)
    actions = _run_post_create_lifecycle(ws, dry_run=False)
    for action in actions:
        print_info(f"  [green]✓[/green] {action}", prefix=False)
    print_success(MESSAGES.devcontainer.post_create_ready, prefix=False)


# =============================================================================
# Command: devops devcontainer post-start
# =============================================================================


@app.command("post-start")
def post_start(
    workspace: Annotated[
        Path, typer.Option("--workspace", "-w", help=HELP.options.workspace_dir)
    ] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
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

    print_info(MESSAGES.devcontainer.post_start_start.format(workspace=ws), prefix=False)
    actions = _run_post_start_lifecycle(ws, dry_run=False)
    for action in actions:
        print_info(f"  [green]✓[/green] {action}", prefix=False)
    print_success(MESSAGES.devcontainer.post_start_ready, prefix=False)


# =============================================================================
# Command: devops devcontainer run-lifecycle
# =============================================================================


@app.command("run-lifecycle")
def run_lifecycle(
    workspace: Annotated[
        Path, typer.Option("--workspace", "-w", help=HELP.options.workspace_dir)
    ] = DEFAULT_CURRENT_PATH,
    post_create_flag: Annotated[
        bool, typer.Option("--post-create", help=HELP.devcontainer.run_post_create)
    ] = False,
    post_start_flag: Annotated[
        bool, typer.Option("--post-start", help=HELP.devcontainer.run_post_start)
    ] = False,
    all_flag: Annotated[bool, typer.Option("--all", "-a", help=HELP.devcontainer.run_all)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
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
