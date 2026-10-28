"""Base domain exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any, cast

from devops_cli.config.constants import CONST_EXIT_FAILURE


def _sanitize_exception_details(details: dict[str, Any] | None) -> dict[str, Any]:
    """Recursively mask secrets and credentials in exception details dictionaries."""
    if not details:
        return {}
    from devops_cli.security.sanitizer import mask_dict_secrets

    return cast(dict[str, Any], mask_dict_secrets(details))


class DevOpsCLIError(Exception):
    """Root base exception for all domain-specific errors in devops-cli.

    Each subclass declares its `error_code` and `exit_code` as class attributes, and a
    subclass that declares neither keeps its base's. An instance takes its class's codes;
    `exit_code=` overrides the exit status of one instance, as when a subprocess's own
    status is the command's.

    Attributes:
        message: Human-readable error explanation (automatically sanitized).
        exit_code: POSIX process exit status code (defaults to 1).
        error_code: Canonical machine-readable identifier string.
        details: Optional structured dictionary containing contextual debug data (automatically sanitized).
    """

    error_code: str = "DEVOPS_CLI_ERROR"
    exit_code: int = CONST_EXIT_FAILURE

    def __init__(
        self,
        message: str,
        *,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        from devops_cli.security.sanitizer import mask_secrets

        clean_message = mask_secrets(message)
        super().__init__(clean_message)
        self.message = clean_message
        if exit_code is not None:
            self.exit_code = exit_code
        self.details = _sanitize_exception_details(details)

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert exception attributes into a serialized dictionary representation."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "exit_code": self.exit_code,
            "details": self.details,
        }
