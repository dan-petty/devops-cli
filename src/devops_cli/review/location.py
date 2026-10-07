"""Location validation and region hash computation for review findings (#871).

Validates physical regions against git commit trees and logical locations
against manifests and lockfiles.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocationValidationResult:
    """Outcome of validating a candidate finding's location."""

    valid: bool
    rejection_reason: str | None = None
    normalized_path: str = ""
    start_line: int | None = None
    end_line: int | None = None
    region_sha256: str | None = None
    logical_location: str | None = None


def normalize_finding_path(path: str, worktree_root: Path | None = None) -> tuple[str, bool]:
    """Normalize finding path, converting worktree-absolute paths to relative.

    Returns:
        (normalized_path, is_valid)
    """
    clean = path.strip()
    if not clean:
        return "", False

    p = Path(clean)
    if p.is_absolute():
        if worktree_root is not None:
            try:
                rel = p.resolve().relative_to(worktree_root.resolve())
                return rel.as_posix(), True
            except ValueError, RuntimeError:
                return clean, False
        return clean, False

    posix = clean.replace("\\", "/").lstrip("/")
    if posix.startswith("./"):
        posix = posix[2:]
    return posix, True


def compute_region_sha256(file_content: str, start_line: int, end_line: int | None = None) -> str:
    """Compute SHA-256 hash of the line region in file_content."""
    lines = file_content.splitlines()
    e_line = end_line if end_line is not None else start_line
    region_lines = lines[start_line - 1 : e_line]
    region_text = "\n".join(region_lines)
    return hashlib.sha256(region_text.encode("utf-8")).hexdigest()


def validate_location(
    *,
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    logical_location: str | None = None,
    worktree_root: Path | None = None,
    commit_files: set[str],
    file_content_getter: Callable[[str], str | None] | None = None,
    manifest_objects: set[str] | None = None,
    lockfile_packages: set[str] | None = None,
) -> LocationValidationResult:
    """Validate that candidate finding location exists in the reviewed commit tree."""
    norm_path, path_ok = normalize_finding_path(path, worktree_root)
    if not path_ok or (norm_path not in commit_files and norm_path != ""):
        return LocationValidationResult(
            valid=False,
            rejection_reason="path-not-in-commit",
            normalized_path=norm_path,
        )

    file_content = None
    if norm_path and file_content_getter:
        file_content = file_content_getter(norm_path)

    region_sha: str | None = None
    if start_line is not None:
        if file_content is None:
            return LocationValidationResult(
                valid=False,
                rejection_reason="path-not-in-commit",
                normalized_path=norm_path,
            )
        lines = file_content.splitlines()
        num_lines = len(lines)
        eff_end = end_line if end_line is not None else start_line

        if start_line < 1 or start_line > num_lines or eff_end < start_line or eff_end > num_lines:
            return LocationValidationResult(
                valid=False,
                rejection_reason="line-out-of-range",
                normalized_path=norm_path,
                start_line=start_line,
                end_line=end_line,
            )
        region_sha = compute_region_sha256(file_content, start_line, eff_end)

    if logical_location and logical_location.strip():
        loc_str = logical_location.strip()
        if "/" in loc_str and manifest_objects is not None and loc_str not in manifest_objects:
            return LocationValidationResult(
                valid=False,
                rejection_reason="object-not-in-commit",
                normalized_path=norm_path,
                logical_location=loc_str,
            )
        if "@" in loc_str and lockfile_packages is not None and loc_str not in lockfile_packages:
            return LocationValidationResult(
                valid=False,
                rejection_reason="object-not-in-commit",
                normalized_path=norm_path,
                logical_location=loc_str,
            )

    return LocationValidationResult(
        valid=True,
        normalized_path=norm_path,
        start_line=start_line,
        end_line=end_line,
        region_sha256=region_sha,
        logical_location=logical_location,
    )
