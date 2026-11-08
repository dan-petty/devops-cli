"""Explain a slow quality gate: the workspace's filesystem and the tests that took longest."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from devops_cli.config.constants import CONST_SLOW_WORKSPACE_FSTYPES
from devops_cli.core.repo import is_stale_linked_worktree
from devops_cli.lang import MESSAGES

_PROC_MOUNTS = Path("/proc/mounts")
_MOUNT_ESCAPE = re.compile(r"\\([0-7]{3})")


def _decode_mount_point(field: str) -> str:
    """Decode the octal escapes /proc/mounts writes for spaces, tabs and backslashes."""
    return _MOUNT_ESCAPE.sub(lambda match: chr(int(match.group(1), 8)), field)


def slow_mount_fstype(path: Path, mounts_text: str | None = None) -> str | None:
    """Return the filesystem type holding `path` when it is a slow host-folder share, else None.

    The most specific mount point containing `path` decides, so a Linux volume mounted inside
    a host share (the devcontainer's `.data` and `.venv`) is not reported.
    """
    if mounts_text is None:
        try:
            mounts_text = _PROC_MOUNTS.read_text(encoding="utf-8")
        except OSError:
            return None
    target = str(path.resolve())
    best_point, best_type = "", ""
    for line in mounts_text.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        point = _decode_mount_point(fields[1])
        inside = target == point or target.startswith(point.rstrip("/") + "/")
        if inside and len(point) > len(best_point):
            best_point, best_type = point, fields[2]
    return best_type if best_type in CONST_SLOW_WORKSPACE_FSTYPES else None


def gate_root_warnings(root: Path, mounts_text: str | None = None) -> list[str]:
    """The warnings the gate gives for the tree it checks, in order: a linked worktree whose
    repository no longer knows it, and a workspace on a slow host-folder share (`mounts_text`
    stands for /proc/mounts)."""
    warnings: list[str] = []
    if is_stale_linked_worktree(root):
        warnings.append(
            MESSAGES.ci.gate_root_stale.format(root=root, root_arg=shlex.quote(str(root)))
        )
    if fstype := slow_mount_fstype(root, mounts_text):
        warnings.append(MESSAGES.ci.gate_root_slow_mount.format(root=root, fstype=fstype))
    return warnings


def slowest_tests(pytest_output: str) -> list[str]:
    """Return the entries of pytest's `--durations` report found in its terminal output."""
    lines = pytest_output.splitlines()
    for index, line in enumerate(lines):
        if "slowest" in line and "durations" in line:
            report: list[str] = []
            for entry in lines[index + 1 :]:
                if not entry.strip() or entry.startswith("="):
                    break
                report.append(entry.strip())
            return report
    return []
