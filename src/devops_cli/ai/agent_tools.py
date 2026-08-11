"""Built-in DevOps tools for PydanticAgent."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


def _is_safe_workspace_path(target: Path) -> bool:
    cwd = Path.cwd().resolve()
    target_resolved = target.resolve()
    return target_resolved == cwd or target_resolved.is_relative_to(cwd)


def list_files(directory: str = ".") -> list[str]:
    """List non-hidden files in the specified directory up to 2 levels deep."""
    root = Path(directory).resolve()
    if not _is_safe_workspace_path(root) or not root.exists() or not root.is_dir():
        return []
    results: list[str] = []
    for path in root.glob("*"):
        if path.name.startswith(".") or path.name == "__pycache__":
            continue
        if not _is_safe_workspace_path(path.resolve()):
            continue
        if path.is_file():
            results.append(path.name)
        elif path.is_dir():
            for child in path.glob("*"):
                if child.name.startswith(".") or child.name == "__pycache__":
                    continue
                if not _is_safe_workspace_path(child.resolve()):
                    continue
                results.append(f"{path.name}/{child.name}")
    return sorted(results)[:100]


def read_file(path: str, max_bytes: int = 4000) -> str:
    """Read contents of a text file up to max_bytes."""
    file_path = Path(path).resolve()
    if not _is_safe_workspace_path(file_path):
        logger.warning("Access denied attempting to read path outside workspace: %s", path)
        return f"Access Denied: {path} is outside workspace."
    if not file_path.exists() or not file_path.is_file():
        return f"File not found: {path}"
    try:
        file_size = file_path.stat().st_size
        bytes_to_read = min(file_size, max_bytes + 1)
        with open(file_path, "rb") as f:
            raw = f.read(bytes_to_read)
        logger.debug("Read %d bytes from %s", len(raw), path)
        if len(raw) > max_bytes:
            return (
                raw[:max_bytes].decode("utf-8", errors="replace")
                + f"\n... [truncated at {max_bytes} bytes]"
            )
        return raw.decode("utf-8", errors="replace")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Error reading file %s: %s", path, exc)
        return f"Error reading file: {exc}"


def git_status() -> str:
    """Return current git status summary."""
    try:
        res = subprocess.run(
            ["git", "status", "-s"],
            capture_output=True,
            text=True,
            check=False,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        logger.debug("Executed git_status (returncode=%d)", res.returncode)
        return res.stdout.strip() or "Working tree clean."
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("git_status failed: %s", exc)
        return f"Git status failed: {exc}"


def git_diff() -> str:
    """Return current unstaged git diff up to 4000 characters."""
    try:
        res = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
            check=False,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        output = res.stdout.strip()
        logger.debug("Executed git_diff (output_len=%d)", len(output))
        if len(output) > 4000:
            return output[:4000] + "\n... [diff truncated]"
        return output or "No unstaged changes."
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("git_diff failed: %s", exc)
        return f"Git diff failed: {exc}"


def get_default_tools() -> list[Any]:
    """Return standard set of agent tools."""
    return [list_files, read_file, git_status, git_diff]
