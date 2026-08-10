"""Built-in DevOps tools for PydanticAgent."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def list_files(directory: str = ".") -> list[str]:
    """List non-hidden files in the specified directory up to 2 levels deep."""
    root = Path(directory).resolve()
    if not root.exists() or not root.is_dir():
        return []
    results: list[str] = []
    for path in root.glob("*"):
        if path.name.startswith(".") or path.name == "__pycache__":
            continue
        if path.is_file():
            results.append(path.name)
        elif path.is_dir():
            for child in path.glob("*"):
                if child.name.startswith(".") or child.name == "__pycache__":
                    continue
                results.append(f"{path.name}/{child.name}")
    return sorted(results)[:100]


def read_file(path: str, max_bytes: int = 4000) -> str:
    """Read contents of a text file up to max_bytes."""
    file_path = Path(path).resolve()
    if not file_path.exists() or not file_path.is_file():
        return f"File not found: {path}"
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_bytes:
            return content[:max_bytes] + f"\n... [truncated at {max_bytes} bytes]"
        return content
    except Exception as exc:
        return f"Error reading file: {exc}"


def git_status() -> str:
    """Return current git status summary."""
    try:
        res = subprocess.run(["git", "status", "-s"], capture_output=True, text=True, check=False)
        return res.stdout.strip() or "Working tree clean."
    except Exception as exc:
        return f"Git status failed: {exc}"


def git_diff() -> str:
    """Return current unstaged git diff up to 4000 characters."""
    try:
        res = subprocess.run(["git", "diff"], capture_output=True, text=True, check=False)
        output = res.stdout.strip()
        if len(output) > 4000:
            return output[:4000] + "\n... [diff truncated]"
        return output or "No unstaged changes."
    except Exception as exc:
        return f"Git diff failed: {exc}"


def get_default_tools() -> list[Any]:
    """Return standard set of agent tools."""
    return [list_files, read_file, git_status, git_diff]
