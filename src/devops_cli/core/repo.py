"""Repository path resolution, dynamic gitignore reading, and workspace utilities."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pathspec

from devops_cli.config.constants import CONST_BINARY_EXTENSIONS
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_FAST_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import SecurityError


@functools.lru_cache(maxsize=32)
def _get_pathspec_for_repo(repo_root_str: str) -> pathspec.PathSpec[Any] | None:
    """Compile and cache PathSpec instance for a repository root."""
    patterns = read_gitignore_patterns(Path(repo_root_str))
    if not patterns:
        return None
    import pathspec

    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def find_repo_root(start_path: Path | str | None = None) -> Path:
    """Find the root directory of the repository containing .git or pyproject.toml."""
    current = Path(start_path or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for parent in [current, *current.parents]:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent

    return current


def find_top_level_repo_root(start_path: Path | str | None = None) -> Path:
    """Find the top-most workspace root directory containing .git or pyproject.toml."""
    current = Path(start_path or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    candidates = [
        p
        for p in [current, *current.parents]
        if (p / ".git").exists() or (p / "pyproject.toml").exists()
    ]
    if candidates:
        return candidates[-1]

    return current


def read_gitignore_patterns(repo_root: Path) -> list[str]:
    """Dynamically read .gitignore patterns from the repository root at runtime."""
    gitignore_file = repo_root / ".gitignore"
    if not gitignore_file.is_file():
        return []

    try:
        return [
            line.strip()
            for line in gitignore_file.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    except Exception:
        return []


def is_ignored_by_git(repo_root: Path, target_path: Path) -> bool:
    """Dynamically check if target_path is ignored by git or runtime .gitignore rules."""
    if target_path.suffix.lower() in CONST_BINARY_EXTENSIONS:
        return True

    rel_parts = (
        target_path.relative_to(repo_root).parts
        if target_path.is_relative_to(repo_root)
        else target_path.parts
    )
    if ".git" in rel_parts:
        return True

    # 1. Fast in-memory matching against cached gitignore rules
    spec = _get_pathspec_for_repo(str(repo_root.resolve()))
    rel_str = (
        str(target_path.relative_to(repo_root))
        if target_path.is_relative_to(repo_root)
        else target_path.name
    )
    if spec is not None and spec.match_file(rel_str):
        return True

    # 2. Fallback check directly with git if inside a repository
    if (repo_root / ".git").exists():
        try:
            rel = (
                target_path.relative_to(repo_root)
                if target_path.is_relative_to(repo_root)
                else target_path
            )
            res = run_subprocess(
                ["git", "-C", str(repo_root), "check-ignore", "-q", "--", str(rel)],
                capture_output=True,
                check=False,
                quiet=True,
                timeout=DEFAULT_SUBPROCESS_FAST_TIMEOUT_SECONDS,
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass

    return False


def _list_git_tracked_files(repo_root: Path, resolved_target: Path) -> list[Path] | None:
    """List files using git ls-files if inside a git repository."""
    if not (repo_root / ".git").exists():
        return None
    try:
        cmd = [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
        ]
        if resolved_target != repo_root:
            rel_to_repo = resolved_target.relative_to(repo_root)
            cmd.extend(["--", str(rel_to_repo)])

        proc = run_subprocess(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_FAST_TIMEOUT_SECONDS,
        )
        files: list[Path] = []
        for line in proc.stdout.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            p = repo_root / line_str
            if p.is_file() and p.suffix.lower() not in CONST_BINARY_EXTENSIONS:
                files.append(p)
        return sorted(files)
    except Exception:
        return None


def list_repo_files(target: Path | str = ".") -> list[Path]:
    """Return all reviewable files under target directory respecting .gitignore rules."""
    resolved_target = Path(target).resolve()
    if not resolved_target.exists():
        return []

    repo_root = find_repo_root(resolved_target)

    if resolved_target.is_file():
        return [resolved_target] if not is_ignored_by_git(repo_root, resolved_target) else []

    # 1. Try git ls-files if inside a git repository
    git_files = _list_git_tracked_files(repo_root, resolved_target)
    if git_files is not None:
        return git_files

    # 2. Directory walk with dynamic .gitignore rules fallback
    walked_files: list[Path] = []
    repo_root_resolved = repo_root.resolve()
    for p in resolved_target.rglob("*"):
        if p.is_symlink():
            try:
                resolved_p = p.resolve()
                if not str(resolved_p).startswith(str(repo_root_resolved)):
                    continue
            except OSError, RuntimeError:
                continue
        if p.is_file() and not is_ignored_by_git(repo_root, p):
            walked_files.append(p)
    return sorted(walked_files)


def get_repo_origin_name(repo_root: Path | None = None) -> str | None:
    """Extract owner/repo string from git remote origin URL (e.g. 'org/repo')."""
    import re

    from devops_cli.core.process import run_subprocess

    root = repo_root or find_repo_root()
    if not (root / ".git").exists():
        return None

    proc = run_subprocess(["git", "remote", "get-url", "origin"], cwd=root, quiet=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None

    raw = proc.stdout.strip()
    match = re.search(r"[:/]([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+?)(?:\.git)?$", raw)
    return match.group(1) if match else None


def is_safe_subpath(root: Path | str, target: Path | str) -> bool:
    """Return True if *target* strictly resides within *root* directory hierarchy."""
    try:
        resolved_root = Path(root).resolve()
        target_p = Path(target)
        resolved_target = (
            (resolved_root / target_p).resolve()
            if not target_p.is_absolute()
            else target_p.resolve()
        )
        return resolved_target.is_relative_to(resolved_root)
    except Exception:
        return False


def resolve_safe_subpath(root: Path | str, target: Path | str) -> Path:
    """Resolve *target* relative to *root* and verify it strictly resides within *root*.

    Raises ValueError if path traversal outside *root* is detected.
    """
    resolved_root = Path(root).resolve()
    target_p = Path(target)
    resolved_target = (
        (resolved_root / target_p).resolve() if not target_p.is_absolute() else target_p.resolve()
    )
    if not resolved_target.is_relative_to(resolved_root):
        raise SecurityError(
            f"Path traversal detected: target '{resolved_target}' "
            f"resolves outside root '{resolved_root}'"
        )
    return resolved_target
