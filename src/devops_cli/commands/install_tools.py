"""Install DevOps tool binaries."""

from __future__ import annotations

import gzip
import io
import os
import platform
import re
import stat
import subprocess
import tarfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import httpx2
import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.cli import new_typer

app = new_typer(help="Install and manage DevOps tool binaries.", no_args_is_help=True)
console = Console()

DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"


# ── Platform detection ────────────────────────────────────────────────────────


def _sys_info() -> tuple[str, str]:
    system = platform.system().lower()
    arch = platform.machine().lower()
    os_name = {"darwin": "darwin", "linux": "linux", "windows": "windows"}.get(system, system)
    arch_name = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(
        arch, arch
    )
    return os_name, arch_name


_OS, _ARCH = _sys_info()
_EXE = ".exe" if _OS == "windows" else ""


# ── Download helpers ──────────────────────────────────────────────────────────


def _gh_latest(repo: str) -> str:
    with httpx2.Client(follow_redirects=True) as c:
        r = c.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
            timeout=30,
        )
        r.raise_for_status()
        return str(r.json()["tag_name"])


def _download(url: str) -> bytes:
    with httpx2.Client(follow_redirects=True) as c:
        r = c.get(url, timeout=120)
        r.raise_for_status()
        return r.content


def _write_binary(data: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    dest.chmod(dest.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _extract_tar_member(data: bytes, member: str, dest: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        f = tf.extractfile(member)
        if f is None:
            raise FileNotFoundError(f"Member '{member}' not found in archive")
        _write_binary(f.read(), dest)


def _current_version(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        m = re.search(r"v?(\d+\.\d+[\.\d]*)", r.stdout + r.stderr)
        return f"v{m.group(1)}" if m else ("installed" if r.returncode == 0 else None)
    except FileNotFoundError, subprocess.TimeoutExpired, OSError:
        return None


# ── Per-tool install functions ────────────────────────────────────────────────


def _install_kubectl(version: str, target_dir: Path) -> None:
    v = version.lstrip("v")
    url = f"https://dl.k8s.io/release/v{v}/bin/{_OS}/{_ARCH}/kubectl{_EXE}"
    _write_binary(_download(url), target_dir / f"kubectl{_EXE}")


def _latest_kubectl() -> str:
    with httpx2.Client(follow_redirects=True) as c:
        r = c.get("https://dl.k8s.io/release/stable.txt", timeout=30)
        r.raise_for_status()
        return r.text.strip()


def _install_kustomize(version: str, target_dir: Path) -> None:
    v = version.lstrip("v")
    url = (
        f"https://github.com/kubernetes-sigs/kustomize/releases/download/"
        f"kustomize%2Fv{v}/kustomize_v{v}_{_OS}_{_ARCH}.tar.gz"
    )
    _extract_tar_member(_download(url), "kustomize", target_dir / f"kustomize{_EXE}")


def _install_helm(version: str, target_dir: Path) -> None:
    v = version.lstrip("v")
    url = f"https://get.helm.sh/helm-v{v}-{_OS}-{_ARCH}.tar.gz"
    _extract_tar_member(_download(url), f"{_OS}-{_ARCH}/helm", target_dir / f"helm{_EXE}")


def _install_argo(version: str, target_dir: Path) -> None:
    v = version.lstrip("v")
    url = f"https://github.com/argoproj/argo-workflows/releases/download/v{v}/argo-{_OS}-{_ARCH}.gz"
    _write_binary(gzip.decompress(_download(url)), target_dir / f"argo{_EXE}")


def _install_argocd(version: str, target_dir: Path) -> None:
    v = version.lstrip("v")
    url = f"https://github.com/argoproj/argo-cd/releases/download/v{v}/argocd-{_OS}-{_ARCH}{_EXE}"
    _write_binary(_download(url), target_dir / f"argocd{_EXE}")


def _install_rollouts(version: str, target_dir: Path) -> None:
    v = version.lstrip("v")
    url = (
        f"https://github.com/argoproj/argo-rollouts/releases/download/"
        f"v{v}/kubectl-argo-rollouts-{_OS}-{_ARCH}{_EXE}"
    )
    _write_binary(_download(url), target_dir / f"kubectl-argo-rollouts{_EXE}")


# ── Tool registry ─────────────────────────────────────────────────────────────


@dataclass
class Tool:
    name: str
    description: str
    bin_name: str
    version_cmd: list[str]
    get_latest: Callable[[], str]
    install: Callable[[str, Path], None]


TOOLS: dict[str, Tool] = {
    "kubectl": Tool(
        name="kubectl",
        description="Kubernetes CLI",
        bin_name="kubectl",
        version_cmd=["kubectl", "version", "--client", "--short"],
        get_latest=_latest_kubectl,
        install=_install_kubectl,
    ),
    "kustomize": Tool(
        name="kustomize",
        description="Kustomize config management",
        bin_name="kustomize",
        version_cmd=["kustomize", "version"],
        get_latest=lambda: _gh_latest("kubernetes-sigs/kustomize").replace("kustomize/", ""),
        install=_install_kustomize,
    ),
    "helm": Tool(
        name="helm",
        description="Kubernetes package manager",
        bin_name="helm",
        version_cmd=["helm", "version", "--short"],
        get_latest=lambda: _gh_latest("helm/helm"),
        install=_install_helm,
    ),
    "argo": Tool(
        name="argo",
        description="Argo Workflows CLI",
        bin_name="argo",
        version_cmd=["argo", "version", "--short"],
        get_latest=lambda: _gh_latest("argoproj/argo-workflows"),
        install=_install_argo,
    ),
    "argocd": Tool(
        name="argocd",
        description="ArgoCD CLI",
        bin_name="argocd",
        version_cmd=["argocd", "version", "--client", "--short"],
        get_latest=lambda: _gh_latest("argoproj/argo-cd"),
        install=_install_argocd,
    ),
    "kubectl-argo-rollouts": Tool(
        name="kubectl-argo-rollouts",
        description="Argo Rollouts kubectl plugin",
        bin_name="kubectl-argo-rollouts",
        version_cmd=["kubectl-argo-rollouts", "version"],
        get_latest=lambda: _gh_latest("argoproj/argo-rollouts"),
        install=_install_rollouts,
    ),
}


# ── Commands ──────────────────────────────────────────────────────────────────


@app.callback(invoke_without_command=True)
def install_all(
    ctx: typer.Context,
    tool: Annotated[
        str | None, typer.Option("--tool", "-t", help="Install a specific tool")
    ] = None,
    version: Annotated[
        str | None, typer.Option("--version", help="Specific version, e.g. v1.30.0")
    ] = None,
    target_dir: Annotated[Path, typer.Option("--target-dir", "-d")] = DEFAULT_BIN_DIR,
) -> None:
    """Install DevOps tool binaries. Without --tool, installs all tools."""
    if ctx.invoked_subcommand is not None:
        return

    if tool and tool not in TOOLS:
        rprint(f"[red]Unknown tool '{tool}'. Available: {', '.join(TOOLS)}[/red]")
        raise typer.Exit(1)

    targets = {tool: TOOLS[tool]} if tool else TOOLS
    target_dir.mkdir(parents=True, exist_ok=True)

    for name, spec in targets.items():
        ver = version
        if not ver:
            rprint(f"Fetching latest version for [cyan]{name}[/cyan]...")
            try:
                ver = spec.get_latest()
            except Exception as exc:
                rprint(f"  [red]✗[/red] {name}: could not determine latest — {exc}")
                continue

        rprint(f"Installing [cyan]{name}[/cyan] {ver}...")
        try:
            spec.install(ver, target_dir)
            rprint(f"  [green]✓[/green] {target_dir / (spec.bin_name + _EXE)}")
        except Exception as exc:
            rprint(f"  [red]✗[/red] {name}: {exc}")

    _path_hint(target_dir)


@app.command()
def status(
    target_dir: Annotated[Path, typer.Option("--target-dir", "-d")] = DEFAULT_BIN_DIR,
) -> None:
    """Show installation status and versions for all managed tools."""
    table = Table(title="DevOps Tool Status")
    table.add_column("Tool", style="cyan")
    table.add_column("Description")
    table.add_column("Installed")
    table.add_column("Latest", style="dim")

    for name, spec in TOOLS.items():
        current = _current_version(spec.version_cmd)
        installed = f"[green]{current}[/green]" if current else "[red]not installed[/red]"
        try:
            latest = spec.get_latest()
        except Exception:
            latest = "unknown"
        table.add_row(name, spec.description, installed, latest)

    console.print(table)


def _path_hint(target_dir: Path) -> None:
    if str(target_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        rprint(
            f"\n[yellow]Note:[/yellow] {target_dir} is not in your PATH.\n"
            f'Add to your shell config:  [dim]export PATH="{target_dir}:$PATH"[/dim]'
        )
