"""Review target discovery, candidate file filtering, and path routing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path, PurePath, PurePosixPath

from devops_cli.config.constants import (
    CONST_BINARY_EXTENSIONS,
    CONST_MAX_FILE_SIZE_BYTES,
    CONST_REVIEW_GENERATED_FILES,
    CONST_REVIEW_ROUTED_PATH_PATTERNS,
)
from devops_cli.config.defaults import DEFAULT_MATCH_ALL_PATTERN
from devops_cli.core.repo import is_ignored_by_git
from devops_cli.exceptions import SecurityError


def is_secret_scan_only(
    path: str | PurePath,
    path_classes: Mapping[str, Sequence[str]] | None = None,
) -> bool:
    """Whether a file stays off review blocks and reaches the secret scan alone, by its
    repository-relative path (#948, #1151).

    Lockfiles stay off for their size. Planning documents (the changelog, ADRs and OpenSpec
    files) and generated references (`docs/commands/`, the CLI reference) stay off because no
    model finding on them held up. Path, branch and pull request
    reviews all decide with this predicate, and the secret scan still reads what it skips.
    """
    from devops_cli.ai.review.path_classes import is_fixture_path

    posix = PurePosixPath(str(path).replace("\\", "/").removeprefix("./"))
    if is_fixture_path(posix, path_classes=path_classes):
        return True
    return posix.name in CONST_REVIEW_GENERATED_FILES or any(
        posix.full_match(pattern) for pattern in CONST_REVIEW_ROUTED_PATH_PATTERNS
    )


def _is_reviewable_candidate_file(
    candidate: Path,
    root: Path,
    max_file_size: int,
    excluded_dirs: set[str] | None = None,
) -> bool:
    """Check if candidate file meets review criteria (non-symlink, within root, text, non-ignored)."""
    if candidate.is_symlink() or not candidate.is_file():
        return False
    # A pattern with a directory part follows a symlinked directory, so a candidate that is no
    # symlink can still have its real path outside the root. A non-strict resolve raises no
    # error for a missing path, a loop or a denied directory.
    if not candidate.resolve().is_relative_to(root):
        return False
    if excluded_dirs and any(part in excluded_dirs for part in candidate.parts):
        return False
    if is_ignored_by_git(root, candidate):
        return False
    if candidate.suffix.lower() in CONST_BINARY_EXTENSIONS:
        return False
    try:
        if candidate.stat().st_size > max_file_size:
            return False
    except OSError:
        return False
    return True


def find_repo_files(
    target: Path,
    pattern: str = DEFAULT_MATCH_ALL_PATTERN,
    max_file_size: int = CONST_MAX_FILE_SIZE_BYTES,
    excluded_dirs: set[str] | None = None,
    repo_root: Path | None = None,
) -> list[Path]:
    """Discover reviewable source files under target, skipping binary and symlinked paths."""
    root = (repo_root or target).resolve()
    target_resolved = target.resolve()
    if not target_resolved.is_relative_to(root):
        raise SecurityError("target must be a sub-path of the repository root")

    if target.is_file():
        return [] if target.is_symlink() else [target]

    return [
        p
        for p in sorted(target.rglob(pattern))
        if _is_reviewable_candidate_file(p, root, max_file_size, excluded_dirs=excluded_dirs)
    ]


__all__ = [
    "find_repo_files",
    "is_secret_scan_only",
]
