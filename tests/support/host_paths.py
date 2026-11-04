"""The host paths a test may open under the hermetic floor (#2165, #3124).

The root conftest's file open guard asks this module whether a path is denied or allowed. It
lives here, not in the conftest, so a test can hold it to its rules: no test module imports a
conftest.
"""

from __future__ import annotations

import os
import sys
import sysconfig
import tempfile
from pathlib import Path

from devops_cli.core.repo import _linked_worktree_common_dir

_ALLOWED_FILES = (
    "/etc/ld.so.cache",
    "/etc/localtime",
    "/etc/os-release",
    "/etc/machine-id",
    "/var/lib/dbus/machine-id",
    "/usr/lib/os-release",
)
_ALLOWED_PREFIXES = (
    "/bin/",
    "/usr/bin/",
    "/usr/local/bin/",
    "/sbin/",
    "/usr/sbin/",
    "/usr/lib",
    "/usr/local/lib",
    "/opt/lib",
    "/opt/scanners",
    "/usr/lib64",
    "/lib",
    "/lib64",
    "/usr/share",
)


def is_denied_host_path(norm: str, raw: str) -> bool:
    """Report whether a path points to /proc or /usr/local/share/tiktoken (#2165)."""
    if norm == "/proc" or norm.startswith("/proc/"):
        return True
    if norm == "/usr/local/share/tiktoken" or norm.startswith("/usr/local/share/tiktoken/"):
        return True
    if raw.startswith("/proc") or raw.startswith("/usr/local/share/tiktoken"):
        return True
    return False


def checkout_roots(repo_root: Path) -> tuple[Path, ...]:
    """The directories of the checkout at `repo_root` that a test may open: the checkout, and
    for a linked worktree the common git directory, which holds the worktree's own git
    directory with its `HEAD` file (#3124). No `git` process finds it: the worktree's `.git`
    file names its git directory, and that holds a `commondir` file.
    """
    common_dir = _linked_worktree_common_dir(repo_root)
    return (repo_root.resolve(), *((common_dir,) if common_dir is not None else ()))


def allowed_host_roots(repo_root: Path) -> tuple[Path, ...]:
    """Collect the allowed checkout, temporary, and interpreter directory roots (#2165)."""
    allowed_roots: list[Path] = [
        *checkout_roots(repo_root),
        Path(tempfile.gettempdir()).resolve(),
        Path(os.sep).joinpath("tmp").resolve(),
        Path(os.sep).joinpath("var", "tmp").resolve(),
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve(),
        Path(sys.exec_prefix).resolve(),
        Path(sys.base_exec_prefix).resolve(),
        Path(sys.executable).resolve().parent,
    ]
    for p in sys.path:
        if p:
            try:
                allowed_roots.append(Path(p).resolve())
            except OSError:
                pass
    for path_name in ("stdlib", "purelib", "platlib", "data"):
        try:
            allowed_roots.append(Path(sysconfig.get_path(path_name)).resolve())
        except Exception:
            pass
    return tuple(dict.fromkeys(allowed_roots))


def is_allowed_host_path(raw_path: str, unique_roots: tuple[Path, ...]) -> bool:
    """Check whether a path is allowed under the hermetic floor (#2165)."""
    if raw_path.startswith("/dev/"):
        return True
    if raw_path in _ALLOWED_FILES or raw_path.startswith("/usr/share/zoneinfo"):
        return True
    if (
        raw_path.startswith(_ALLOWED_PREFIXES)
        or "/site-packages" in raw_path
        or "/dist-packages" in raw_path
    ):
        return True

    try:
        resolved = Path(raw_path).resolve()
    except Exception:
        resolved = Path(os.path.abspath(raw_path))

    for root in unique_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            pass
    return False
