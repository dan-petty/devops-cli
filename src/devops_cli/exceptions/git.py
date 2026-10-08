"""Git-related exception definitions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_GIT,
    CONST_EXIT_FAILURE,
    CONST_GITHUB_UNAUTHENTICATED_ERROR_CODE,
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


class GitHubFileNotFoundError(GitHubOperationError):
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


class GitHubUnauthenticatedError(GitHubOperationError):
    """Raised when `gh auth token` gives the process no GitHub identity to call GitHub as."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            operation="gh_auth_token",
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
        err_details = {"subcommand": subcommand[:256]}
        if details:
            err_details.update({k: str(v)[:256] for k, v in details.items()})
        super().__init__(
            message,
            operation=operation,
            error_code="GITHUB_RATE_LIMIT_UNKNOWN",
            details=err_details,
        )


class ReleaseWorkingTreeDirtyError(GitOperationError):
    """Raised when the working tree has uncommitted changes before cutting a release."""

    def __init__(
        self,
        message: str = "Working directory has uncommitted changes. Stash or commit them before cutting a release.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            operation="verify_clean_tree",
            exit_code=CONST_EXIT_FAILURE,
            error_code="RELEASE_WORKING_TREE_DIRTY",
            details=details,
        )


class ReleaseRemoteFetchError(GitOperationError):
    """Raised when fetching the remote release branch tip fails."""

    def __init__(
        self,
        message: str,
        *,
        remote_ref: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"remote_ref": remote_ref} if remote_ref else {}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            operation="fetch_remote_release_branch",
            exit_code=CONST_EXIT_FAILURE,
            error_code="RELEASE_REMOTE_FETCH_FAILED",
            details=err_details,
        )


class ReleaseBranchMissingError(GitOperationError):
    """Raised when the remote release branch tracking ref does not exist."""

    def __init__(
        self,
        message: str,
        *,
        remote_ref: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"remote_ref": remote_ref} if remote_ref else {}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            operation="verify_remote_release_branch",
            exit_code=CONST_EXIT_FAILURE,
            error_code="RELEASE_BRANCH_MISSING",
            details=err_details,
        )


class ReleasePushError(GitOperationError):
    """Raised when pushing a release cut branch or tag to origin fails."""

    def __init__(
        self,
        message: str,
        *,
        target_ref: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = "RELEASE_PUSH_FAILED",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"target_ref": target_ref} if target_ref else {}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            operation="git_push",
            exit_code=exit_code,
            error_code=error_code,
            details=err_details,
        )


class ReleasePushRefusedError(ReleasePushError):
    """Raised when git push to a release branch is refused by a repository ruleset (GH013)."""

    def __init__(
        self,
        message: str,
        *,
        target_ref: str | None = None,
        ruleset: str = "23059172",
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details = {"ruleset": ruleset}
        if details:
            err_details.update(details)
        super().__init__(
            message,
            target_ref=target_ref,
            exit_code=CONST_EXIT_FAILURE,
            error_code="RELEASE_PUSH_REFUSED_RULESET",
            details=err_details,
        )


class ReleasePRCreationError(GitHubOperationError):
    """Raised when creating a release pull request via GitHub CLI fails."""

    def __init__(
        self,
        message: str,
        *,
        pr_title: str | None = None,
        base: str | None = None,
        head: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details: dict[str, Any] = {}
        if pr_title:
            err_details["title"] = pr_title
        if base:
            err_details["base"] = base
        if head:
            err_details["head"] = head
        if details:
            err_details.update(details)
        super().__init__(
            message,
            operation="create_release_pr",
            exit_code=CONST_EXIT_FAILURE,
            error_code="RELEASE_PR_CREATION_FAILED",
            details=err_details,
        )
