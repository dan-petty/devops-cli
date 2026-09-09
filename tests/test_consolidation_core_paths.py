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


def test_safe_resolve_subpath_external_symlink_blocked_even_with_allow_symlinks(
    tmp_path: Path,
) -> None:
    """Even when allow_symlinks=True, symlinks pointing outside base_dir are strictly blocked."""
    outside_dir = tmp_path.parent / "outside_dir_allowed"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")

    symlink_path = tmp_path / "link_to_outside_allowed"
    try:
        symlink_path.symlink_to(outside_file)
    except OSError:
        pytest.skip("Symlink creation not permitted in this test environment")

    with pytest.raises(SecurityError):
        safe_resolve_subpath(tmp_path, "link_to_outside_allowed", allow_symlinks=True)


def test_safe_resolve_subpath_internal_symlink_allowed(tmp_path: Path) -> None:
    """When allow_symlinks=True, symlinks pointing inside base_dir are safely permitted."""
    internal_file = tmp_path / "target.txt"
    internal_file.write_text("internal", encoding="utf-8")

    symlink_path = tmp_path / "link_internal"
    try:
        symlink_path.symlink_to(internal_file)
    except OSError:
        pytest.skip("Symlink creation not permitted in this test environment")

    # allow_symlinks=True succeeds
    resolved = safe_resolve_subpath(tmp_path, "link_internal", allow_symlinks=True)
    assert resolved == internal_file.resolve()

    # allow_symlinks=False rejects any symlink
    with pytest.raises(SecurityError) as exc_info:
        safe_resolve_subpath(tmp_path, "link_internal", allow_symlinks=False)
    assert "symlink" in str(exc_info.value).lower()


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


def test_is_forbidden_system_path() -> None:
    """Verify system directory identification."""
    from devops_cli.core.paths import is_forbidden_system_path

    assert is_forbidden_system_path("/etc") is True
    assert is_forbidden_system_path("/etc/shadow") is True
    assert is_forbidden_system_path("/sys/kernel") is True
    assert is_forbidden_system_path("/proc/cpuinfo") is True
    assert is_forbidden_system_path("/dev/null") is True
    assert is_forbidden_system_path("/bin/sh") is True
    assert is_forbidden_system_path("/sbin/iptables") is True
    assert is_forbidden_system_path("/usr/bin/python3") is True

    assert is_forbidden_system_path("/workspaces/devops-cli/src") is False
    assert is_forbidden_system_path("relative/path/to/file.txt") is False


def test_validate_no_path_traversal() -> None:
    """Verify traversal rejection for strings and paths."""
    from devops_cli.core.paths import validate_no_path_traversal

    class CustomTraversalError(Exception):
        pass

    assert validate_no_path_traversal("safe/sub/path.txt") == Path("safe/sub/path.txt")
    assert validate_no_path_traversal(Path("safe/path.json")) == Path("safe/path.json")

    with pytest.raises(SecurityError, match="traversal"):
        validate_no_path_traversal("../secret.txt")

    with pytest.raises(CustomTraversalError, match="traversal"):
        validate_no_path_traversal(
            "dir/../../escaped", error_cls=CustomTraversalError, label="Target file"
        )

    # URL-encoded traversal
    with pytest.raises(SecurityError, match="traversal"):
        validate_no_path_traversal("%2e%2e/encoded")


def test_validate_path_parameter() -> None:
    """Verify tool parameter inspection against path traversal and escapes."""
    from devops_cli.core.paths import validate_path_parameter

    # Non-path parameter is ignored
    validate_path_parameter("user_name", "../not-a-path-param")

    # Safe path parameter
    validate_path_parameter("file_path", "src/devops_cli/main.py")
    validate_path_parameter("dest_dir", Path("build/output"))

    # Traversal in path param
    with pytest.raises(SecurityError, match="traversal"):
        validate_path_parameter("target_path", "../../../etc/passwd")

    with pytest.raises(SecurityError, match="traversal"):
        validate_path_parameter("dest", "sub/%2e%2e/escape")

    # Absolute path blocked when allow_absolute=False
    with pytest.raises(SecurityError, match=r"(?i)absolute path"):
        validate_path_parameter("output_file", "/etc/passwd", allow_absolute=False)
