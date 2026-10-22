"""The tools lock: every tool `devops install-tools` installs, at an exact version (#1142).

`tools.lock`, beside this module, names each tool's version and source. A binary tool lists, per
platform, the URL of its build and that build's SHA-256; a Python tool names a requirements file
compiled with `uv pip compile --generate-hashes`, installed into a virtual environment of its own;
a Node tool has a directory beside the lock, named for it, whose `package.json` pins its one
dependency and whose `package-lock.json` records the sha512 of every package, installed with
`npm ci`. Each tool version installs under the user-level data root, and the commands it provides
link there, so a command on PATH is at its pin exactly when its link resolves into that directory.

A review records the lock's digest as one of its inputs: two reviews ran the same tools only when
their digests match.
"""

from __future__ import annotations

import functools
import tomllib
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import CONST_NPM_PROJECT_FILES
from devops_cli.core.repo import user_data_root

LOCK_DIR = Path(__file__).resolve().parent
LOCK_FILENAME = "tools.lock"


class _LockEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


ArchiveFormat = Literal["binary", "gzip", "tar.gz"]


class Artifact(_LockEntry):
    """One platform's build of a binary tool: where it is fetched from and its SHA-256."""

    url: str
    sha256: str
    # The archive member that is the tool, for a tar.gz build.
    member: str | None = None
    # A build packed unlike the tool's others, such as cloudflared's macOS tar.gz.
    format: ArchiveFormat | None = None


class BinaryTool(_LockEntry):
    """A tool published as a binary, a gzip file or a tar.gz archive per platform."""

    version: str
    description: str
    source: str
    bin: str
    format: ArchiveFormat
    # Builds by `<os>-<arch>`, such as `linux-amd64`.
    platforms: dict[str, Artifact]

    # Where in the version directory the tool's commands are.
    command_dir: ClassVar[tuple[str, ...]] = ()

    def format_of(self, artifact: Artifact) -> ArchiveFormat:
        """How `artifact` is packed: its own format, else the tool's."""
        return artifact.format or self.format

    @property
    def commands(self) -> tuple[str, ...]:
        """The commands the tool puts on PATH."""
        return (self.bin,)


class PythonTool(_LockEntry):
    """A tool installed from PyPI into a virtual environment of its own."""

    version: str
    description: str
    source: str
    # The hashed requirements file beside the lock.
    requirements: str
    entry_points: list[str]

    # Where in the version directory the tool's commands are.
    command_dir: ClassVar[tuple[str, ...]] = ("bin",)

    @property
    def commands(self) -> tuple[str, ...]:
        """The commands the tool puts on PATH."""
        return tuple(self.entry_points)


class NpmTool(_LockEntry):
    """A Node tool installed with `npm ci` from the `package.json` and `package-lock.json` in the
    directory beside the lock that is named for it."""

    version: str
    description: str
    source: str
    # The command the tool's package links into `node_modules/.bin`.
    bin: str

    # Where in the version directory the tool's commands are.
    command_dir: ClassVar[tuple[str, ...]] = ("node_modules", ".bin")

    @property
    def commands(self) -> tuple[str, ...]:
        """The commands the tool puts on PATH."""
        return (self.bin,)


# Any of the three kinds of tool the lock holds.
LockedTool = BinaryTool | PythonTool | NpmTool


class ToolsLock(_LockEntry):
    """The whole lock."""

    # The Python each Python tool's virtual environment runs.
    python_version: str
    binary: dict[str, BinaryTool]
    python: dict[str, PythonTool]
    npm: dict[str, NpmTool]

    def tools(self) -> dict[str, LockedTool]:
        """Every tool by name, binaries first, then Python and Node tools, in the order the lock
        lists them."""
        return {**self.binary, **self.python, **self.npm}


def read_tools_lock(lock_dir: Path) -> ToolsLock:
    """The lock in `lock_dir`."""
    return ToolsLock.model_validate(tomllib.loads((lock_dir / LOCK_FILENAME).read_text("utf-8")))


@functools.cache
def load_tools_lock() -> ToolsLock:
    """The lock devops-cli ships."""
    return read_tools_lock(LOCK_DIR)


def reset_tools_lock_cache() -> None:
    """Clear the cached tools.lock parse."""
    load_tools_lock.cache_clear()


def tools_lock_digest(lock_dir: Path = LOCK_DIR) -> str:
    """A digest of the lock and its requirements and package files, in the form of the review
    prompt digest.

    Any change to a pin, a URL, a checksum, a hashed requirement or a Node tool's manifest or
    lockfile changes it.
    """
    from devops_cli.ai.run_store import digest

    lock = read_tools_lock(lock_dir)
    names = [
        LOCK_FILENAME,
        *(tool.requirements for tool in lock.python.values()),
        *(f"{name}/{filename}" for name in lock.npm for filename in CONST_NPM_PROJECT_FILES),
    ]
    return digest({name: (lock_dir / name).read_text(encoding="utf-8") for name in names})


def tool_install_dir(name: str, version: str) -> Path:
    """Where version `version` of tool `name` installs: a binary tool's file, a Python tool's
    virtual environment, or a Node tool's `node_modules`."""
    return user_data_root() / "tools" / name / version


def installed_commands(name: str, tool: LockedTool) -> dict[str, Path]:
    """Each command `tool` puts on PATH, and the file in its version directory it links to."""
    directory = tool_install_dir(name, tool.version).joinpath(*tool.command_dir)
    return {command: directory / command for command in tool.commands}


__all__ = [
    "LOCK_DIR",
    "LOCK_FILENAME",
    "Artifact",
    "BinaryTool",
    "LockedTool",
    "NpmTool",
    "PythonTool",
    "ToolsLock",
    "installed_commands",
    "load_tools_lock",
    "read_tools_lock",
    "tool_install_dir",
    "tools_lock_digest",
]
