"""Path containment, secure traversal validation, and filesystem utilities."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from devops_cli.exceptions import ValidationError
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.security import SecurityError

E = TypeVar("E", bound=DevOpsCLIError)


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
        allow_symlinks: Whether to allow symlinks pointing outside base_dir.
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

    # If subpath is absolute or relative, resolve against base
    candidate = Path(raw_sub)
    if not candidate.is_absolute():
        candidate = base / candidate

    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as exc:
        raise error_cls(f"Failed to resolve path '{subpath}': {exc}") from exc

    # Enforce strict directory containment
    if not resolved.is_relative_to(base):
        raise error_cls(
            f"Path traversal detected: path '{subpath}' escapes base directory '{base}'."
        )

    # Symlink escape verification
    if not allow_symlinks:
        current = candidate
        while True:
            if current.is_symlink():
                target_dest = current.resolve()
                if not target_dest.is_relative_to(base):
                    raise error_cls(
                        f"Symlink escape detected: '{current}' points outside base directory '{base}'."
                    )
            if current == base or current.parent == current:
                break
            current = current.parent

    # Existence verification
    if must_exist and not resolved.exists():
        raise ValidationError(
            f"Target path does not exist: '{resolved}'.",
            field="subpath",
        )

    return resolved
