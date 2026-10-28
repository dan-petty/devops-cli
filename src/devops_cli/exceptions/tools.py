"""Tool installer and external binary exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


class ToolExecutionError(DevOpsCLIError, ValueError):
    """Base exception for external developer tool and binary execution failures."""

    error_code = "TOOL_EXECUTION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        tool_name: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"tool_name": tool_name} if tool_name else {}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, details=err_details)


class ToolDownloadError(ToolExecutionError):
    """Raised when an external tool download fails or is rejected."""

    error_code = "TOOL_DOWNLOAD_ERROR"

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
            details=err_details,
        )


class ChecksumMismatchError(ToolExecutionError):
    """Raised when downloaded tool archive SHA-256 does not match expected checksum."""

    error_code = "CHECKSUM_MISMATCH"

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
            details=err_details,
        )


class SubprocessError(ToolExecutionError):
    """Raised when an external subprocess command exits with a non-zero code or fails execution."""

    error_code = "SUBPROCESS_FAILED"

    def __init__(
        self,
        message: str,
        *,
        command: list[str] | None = None,
        exit_code: int | None = None,
        stderr: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"command": command, "stderr": stderr} if (command or stderr) else {}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            exit_code=exit_code,
            details=err_details,
        )


class DependencyError(ToolExecutionError):
    """Raised when a required external binary/dependency is missing from the system PATH."""

    error_code = "DEPENDENCY_MISSING"

    def __init__(
        self,
        tool_name: str,
        *,
        install_hint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"Required dependency '{tool_name}' is not installed or not available in PATH."
        if install_hint:
            msg += f" {install_hint}"
        err_details = {"tool_name": tool_name, "install_hint": install_hint}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            tool_name=tool_name,
            details=err_details,
        )
