"""Install DevOps tools from the tools lock, each at its exact version (#1142).

The lock (`devops_cli.tools_lock`) is the registry: nothing installs at a version it does not
name. A binary tool's build for this platform is downloaded from the lock's URL alone and refused
unless its SHA-256 is the lock's. A Python tool installs from its hashed requirements file into a
relocatable virtual environment of its own. Each install is staged beside its version directory,
moved into place with one rename, and linked from the target directory, so a tool is at its pin
exactly when its command links into that version directory. Once linked, the tool's other version
directories are removed.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import os
import platform
import shutil
import tarfile
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Final

import httpx2
import typer

from devops_cli.config.constants import CONST_PERM_EXEC
from devops_cli.config.defaults import DEFAULT_HTTP_TIMEOUT_SECONDS, DEFAULT_LOCAL_BIN_DIR
from devops_cli.core.binaries import require_binary
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import ChecksumMismatchError, ToolDownloadError, ToolExecutionError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
)
from devops_cli.tools_lock import (
    LOCK_DIR,
    Artifact,
    BinaryTool,
    PythonTool,
    installed_commands,
    load_tools_lock,
    tool_install_dir,
)

app = new_typer(help=HELP.install.app, no_args_is_help=True)


# =============================================================================
# Platform Detection
# =============================================================================


def _sys_info() -> tuple[str, str]:
    system = platform.system().lower()
    arch = platform.machine().lower()
    os_name = {"darwin": "darwin", "linux": "linux", "windows": "windows"}.get(system, system)
    arch_name = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(
        arch, arch
    )
    return os_name, arch_name


# The lock's key for this machine's builds, such as `linux-amd64`.
_PLATFORM: Final[str] = "-".join(_sys_info())


# ── Download helpers ──────────────────────────────────────────────────────────


def _require_https(request: httpx2.Request) -> None:
    """Refuse a tool download hop, the first request or a redirect, that is not https."""
    if request.url.scheme != "https":
        raise ToolDownloadError(
            str(request.url)[:256], reason="Only HTTPS URLs are permitted for tool downloads"
        )


def _download_client() -> httpx2.Client:
    """A public-only client that follows redirects and refuses every hop that is not https.

    The tool hosts are public, so a name answering a private, loopback or metadata address is
    refused at the connect, whatever `ai.allow_private_network` says.
    """
    return new_http_client(
        level=EgressLevel.PUBLIC,
        follow_redirects=True,
        event_hooks={"request": [_require_https]},
    )


def _download(url: str) -> bytes:
    with _download_client() as c:
        r = c.get(url, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS)
        r.raise_for_status()
        return r.content


def _verify_sha256(name: str, data: bytes, expected_hex: str) -> None:
    """Refuse `data` unless its SHA-256 is the one the lock gives for tool `name`."""
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_hex.lower():
        raise ChecksumMismatchError(name, actual_checksum=actual, expected_checksum=expected_hex)


# ── Unpacking ─────────────────────────────────────────────────────────────────


def _write_binary(data: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    dest.chmod(CONST_PERM_EXEC)


def _extract_tar_member(data: bytes, member: str, dest: Path) -> None:
    """Copy the verified archive's `member`, the one the lock names, to the new file `dest`."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        f = tf.extractfile(member)
        if f is None:
            raise ToolExecutionError(f"Archive member '{member}' is not a file")
        with dest.open("wb") as out:
            shutil.copyfileobj(f, out)
    dest.chmod(CONST_PERM_EXEC)


# Writes a verified build's executable to its destination, by the lock's `format`.
_UNPACKERS: Final[dict[str, Callable[[bytes, Artifact, Path], None]]] = {
    "binary": lambda data, artifact, dest: _write_binary(data, dest),
    "gzip": lambda data, artifact, dest: _write_binary(gzip.decompress(data), dest),
    "tar.gz": lambda data, artifact, dest: _extract_tar_member(
        data, artifact.member or dest.name, dest
    ),
}


# ── Installing at the pin ─────────────────────────────────────────────────────


@contextmanager
def _staged(pinned: Path) -> Iterator[Path]:
    """A new directory beside `pinned` that becomes `pinned` when the block completes.

    It sits on the same filesystem as `pinned`, so one rename moves it into place, and it is
    removed when the block fails, leaving any earlier install of that version untouched.
    """
    pinned.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=pinned.parent))
    try:
        yield stage
        shutil.rmtree(pinned, ignore_errors=True)
        os.replace(stage, pinned)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _link(command: Path, installed: Path) -> None:
    """Point `command` at `installed` with one rename, replacing any file or link there."""
    command.parent.mkdir(parents=True, exist_ok=True)
    temporary = command.with_name(f".{command.name}.{os.getpid()}.link")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(installed)
    os.replace(temporary, command)


