"""Install DevOps tool binaries."""

from __future__ import annotations

import gzip
import hashlib
import io
import os
import platform
import re
import subprocess
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Final

import httpx2
import typer
from pydantic import BaseModel, ConfigDict
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.config.constants import (
    CONST_PERM_EXEC,
    CONST_URL_GITHUB_API_BASE,
    CONST_URL_GITHUB_ARGO_ROLLOUTS_RELEASES_BASE,
    CONST_URL_GITHUB_ARGO_WORKFLOWS_RELEASES_BASE,
    CONST_URL_GITHUB_ARGOCD_RELEASES_BASE,
    CONST_URL_GITHUB_KUSTOMIZE_RELEASES_BASE,
    CONST_URL_HELM_DOWNLOAD_BASE,
    CONST_URL_K8S_DOWNLOAD_BASE,
)
from devops_cli.config.defaults import (
    DEFAULT_HTTP_DOWNLOAD_TIMEOUT_SECONDS,
    DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_SUBPROCESS_FAST_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.validation import validate_version_str

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
            f"{CONST_URL_GITHUB_API_BASE}/repos/{repo}/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        r.raise_for_status()
        return str(r.json()["tag_name"])


def _download(url: str) -> bytes:
    from devops_cli.http.validation import validate_service_url

    if not url.startswith("https://"):
        raise ValueError(f"Only HTTPS URLs are permitted for tool downloads, got: {url!r}")
    validate_service_url(url, purpose="tool download")
    with httpx2.Client(follow_redirects=True) as c:
        r = c.get(url, timeout=DEFAULT_HTTP_DOWNLOAD_TIMEOUT_SECONDS)
        r.raise_for_status()
        return r.content


def _verify_sha256(data: bytes, expected_hex: str) -> None:
    """Raise ValueError if SHA-256 of data doesn't match expected_hex."""
    actual = hashlib.sha256(data).hexdigest().lower()
    if actual != expected_hex.strip().lower():
        raise ValueError(f"SHA-256 checksum mismatch (got {actual[:16]}…)")


def _parse_checksum_file(text: str, filename: str) -> str:
    """Extract hex digest for filename from a multi-entry checksums file."""
    for line in text.splitlines():
        line = line.strip().replace("\r", "")
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1].lstrip("*").strip() == filename:
            return parts[0].strip()
    raise ValueError(f"No checksum entry found for {filename!r}")


