"""The tools lock: every tool `devops install-tools` installs, at an exact version (#1142).

`tools.lock`, beside this module, names each tool's version and source. A binary tool lists, per
platform, the URL of its build and that build's SHA-256; a Python tool names a requirements file
compiled with `uv pip compile --generate-hashes`, installed into a virtual environment of its own.
Each tool version installs under the user-level data root, and the commands it provides link
there, so a command on PATH is at its pin exactly when its link resolves into that directory.

A review records the lock's digest as one of its inputs: two reviews ran the same tools only when
their digests match.
"""

from __future__ import annotations

import functools
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from devops_cli.core.repo import user_data_root

LOCK_DIR = Path(__file__).resolve().parent
LOCK_FILENAME = "tools.lock"


class _LockEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Artifact(_LockEntry):
    """One platform's build of a binary tool: where it is fetched from and its SHA-256."""

    url: str
    sha256: str
    # The archive member that is the tool, for a tar.gz build.
    member: str | None = None


class BinaryTool(_LockEntry):
    """A tool published as a binary, a gzip file or a tar.gz archive per platform."""

    version: str
    description: str
    source: str
    bin: str
    format: Literal["binary", "gzip", "tar.gz"]
    # Builds by `<os>-<arch>`, such as `linux-amd64`.
    platforms: dict[str, Artifact]

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

    @property
    def commands(self) -> tuple[str, ...]:
        """The commands the tool puts on PATH."""
        return tuple(self.entry_points)


class ToolsLock(_LockEntry):
    """The whole lock."""

    # The Python each Python tool's virtual environment runs.
    python_version: str
    binary: dict[str, BinaryTool]
    python: dict[str, PythonTool]

    def tools(self) -> dict[str, BinaryTool | PythonTool]:
        """Every tool by name, binaries first, in the order the lock lists them."""
        return {**self.binary, **self.python}


def read_tools_lock(lock_dir: Path) -> ToolsLock:
    """The lock in `lock_dir`."""
    return ToolsLock.model_validate(tomllib.loads((lock_dir / LOCK_FILENAME).read_text("utf-8")))


@functools.cache
def load_tools_lock() -> ToolsLock:
    """The lock devops-cli ships."""
    return read_tools_lock(LOCK_DIR)


def tools_lock_digest(lock_dir: Path = LOCK_DIR) -> str:
    """A digest of the lock and its requirements files, in the form of the review prompt digest.

    Any change to a pin, a URL, a checksum or a hashed requirement changes it.
    """
    from devops_cli.ai.run_store import digest

    names = [
        LOCK_FILENAME,
        *(tool.requirements for tool in read_tools_lock(lock_dir).python.values()),
    ]
    return digest({name: (lock_dir / name).read_text(encoding="utf-8") for name in names})


def tool_install_dir(name: str, version: str) -> Path:
    """Where version `version` of tool `name` installs: a binary tool's file, or a Python tool's
    virtual environment."""
    return user_data_root() / "tools" / name / version


def installed_commands(name: str, tool: BinaryTool | PythonTool) -> dict[str, Path]:
    """Each command `tool` puts on PATH, and the file in its version directory it links to."""
    pinned = tool_install_dir(name, tool.version)
    directory = pinned / "bin" if isinstance(tool, PythonTool) else pinned
    return {command: directory / command for command in tool.commands}


__all__ = [
    "LOCK_DIR",
    "LOCK_FILENAME",
    "Artifact",
    "BinaryTool",
    "PythonTool",
    "ToolsLock",
    "installed_commands",
    "load_tools_lock",
    "read_tools_lock",
    "tool_install_dir",
    "tools_lock_digest",
]
