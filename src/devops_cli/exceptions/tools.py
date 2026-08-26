"""Tool installer and external binary exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import CONST_ERROR_CODE_TOOL, CONST_EXIT_FAILURE
from devops_cli.exceptions.base import DevOpsCLIError


class ToolExecutionError(DevOpsCLIError, ValueError):
    """Base exception for external developer tool and binary execution failures."""

    def __init__(
        self,
        message: str,
        *,
        tool_name: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_TOOL,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"tool_name": tool_name} if tool_name else {}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class ToolDownloadError(ToolExecutionError):
    """Raised when an external tool download fails or is rejected."""

    def __init__(
        self,
        url: str,
        reason: str,
        *,
        tool_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"Tool download failed for '{url}': {reason}"
        err_details = {"url": url, "reason": reason}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            tool_name=tool_name,
            exit_code=1,
            error_code="TOOL_DOWNLOAD_ERROR",
            details=err_details,
        )


class ChecksumMismatchError(ToolExecutionError):
    """Raised when downloaded tool archive SHA-256 does not match expected checksum."""

    def __init__(
        self,
        filename: str,
        actual_checksum: str,
        *,
        expected_checksum: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"SHA-256 checksum mismatch for '{filename}' (got {actual_checksum[:16]}...)"
        err_details = {
            "filename": filename,
            "actual_checksum": actual_checksum,
            "expected_checksum": expected_checksum,
        }
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            exit_code=1,
            error_code="CHECKSUM_MISMATCH",
            details=err_details,
        )
