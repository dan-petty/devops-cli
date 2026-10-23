"""Git-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_GIT,
    CONST_EXIT_FAILURE,
    CONST_GITHUB_NOT_FOUND_ERROR_CODE,
    CONST_GITHUB_SCOPE_ERROR_CODE,
    CONST_GITHUB_UNAUTHENTICATED_ERROR_CODE,
    CONST_GITHUB_UNREAD_ERROR_CODE,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_MSG_BRANCH_INVALID,
)
from devops_cli.exceptions.base import DevOpsCLIError


def _bounded_detail(value: Any) -> Any:
    """A detail as an error carries it: a number as it is, anything else as text of at most
    `CONST_MAX_ERROR_DETAIL_LENGTH` characters."""
    if isinstance(value, int | float):
        return value
    return str(value)[:CONST_MAX_ERROR_DETAIL_LENGTH]


class GitOperationError(DevOpsCLIError, ValueError):
    """Base exception for Git repository and branch operation failures."""

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_GIT,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"operation": operation} if operation else {}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class InvalidBranchNameError(GitOperationError):
    """Raised when a proposed Git branch name violates naming conventions."""

    def __init__(
        self,
        branch_name: str,
        reason: str = CONST_MSG_BRANCH_INVALID,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"Invalid branch name '{branch_name}': {reason}"
        err_details = {"branch_name": branch_name, "reason": reason}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            operation="branch_validation",
            exit_code=CONST_EXIT_FAILURE,
            error_code="INVALID_BRANCH_NAME",
            details=err_details,
        )


class BranchAlreadyExistsError(GitOperationError):
    """Raised when attempting to create a branch that already exists."""

    def __init__(
        self,
        branch_name: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"Branch '{branch_name}' already exists"
        err_details = {"branch_name": branch_name}
        if details:
            err_details.update(details)
        super().__init__(
            msg,
            operation="branch_create",
            exit_code=1,
            error_code="BRANCH_ALREADY_EXISTS",
            details=err_details,
        )


class GitHubOperationError(DevOpsCLIError, RuntimeError):
    """Exception raised for GitHub API or CLI automation failures."""

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "GITHUB_OPERATION_FAILED",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"operation": operation} if operation else {}
        if details:
            err_details.update(details)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)


class GitHubNotFoundError(GitHubOperationError):
    """Raised when GitHub answers that what it was asked for does not exist (HTTP 404)."""

    def __init__(
        self,
        message: str,
        *,
        operation: str = "github_request",
        error_code: str = CONST_GITHUB_NOT_FOUND_ERROR_CODE,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, operation=operation, error_code=error_code, details=details)


class GitHubFileNotFoundError(GitHubNotFoundError):
    """Raised when a repository file GitHub was asked for does not exist on that ref."""

    def __init__(
        self,
        message: str,
        *,
        operation: str = "repository_file",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message, operation=operation, error_code="GITHUB_FILE_NOT_FOUND", details=details
        )


class GitHubScopeError(GitHubOperationError):
    """Raised when GitHub refuses a request because the token lacks a scope the endpoint needs."""

    def __init__(
        self,
        message: str,
        *,
        operation: str = "github_request",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            operation=operation,
            error_code=CONST_GITHUB_SCOPE_ERROR_CODE,
            details=details,
        )


class GitHubUnreadError(GitHubOperationError):
    """Raised when no answer from GitHub could be read, so what the request did is unknown.

    The cause is no connection, a server error that outlasted the retries, a body that does not
    decode, or a request to another origin that the session refused to send.
    """

    def __init__(
        self,
        message: str,
        *,
        operation: str = "github_request",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            operation=operation,
            error_code=CONST_GITHUB_UNREAD_ERROR_CODE,
            details=details,
        )


class GitHubUnauthenticatedError(GitHubOperationError):
    """Raised when the process has no GitHub identity, or GitHub refused its token (HTTP 401).

    `gh auth token` gives the process no token, or GitHub answers a request made with the one it
    gave with a 401.
    """

    def __init__(
        self,
        message: str,
        *,
        operation: str = "gh_auth_token",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            operation=operation,
            error_code=CONST_GITHUB_UNAUTHENTICATED_ERROR_CODE,
            details=details,
        )


class GitHubRateLimitError(GitHubOperationError, ValueError):
    """Exception raised when GitHub rate limit quota state is broken or unknown and cannot be resolved."""

    def __init__(
        self,
        message: str,
        *,
        subcommand: str = "core",
        operation: str = "rate_limit_resolve",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details: dict[str, Any] = {"subcommand": subcommand[:256]}
        if details:
            err_details.update({k: _bounded_detail(v) for k, v in details.items()})
        super().__init__(
            message,
            operation=operation,
            error_code="GITHUB_RATE_LIMIT_UNKNOWN",
            details=err_details,
        )
