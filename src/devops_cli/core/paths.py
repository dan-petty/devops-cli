"""Path containment, secure traversal validation, and filesystem utilities."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TypeVar

from devops_cli.config.constants import CONST_FORBIDDEN_SYSTEM_DIRS
from devops_cli.exceptions import ValidationError
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.security import SecurityError

E = TypeVar("E", bound=DevOpsCLIError)


def _verify_no_symlinks(
    candidate: Path,
    base: Path,
    error_cls: type[DevOpsCLIError],
) -> None:
    """Verify that candidate path and its parent hierarchy contain no symbolic links."""
    current = candidate
    while True:
        if current.is_symlink():
            raise error_cls(
                f"Symlink rejected: '{current}' is a symbolic link and allow_symlinks is False."
            )
        if current == base or current.parent == current:
            break
        current = current.parent


def safe_resolve_subpath(
    base_dir: Path | str,
    subpath: Path | str,
    *,
    must_exist: bool = False,
    allow_symlinks: bool = False,
    error_cls: type[DevOpsCLIError] = SecurityError,
) -> Path:
    """Safely resolve and validate that subpath resides strictly within base_dir.

    Guards against relative directory traversal ('..'), absolute path overrides,
    and symlink directory escapes.

    Args:
        base_dir: Root anchor directory.
        subpath: Relative or absolute subpath to validate.
        must_exist: Whether the target path must already exist on disk.
        allow_symlinks: Whether to permit symbolic links within base_dir (all destinations must still reside strictly within base_dir).
        error_cls: Specific DevOpsCLIError subclass to raise upon violation.

    Returns:
        The safely resolved Path object strictly contained within base_dir.

    Raises:
        error_cls: If directory traversal or escape outside base_dir is detected.
        ValidationError: If must_exist is True and the target file/dir is missing.
    """
    base = Path(base_dir).resolve()
    raw_sub = str(subpath).strip()

    if not raw_sub:
        raise error_cls(f"Path traversal detected: empty subpath provided for base '{base}'.")

    if "\x00" in raw_sub or "\x00" in str(subpath):
        raise error_cls(f"Path traversal detected: null byte in path '{subpath}'.")

    # If subpath is absolute or relative, resolve against base
    try:
        candidate = Path(raw_sub)
        if not candidate.is_absolute():
            candidate = base / candidate
        resolved = candidate.resolve()
    except (ValueError, OSError, RuntimeError) as exc:
        raise error_cls(f"Failed to resolve path '{subpath}': {exc}") from exc

    # Enforce strict directory containment (symlinks or traversal outside base are never permitted)
    if not resolved.is_relative_to(base):
        raise error_cls(
            f"Path traversal detected: path '{subpath}' escapes base directory '{base}'."
        )

    # Symlink rejection when allow_symlinks=False
    if not allow_symlinks:
        _verify_no_symlinks(candidate, base, error_cls)

    # Existence verification
    if must_exist and not resolved.exists():
        raise ValidationError(
            f"Target path does not exist: '{resolved}'.",
            field="subpath",
        )

    return resolved


_ADDITIONAL_SYSTEM_DIRS: tuple[Path, ...] = (
    Path("/dev"),
    Path("/boot"),
)
_ALL_FORBIDDEN_SYSTEM_DIRS: tuple[Path, ...] = CONST_FORBIDDEN_SYSTEM_DIRS + _ADDITIONAL_SYSTEM_DIRS

_PATH_PARAM_KEYWORDS: tuple[str, ...] = (
    "path",
    "file",
    "dir",
    "dest",
    "target",
    "filename",
    "filepath",
    "uri",
)


def is_forbidden_system_path(path: Path | str) -> bool:
    """Return True if path resolves to a forbidden host system directory."""
    raw_str = str(path).strip()
    if not raw_str:
        return False
    p = Path(path)
    if not p.is_absolute():
        return False
    resolved = p.resolve()
    return any(
        resolved == sys_dir or resolved.is_relative_to(sys_dir)
        for sys_dir in _ALL_FORBIDDEN_SYSTEM_DIRS
    )


def validate_no_path_traversal(
    path: Path | str,
    *,
    error_cls: type[Exception] = SecurityError,
    label: str = "Path",
) -> Path:
    """Validate that a path string does not contain traversal sequences or escape attempts."""
    raw_str = str(path).strip()
    if not raw_str:
        raise error_cls(f"{label} traversal detected: empty path provided.")

    import urllib.parse

    unquoted = urllib.parse.unquote(raw_str)
    if "\x00" in raw_str or "\x00" in unquoted:
        raise error_cls(f"{label} traversal detected: null byte in path '{path}'.")

    parts = [part for part in re.split(r"[/\\]+", unquoted) if part]
    if any(part == ".." for part in parts):
        raise error_cls(
            f"Path traversal detected in {label}: '{path}' (cannot contain '..' traversal sequences)."
        )
    return Path(path)


def validate_path_parameter(
    param_name: str,
    value: Any,
    *,
    allow_absolute: bool = True,
    error_cls: type[Exception] = SecurityError,
) -> None:
    """Validate tool argument values named after path parameters against traversal and escapes."""
    if not isinstance(value, (str, Path)):
        return
    lower_name = param_name.lower()
    if not any(kw in lower_name for kw in _PATH_PARAM_KEYWORDS):
        return

    raw_str = str(value).strip()
    import urllib.parse

    unquoted = urllib.parse.unquote(raw_str)
    if "\x00" in raw_str or "\x00" in unquoted:
        raise error_cls(
            f"Path traversal sequence detected in parameter '{param_name}': null byte in path '{value}'."
        )

    parts = [part for part in re.split(r"[/\\]+", unquoted) if part]
    if any(part == ".." for part in parts):
        raise error_cls(f"Path traversal sequence detected in parameter '{param_name}': '{value}'.")

    if not allow_absolute:
        p = Path(unquoted)
        is_abs = (
            p.is_absolute()
            or raw_str.startswith(("/", "\\"))
            or unquoted.startswith(("/", "\\", "~"))
            or "://" in unquoted
        )
        if is_abs:
            raise error_cls(
                f"Absolute path in parameter '{param_name}' is blocked by security policy: '{value}'."
            )