def _link_commands(name: str, entry: BinaryTool | PythonTool, target_dir: Path) -> None:
    """Link the tool's commands to its locked version, then remove the tool's other versions."""
    for command, installed in installed_commands(name, entry).items():
        _link(target_dir / command, installed)
    pinned = tool_install_dir(name, entry.version)
    for other in pinned.parent.iterdir():
        if other != pinned:
            shutil.rmtree(other, ignore_errors=True)


def install_binary(name: str, entry: BinaryTool, target_dir: Path) -> None:
    """Install this platform's build of `name`, verified against the lock, and link it."""
    artifact = entry.platforms.get(_PLATFORM)
    if artifact is None:
        raise ToolExecutionError(f"tools.lock has no {_PLATFORM} build of {name}", tool_name=name)
    with _staged(tool_install_dir(name, entry.version)) as stage:
        data = _download(artifact.url)
        _verify_sha256(name, data, artifact.sha256)
        _UNPACKERS[entry.format](data, artifact, stage / entry.bin)
    _link_commands(name, entry, target_dir)


# The uv settings a locked install keeps from the environment, those the devcontainer sets that
# cannot change what it installs: the malware check can only refuse a distribution, and the cache
# directory and link mode only decide where and how its bytes are kept.
_UV_ENV: Final[frozenset[str]] = frozenset({"UV_MALWARE_CHECK", "UV_CACHE_DIR", "UV_LINK_MODE"})


def _run_uv(name: str, args: list[str]) -> None:
    """Run `uv --no-config <args>`, so a `uv.toml` or `[tool.uv]` in the current directory cannot
    change the install, and raise with uv's reason when it fails."""
    result = run_subprocess(["uv", "--no-config", *args], quiet=True, extra_allowed_env=_UV_ENV)
    if result.returncode != 0:
        raise ToolExecutionError(
            f"uv could not install {name}: {result.stderr.strip()[-256:]}", tool_name=name
        )


def install_python_tool(name: str, entry: PythonTool, target_dir: Path) -> None:
    """Install `name` from its hashed requirements into a relocatable virtual environment of its
    own, and link its entry points.

    The environment is created relocatable (`uv venv --relocatable`) so that it survives the
    rename from its staging directory into place; uv refuses any distribution whose hash the
    requirements file does not list.
    """
    require_binary("uv")
    with _staged(tool_install_dir(name, entry.version)) as stage:
        python_version = load_tools_lock().python_version
        _run_uv(name, ["venv", "--relocatable", "--python", python_version, str(stage)])
        python = str(stage / "bin" / "python")
        requirements = str(LOCK_DIR / entry.requirements)
        _run_uv(name, ["pip", "sync", "--require-hashes", "-p", python, requirements])
    _link_commands(name, entry, target_dir)


def install_tool(name: str, entry: BinaryTool | PythonTool, target_dir: Path) -> None:
    """Install `name` at its locked version and link its commands into `target_dir`."""
    if isinstance(entry, PythonTool):
        install_python_tool(name, entry, target_dir)
    else:
        install_binary(name, entry, target_dir)


def _at_pin(name: str, entry: BinaryTool | PythonTool, target_dir: Path) -> bool:
    """Whether each of the tool's commands in `target_dir` links to its locked version."""
    return all(
        installed.is_file() and (target_dir / command).resolve() == installed.resolve()
        for command, installed in installed_commands(name, entry).items()
    )


def _off_pin(
    tools: dict[str, BinaryTool | PythonTool], target_dir: Path
) -> dict[str, BinaryTool | PythonTool]:
    """The tools whose commands in `target_dir` do not link to their locked versions."""
    return {name: entry for name, entry in tools.items() if not _at_pin(name, entry, target_dir)}


def _installed(name: str, entry: BinaryTool | PythonTool, target_dir: Path) -> str:
    """`at pin`; else the command PATH finds, searching `target_dir` first; else `not installed`."""
    if _at_pin(name, entry, target_dir):
        return MESSAGES.install.at_pin
    search_path = os.pathsep.join((str(target_dir), os.environ.get("PATH", "")))
    found = shutil.which(entry.commands[0], path=search_path)
    return found or MESSAGES.install.not_installed


