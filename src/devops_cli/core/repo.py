"""Repository path resolution, dynamic gitignore reading, and workspace utilities."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

_BINARY_EXTENSIONS: set[str] = {
    ".pyc",
    ".pyo",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".db",
    ".sqlite",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".7z",
    ".rar",
    ".log",
}


def find_repo_root(start_path: Path | str | None = None) -> Path:
    """Find the root directory of the repository containing .git or pyproject.toml."""
    current = Path(start_path or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for parent in [current, *current.parents]:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent

    return current


def read_gitignore_patterns(repo_root: Path) -> list[str]:
    """Dynamically read .gitignore patterns from the repository root at runtime."""
    gitignore_file = repo_root / ".gitignore"
    if not gitignore_file.is_file():
        return []

    patterns: list[str] = []
    try:
        content = gitignore_file.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            line_str = line.strip()
            if line_str and not line_str.startswith("#"):
                patterns.append(line_str)
    except Exception:
        pass
    return patterns


def is_ignored_by_git(repo_root: Path, target_path: Path) -> bool:
    """Dynamically check if target_path is ignored by git or runtime .gitignore rules."""
    if target_path.suffix.lower() in _BINARY_EXTENSIONS:
        return True

    rel_parts = (
        target_path.relative_to(repo_root).parts
        if target_path.is_relative_to(repo_root)
        else target_path.parts
    )
    if ".git" in rel_parts:
        return True

    # 1. Ask git directly if inside a git repository
    if (repo_root / ".git").exists():
        try:
            rel = (
                target_path.relative_to(repo_root)
                if target_path.is_relative_to(repo_root)
                else target_path
            )
            res = subprocess.run(
                ["git", "-C", str(repo_root), "check-ignore", "-q", "--", str(rel)],
                capture_output=True,
                check=False,
                timeout=5,
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # 2. Dynamic runtime fallback: match against dynamically loaded .gitignore rules
    patterns = read_gitignore_patterns(repo_root)
    if not patterns:
        return False

    rel_str = (
        str(target_path.relative_to(repo_root))
        if target_path.is_relative_to(repo_root)
        else target_path.name
    )
    for pat in patterns:
        clean_pat = pat.rstrip("/")
        if clean_pat.startswith("/"):
            clean_pat = clean_pat[1:]
        if fnmatch.fnmatch(rel_str, clean_pat) or fnmatch.fnmatch(target_path.name, clean_pat):
            return True
        for part in rel_parts:
            if fnmatch.fnmatch(part, clean_pat):
                return True

    return False


def list_repo_files(target_dir: Path) -> list[Path]:
    """Return non-git-ignored source files using dynamic git ls-files or .gitignore."""
    resolved_target = target_dir.resolve()
    repo_root = find_repo_root(resolved_target)

    if resolved_target.is_file():
        return [resolved_target] if not is_ignored_by_git(repo_root, resolved_target) else []

    # 1. Try git ls-files if inside a git repository
    if (repo_root / ".git").exists():
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

            proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
            files: list[Path] = []
            for line in proc.stdout.splitlines():
                line_str = line.strip()
                if line_str:
                    p = repo_root / line_str
                    if p.is_file() and p.suffix.lower() not in _BINARY_EXTENSIONS:
                        files.append(p)
            return sorted(files)
        except Exception:
            pass

    # 2. Directory walk with dynamic .gitignore rules fallback
    walked_files: list[Path] = []
    for p in resolved_target.rglob("*"):
        if p.is_file() and not is_ignored_by_git(repo_root, p):
            walked_files.append(p)
    return sorted(walked_files)
