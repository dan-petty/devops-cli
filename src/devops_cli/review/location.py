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


def _check_logical_location(
    loc_str: str,
    manifest_objects: set[str] | None,
    lockfile_packages: set[str] | None,
) -> str | None:
    """Return rejection reason if logical location does not exist in manifests or lockfiles."""
    if "/" in loc_str and manifest_objects is not None and loc_str not in manifest_objects:
        return "object-not-in-commit"
    if "@" in loc_str and lockfile_packages is not None and loc_str not in lockfile_packages:
        return "object-not-in-commit"
    return None


def _validate_empty_path_location(
    clean_logical: str,
    manifest_objects: set[str] | None,
) -> LocationValidationResult:
    """Validate a candidate finding that has only a logical location and no physical path (#1352)."""
    if not clean_logical:
        return LocationValidationResult(
            valid=False,
            rejection_reason="path-not-in-commit",
            normalized_path="",
        )
    if manifest_objects is None or clean_logical not in manifest_objects:
        return LocationValidationResult(
            valid=False,
            rejection_reason="object-not-in-commit",
            normalized_path="",
            logical_location=clean_logical,
        )
    return LocationValidationResult(
        valid=True,
        normalized_path="",
        logical_location=clean_logical,
    )


def _validate_line_range(
    file_content: str | None,
    start_line: int,
    end_line: int | None,
) -> tuple[str | None, str | None]:
    """Validate line bounds and return (region_sha256, rejection_reason)."""
    if file_content is None:
        return None, "path-not-in-commit"
    lines = file_content.splitlines()
    num_lines = len(lines)
    eff_end = end_line if end_line is not None else start_line
    if start_line < 1 or start_line > num_lines or eff_end < start_line or eff_end > num_lines:
        return None, "line-out-of-range"
    return compute_region_sha256(file_content, start_line, eff_end), None


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
    clean_path = path.strip()
    clean_logical = logical_location.strip() if logical_location else ""

    if not clean_path:
        return _validate_empty_path_location(clean_logical, manifest_objects)

    norm_path, path_ok = normalize_finding_path(clean_path, worktree_root)
    if not path_ok or norm_path not in commit_files:
        return LocationValidationResult(
            valid=False,
            rejection_reason="path-not-in-commit",
            normalized_path=norm_path,
        )

    region_sha: str | None = None
    if start_line is not None:
        file_content = file_content_getter(norm_path) if file_content_getter else None
        region_sha, line_err = _validate_line_range(file_content, start_line, end_line)
        if line_err:
            return LocationValidationResult(
                valid=False,
                rejection_reason=line_err,
                normalized_path=norm_path,
                start_line=start_line,
                end_line=end_line,
            )

    if clean_logical:
        err = _check_logical_location(clean_logical, manifest_objects, lockfile_packages)
        if err:
            return LocationValidationResult(
                valid=False,
                rejection_reason=err,
                normalized_path=norm_path,
                logical_location=clean_logical,
            )

    return LocationValidationResult(
        valid=True,
        normalized_path=norm_path,
        start_line=start_line,
        end_line=end_line,
        region_sha256=region_sha,
        logical_location=logical_location,
    )