# =============================================================================
# Command: devops install-tools
# =============================================================================


def _resolve_install_targets(tool: str | None) -> dict[str, BinaryTool | PythonTool]:
    tools = load_tools_lock().tools()
    if tool is None:
        return tools
    if tool not in tools:
        print_error(f"Unknown tool '{tool}'. Available: {', '.join(tools)}", prefix=False)
        raise typer.Exit(1)
    return {tool: tools[tool]}


def _install_single_target(name: str, entry: BinaryTool | PythonTool, target_dir: Path) -> bool:
    """Install one tool, printing its command's path or why it was refused; whether it installed."""
    print_info(
        MESSAGES.install.installing_tool.format(name=name, version=entry.version),
        prefix=False,
    )
    try:
        install_tool(name, entry, target_dir)
    except Exception as exc:
        print_error(f"{name}: {exc}")
        return False
    print_success(str(target_dir / entry.commands[0]))
    return True


def _check_pins(targets: dict[str, BinaryTool | PythonTool], target_dir: Path) -> None:
    """Print each tool not at its pin and exit 1, or confirm that every tool is."""
    off_pin = _off_pin(targets, target_dir)
    for name, entry in off_pin.items():
        installed = _installed(name, entry, target_dir)
        print_error(
            MESSAGES.install.check_off_pin.format(
                name=name, version=entry.version, installed=installed
            ),
            prefix=False,
        )
    if off_pin:
        raise typer.Exit(1)
    print_success(MESSAGES.install.check_all_pinned.format(count=len(targets), path=target_dir))


def install_managed_tools(
    target_dir: Path = DEFAULT_LOCAL_BIN_DIR,
    *,
    only_missing: bool = True,
) -> list[str]:
    """Install the locked tools into target_dir, as post-create does.

    Returns one human-readable line per tool it installed or failed to install.
    """
    tools = load_tools_lock().tools()
    actions: list[str] = []
    for name, entry in (_off_pin(tools, target_dir) if only_missing else tools).items():
        try:
            install_tool(name, entry, target_dir)
            actions.append(f"Installed {name} {entry.version} into {target_dir}")
        except Exception as exc:
            actions.append(f"Warning: Failed to install {name} ({exc})")
    return actions


@app.callback(invoke_without_command=True)
def install_all(
    ctx: typer.Context,
    tool: Annotated[str | None, typer.Option("--tool", "-t", help=HELP.install.tool)] = None,
    target_dir: Annotated[
        Path, typer.Option("--target-dir", "-d", help=HELP.options.target_dir)
    ] = DEFAULT_LOCAL_BIN_DIR,
    only_missing: Annotated[
        bool, typer.Option("--only-missing", help=HELP.install.only_missing)
    ] = False,
    check: Annotated[bool, typer.Option("--check", help=HELP.install.check)] = False,
) -> None:
    """Install DevOps tools at their locked versions. Without --tool, installs all tools.

    Exits 1 when any tool did not install, such as a build refused for its checksum.
    """
    if ctx.invoked_subcommand is not None:
        return

    targets = _resolve_install_targets(tool)
    if check:
        _check_pins(targets, target_dir)
        return
    installed = [
        _install_single_target(name, entry, target_dir)
        for name, entry in (_off_pin(targets, target_dir) if only_missing else targets).items()
    ]

    _path_hint(target_dir)
    if not all(installed):
        raise typer.Exit(1)


# =============================================================================
# Command: devops install-tools status
# =============================================================================


@app.command()
def status(
    target_dir: Annotated[
        Path, typer.Option("--target-dir", "-d", help=HELP.options.target_dir)
    ] = DEFAULT_LOCAL_BIN_DIR,
) -> None:
    """Show each tool's locked version and where its command is installed, without a request."""
    rows = [
        [name, entry.description, entry.version, _installed(name, entry, target_dir)]
        for name, entry in load_tools_lock().tools().items()
    ]
    print_table(
        title=MESSAGES.install.status_title,
        columns=[("Tool", "cyan"), "Description", "Pinned", "Installed"],
        rows=rows,
    )


# =============================================================================
# Path Configuration Hint Helper
# =============================================================================


def _path_hint(target_dir: Path) -> None:
    if str(target_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        print_warning(
            MESSAGES.install.path_hint.format(path=str(target_dir)),
            prefix=False,
        )
