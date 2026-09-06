"""Git-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_GIT,
    CONST_EXIT_FAILURE,
    CONST_MSG_BRANCH_INVALID,
)
from devops_cli.exceptions.base import DevOpsCLIError


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
