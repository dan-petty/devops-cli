"""Errors of `devops infra`, the commands of an Ansible infra repo (#5120)."""

from __future__ import annotations

from devops_cli.exceptions.base import DevOpsCLIError


class InfraError(DevOpsCLIError):
    """Base exception of the infra repo commands."""

    error_code = "INFRA_ERROR"


class InfraAccessRefusedError(InfraError):
    """An agent gave an agent access level above `none` for an infra repo. Only a person sets it."""

    error_code = "INFRA_ACCESS_REFUSED"

    def __init__(self, message: str, *, key: str) -> None:
        super().__init__(message, details={"key": key})


class InfraReadError(InfraError):
    """A local read of an infra repo failed: an Ansible command, or its output is not JSON."""

    error_code = "INFRA_READ_FAILED"


class InfraRepoNotFoundError(InfraError):
    """The checkout of an infra repo is not where the settings or the arguments put it."""

    error_code = "INFRA_REPO_NOT_FOUND"

    def __init__(self, message: str, *, path: str) -> None:
        super().__init__(message, details={"path": path})


__all__ = ["InfraAccessRefusedError", "InfraError", "InfraReadError", "InfraRepoNotFoundError"]
