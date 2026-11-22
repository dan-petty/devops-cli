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


class InfraApplyRefusedError(InfraError):
    """A guard of `devops infra apply` refused the apply before it changed a host: the plan, its
    hash, age or arguments, the commit at origin, the host key checks, or the health of the
    cluster (#5125)."""

    error_code = "INFRA_APPLY_REFUSED"


class InfraNodeRefusedError(InfraError):
    """A guard of `devops infra node` refused the run before it changed a node: a host that is not
    in service in the inventory, a restart with no unit, `--force` from an agent, or host key
    checks off for an agent (#5128)."""

    error_code = "INFRA_NODE_REFUSED"


class InfraReadError(InfraError):
    """A read of an infra repo failed: a git command of the read of its default branch, an Ansible
    command, or its output is not JSON."""

    error_code = "INFRA_READ_FAILED"


class InfraRepoNotFoundError(InfraError):
    """The checkout of an infra repo is not where the settings or the arguments put it."""

    error_code = "INFRA_REPO_NOT_FOUND"

    def __init__(self, message: str, *, path: str) -> None:
        super().__init__(message, details={"path": path})


__all__ = [
    "InfraAccessRefusedError",
    "InfraApplyRefusedError",
    "InfraError",
    "InfraNodeRefusedError",
    "InfraReadError",
    "InfraRepoNotFoundError",
]