def _write_binary(data: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    dest.chmod(CONST_PERM_EXEC)


def _extract_tar_member(data: bytes, member: str, dest: Path) -> None:
    import os
    import shutil

    if member.startswith("/") or ".." in Path(member).parts:
        raise ValueError(f"Path traversal detected in archive member '{member}'")

    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        f = tf.extractfile(member)
        if f is None:
            raise FileNotFoundError(f"Member '{member}' not found in archive")
        with dest.open("wb") as out:
            shutil.copyfileobj(f, out)

    # Symlink-safe check: verify resolved dest stays within intended directory.
    resolved = dest.resolve()
    target_dir = dest.parent.resolve()
    if os.path.commonpath([resolved, target_dir]) != str(target_dir):
        dest.unlink(missing_ok=True)
        raise ValueError(f"Extracted path '{resolved}' escapes target directory '{target_dir}'")

    dest.chmod(CONST_PERM_EXEC)


def _current_version(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=DEFAULT_SUBPROCESS_FAST_TIMEOUT_SECONDS,
        )
        m = re.search(r"v?(\d+\.\d+[\.\d]*)", r.stdout + r.stderr)
        return f"v{m.group(1)}" if m else ("installed" if r.returncode == 0 else None)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


# ── Per-tool install functions ────────────────────────────────────────────────


def _install_kubectl(version: str, target_dir: Path) -> None:
    v = version.lstrip("v")
    url = f"{CONST_URL_K8S_DOWNLOAD_BASE}/release/v{v}/bin/{_OS}/{_ARCH}/kubectl{_EXE}"
    data = _download(url)
    sha256_text = _download(f"{url}.sha256").decode()
    _verify_sha256(data, sha256_text.split()[0])
    _write_binary(data, target_dir / f"kubectl{_EXE}")


def _validate_version_str(version: str, tool_name: str = "tool") -> str:
    """Validate that version string matches semantic version pattern."""
    return validate_version_str(version, tool_name)


def _latest_kubectl() -> str:
    with httpx2.Client(follow_redirects=True) as c:
        r = c.get(
            f"{CONST_URL_K8S_DOWNLOAD_BASE}/release/stable.txt",
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        r.raise_for_status()
        return r.text.strip()


def _install_kustomize(version: str, target_dir: Path) -> None:
    v = _validate_version_str(version, "kustomize")
    tar_name = f"kustomize_v{v}_{_OS}_{_ARCH}.tar.gz"
    url = f"{CONST_URL_GITHUB_KUSTOMIZE_RELEASES_BASE}/kustomize%2Fv{v}/{tar_name}"
    checksums_url = f"{CONST_URL_GITHUB_KUSTOMIZE_RELEASES_BASE}/kustomize%2Fv{v}/checksums.txt"
    data = _download(url)
    expected = _parse_checksum_file(_download(checksums_url).decode(), tar_name)
    _verify_sha256(data, expected)
    _extract_tar_member(data, "kustomize", target_dir / f"kustomize{_EXE}")


def _install_helm(version: str, target_dir: Path) -> None:
    v = _validate_version_str(version, "helm")
    tar_name = f"helm-v{v}-{_OS}-{_ARCH}.tar.gz"
    url = f"{CONST_URL_HELM_DOWNLOAD_BASE}/{tar_name}"
    data = _download(url)
    sha256_text = _download(f"{url}.sha256sum").decode()
    expected = _parse_checksum_file(sha256_text, tar_name)
    _verify_sha256(data, expected)
    _extract_tar_member(data, f"{_OS}-{_ARCH}/helm", target_dir / f"helm{_EXE}")


def _install_argo(version: str, target_dir: Path) -> None:
    v = _validate_version_str(version, "argo")
    gz_name = f"argo-{_OS}-{_ARCH}.gz"
    url = f"{CONST_URL_GITHUB_ARGO_WORKFLOWS_RELEASES_BASE}/v{v}/{gz_name}"
    data = _download(url)
    sha256_text = _download(f"{url}.sha256").decode()
    _verify_sha256(data, sha256_text.split()[0])
    _write_binary(gzip.decompress(data), target_dir / f"argo{_EXE}")


def _install_argocd(version: str, target_dir: Path) -> None:
    v = _validate_version_str(version, "argocd")
    bin_name = f"argocd-{_OS}-{_ARCH}{_EXE}"
    url = f"{CONST_URL_GITHUB_ARGOCD_RELEASES_BASE}/v{v}/{bin_name}"
    data = _download(url)
    checksums_text = _download(
        f"{CONST_URL_GITHUB_ARGOCD_RELEASES_BASE}/v{v}/cli_checksums.txt"
    ).decode()
    expected = _parse_checksum_file(checksums_text, bin_name)
    _verify_sha256(data, expected)
    _write_binary(data, target_dir / f"argocd{_EXE}")


def _install_rollouts(version: str, target_dir: Path) -> None:
    v = _validate_version_str(version, "rollouts")
    bin_name = f"kubectl-argo-rollouts-{_OS}-{_ARCH}{_EXE}"
    url = f"{CONST_URL_GITHUB_ARGO_ROLLOUTS_RELEASES_BASE}/v{v}/{bin_name}"
    data = _download(url)
    checksums_text = _download(
        f"{CONST_URL_GITHUB_ARGO_ROLLOUTS_RELEASES_BASE}/v{v}/sha256checksums.txt"
    ).decode()
    expected = _parse_checksum_file(checksums_text, bin_name)
    _verify_sha256(data, expected)
    _write_binary(data, target_dir / f"kubectl-argo-rollouts{_EXE}")


def _install_trivy(version: str, target_dir: Path) -> None:
    v = _validate_version_str(version, "trivy")
    arch_str = "64bit" if _ARCH == "amd64" else "ARM64"
    tar_name = f"trivy_{v}_Linux-{arch_str}.tar.gz"
    url = f"https://github.com/aquasecurity/trivy/releases/download/v{v}/{tar_name}"
    checksums_url = (
        f"https://github.com/aquasecurity/trivy/releases/download/v{v}/trivy_{v}_checksums.txt"
    )
    data = _download(url)
    try:
        expected = _parse_checksum_file(_download(checksums_url).decode(), tar_name)
        _verify_sha256(data, expected)
    except Exception:
        pass
    _extract_tar_member(data, f"trivy{_EXE}", target_dir / f"trivy{_EXE}")


def _install_kubelinter(version: str, target_dir: Path) -> None:
    v = version.lstrip("v")
    tar_name = f"kube-linter-linux-{_ARCH}.tar.gz"
    url = f"https://github.com/stackrox/kube-linter/releases/download/v{v}/{tar_name}"
    data = _download(url)
    _extract_tar_member(data, f"kube-linter{_EXE}", target_dir / f"kube-linter{_EXE}")


def _install_popeye(version: str, target_dir: Path) -> None:
    v = version.lstrip("v")
    tar_name = f"popeye_linux_{_ARCH}.tar.gz"
    url = f"https://github.com/derailed/popeye/releases/download/v{v}/{tar_name}"
    checksums_url = f"https://github.com/derailed/popeye/releases/download/v{v}/checksums.sha256"
    data = _download(url)
    try:
        expected = _parse_checksum_file(_download(checksums_url).decode(), tar_name)
        _verify_sha256(data, expected)
    except Exception:
        pass
    _extract_tar_member(data, f"popeye{_EXE}", target_dir / f"popeye{_EXE}")


def _install_pluto(version: str, target_dir: Path) -> None:
    v = version.lstrip("v")
    tar_name = f"pluto_{v}_linux_{_ARCH}.tar.gz"
    url = f"https://github.com/FairwindsOps/pluto/releases/download/v{v}/{tar_name}"
    checksums_url = f"https://github.com/FairwindsOps/pluto/releases/download/v{v}/checksums.txt"
    data = _download(url)
    try:
        expected = _parse_checksum_file(_download(checksums_url).decode(), tar_name)
        _verify_sha256(data, expected)
    except Exception:
        pass
    _extract_tar_member(data, f"pluto{_EXE}", target_dir / f"pluto{_EXE}")


def _install_k9s(version: str, target_dir: Path) -> None:
    v = version if version.startswith("v") else f"v{version}"
    os_cap = "Linux" if _OS == "linux" else ("Darwin" if _OS == "darwin" else "Windows")
    tar_name = f"k9s_{os_cap}_{_ARCH}.tar.gz"
    url = f"https://github.com/derailed/k9s/releases/download/{v}/{tar_name}"
    checksums_url = f"https://github.com/derailed/k9s/releases/download/{v}/checksums.sha256"
    data = _download(url)
    try:
        expected = _parse_checksum_file(_download(checksums_url).decode(), tar_name)
        _verify_sha256(data, expected)
    except Exception:
        pass
    _extract_tar_member(data, f"k9s{_EXE}", target_dir / f"k9s{_EXE}")


# ── Tool registry ─────────────────────────────────────────────────────────────


class Tool(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    bin_name: str
    version_cmd: list[str]
    get_latest: Callable[[], str]
    install: Callable[[str, Path], None]


TOOLS: Final[dict[str, Tool]] = {
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
    "trivy": Tool(
        name="trivy",
        description="Aqua Trivy vulnerability, secret & IaC scanner",
        bin_name="trivy",
        version_cmd=["trivy", "version"],
        get_latest=lambda: _gh_latest("aquasecurity/trivy"),
        install=_install_trivy,
    ),
    "kube-linter": Tool(
        name="kube-linter",
        description="Red Hat Kube-linter static K8s manifest linter",
        bin_name="kube-linter",
        version_cmd=["kube-linter", "version"],
        get_latest=lambda: _gh_latest("stackrox/kube-linter"),
        install=_install_kubelinter,
    ),
    "popeye": Tool(
        name="popeye",
        description="Derailed Popeye K8s cluster health sanitizer",
        bin_name="popeye",
        version_cmd=["popeye", "version"],
        get_latest=lambda: _gh_latest("derailed/popeye"),
        install=_install_popeye,
    ),
    "pluto": Tool(
        name="pluto",
        description="Fairwinds Pluto K8s deprecated API scanner",
        bin_name="pluto",
        version_cmd=["pluto", "version"],
        get_latest=lambda: _gh_latest("FairwindsOps/pluto"),
        install=_install_pluto,
    ),
    "k9s": Tool(
        name="k9s",
        description="Derailed K9s Kubernetes CLI TUI dashboard",
        bin_name="k9s",
        version_cmd=["k9s", "version", "--short"],
        get_latest=lambda: _gh_latest("derailed/k9s"),
        install=_install_k9s,
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

    if version and not re.match(r"^v?\d+\.\d+(\.\d+)*(-\w+)?$", version):
        rprint(f"[red]Invalid version format '{version}'. Expected semver e.g. v1.30.0[/red]")
        raise typer.Exit(1)

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
