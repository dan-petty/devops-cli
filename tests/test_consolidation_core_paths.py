"""Unit tests for safe subpath containment and traversal defense (TDD Specification)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.core.paths import safe_resolve_subpath
from devops_cli.exceptions import ValidationError
from devops_cli.exceptions.security import SecurityError


def test_safe_resolve_subpath_valid(tmp_path: Path) -> None:
    """Resolves valid subpath cleanly within base directory."""
    child_file = tmp_path / "subdir" / "nested.txt"
    child_file.parent.mkdir(parents=True, exist_ok=True)
    child_file.write_text("hello", encoding="utf-8")

    res = safe_resolve_subpath(tmp_path, "subdir/nested.txt")
    assert res == child_file.resolve()


def test_safe_resolve_subpath_relative_traversal_blocked(tmp_path: Path) -> None:
    """Relative traversal ('../') attempting escape outside base raises SecurityError."""
    with pytest.raises(SecurityError) as exc_info:
        safe_resolve_subpath(tmp_path, "../../etc/shadow")
    assert "traversal" in str(exc_info.value).lower() or "escapes" in str(exc_info.value).lower()


def test_safe_resolve_subpath_absolute_path_escape_blocked(tmp_path: Path) -> None:
    """Absolute path pointing outside base directory raises SecurityError."""
    with pytest.raises(SecurityError) as exc_info:
        safe_resolve_subpath(tmp_path, "/etc/passwd")
    assert "traversal" in str(exc_info.value).lower() or "escapes" in str(exc_info.value).lower()


def test_safe_resolve_subpath_symlink_escape_blocked(tmp_path: Path) -> None:
    """Symlink pointing to target outside base directory raises SecurityError when allow_symlinks=False."""
    outside_dir = tmp_path.parent / "outside_dir"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")

    symlink_path = tmp_path / "link_to_outside"
    try:
        symlink_path.symlink_to(outside_file)
    except OSError:
        pytest.skip("Symlink creation not permitted in this test environment")

    with pytest.raises(SecurityError):
        safe_resolve_subpath(tmp_path, "link_to_outside", allow_symlinks=False)


def test_safe_resolve_subpath_must_exist(tmp_path: Path) -> None:
    """When must_exist=True, non-existent target raises ValidationError or SecurityError."""
    with pytest.raises((ValidationError, SecurityError)):
        safe_resolve_subpath(tmp_path, "non_existent_file.txt", must_exist=True)


def test_safe_resolve_subpath_custom_error_cls(tmp_path: Path) -> None:
    """Custom error class is raised when specified."""

    class CustomError(SecurityError):
        pass

    with pytest.raises(CustomError):
        safe_resolve_subpath(tmp_path, "../outside", error_cls=CustomError)
