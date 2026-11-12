"""Pydantic models of `devops infra`: the commit that a command read (#5162), the onboarding
report of an infra repo (#5121) and the status of its hosts (#5123)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OnboardState(StrEnum):
    """The state of one onboarding check."""

    PRESENT = "present"
    MISSING = "missing"
    NOT_READABLE = "not readable"
    # The check found items that a person reads, such as the tasks that run for real in check
    # mode. They do not stop the onboarding.
    LISTED = "listed"


class ReadCommit(BaseModel):
    """The commit of an infra repo that a command read, and where the checkout is."""

    model_config = ConfigDict(frozen=True)

    ref: str = Field(description="The default branch at origin, as origin/<branch>")
    commit: str = Field(description="The commit of the default branch that the command read")
    checkout_branch: str | None = Field(
        description="The branch of the checkout; none when HEAD is detached or has no commit"
    )
    checkout_commit: str | None = Field(
        description="The commit of the checkout; none when the checkout has no commit"
    )

    @property
    def checkout_differs(self) -> bool:
        """Whether the checkout is at another commit than the one that the command read."""
        return self.checkout_commit != self.commit


class OnboardRow(BaseModel):
    """One check of the onboarding of an infra repo: what it checks, its state and the next step."""

    model_config = ConfigDict(frozen=True)

    number: int = Field(description="The number of the row in the report, from 1")
    check: str = Field(description="What the row checks")
    state: OnboardState = Field(description="How the check ended")
    reason: str | None = Field(default=None, description="Why the row has its state")
    step: str | None = Field(default=None, description="What a person does to fix a gap")
    items: tuple[str, ...] = Field(
        default=(), description="The things that the check found, such as hosts or files"
    )


class OnboardReport(BaseModel):
    """The onboarding report of one infra repo, and the settings entry that `--confirm` writes."""

    model_config = ConfigDict(frozen=True)

    repo: str = Field(description="The GitHub repository of the infra repo, as owner/name")
    path: str = Field(description="The folder of the checkout")
    read: ReadCommit = Field(description="The commit that the report reads")
    rows: tuple[OnboardRow, ...] = Field(description="One row for each check, in order")
    entry: dict[str, Any] = Field(description="The entry of `infra.repos` for the repository")
    written_to: str | None = Field(
        default=None, description="The config file that `--confirm` wrote the entry to"
    )

    @property
    def has_missing(self) -> bool:
        """Whether a row is missing."""
        return any(row.state is OnboardState.MISSING for row in self.rows)


class NodeState(BaseModel):
    """One Kubernetes node, as the Kubernetes API gives it."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="The name of the node")
    ready: str = Field(description="The status of the Ready condition: True, False or Unknown")
    cordoned: bool = Field(description="Whether the node takes no new pods (spec.unschedulable)")
    kernel: str | None = Field(default=None, description="The kernel version of the node")
    kubelet: str | None = Field(default=None, description="The kubelet version of the node")
    memory_capacity_bytes: int | None = Field(
        default=None, description="The memory capacity of the node, in bytes"
    )
    memory_allocatable_bytes: int | None = Field(
        default=None, description="The memory that pods can request on the node, in bytes"
    )
    gpu_allocatable: int | None = Field(
        default=None,
        description="The GPUs that pods can request (each <vendor>/gpu resource); none when the "
        "node has no GPU resource",
    )


class PingState(StrEnum):
    """How the SSH check of one host ended."""

    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"
    # The host answered, but the check on it failed.
    FAILED = "failed"
    # The run gave no result for the host.
    NO_ANSWER = "no answer"


class HostPing(BaseModel):
    """The SSH check of one host: whether it answers, and whether it waits for a reboot."""

    model_config = ConfigDict(frozen=True)

    state: PingState = Field(description="How the check ended")
    reboot_required: bool | None = Field(
        default=None, description="Whether /run/reboot-required exists; none when not read"
    )
    reason: str | None = Field(default=None, description="Why the check did not read the host")


class HostStatus(BaseModel):
    """One inventory host with the state of its Kubernetes node, or a node with no host."""

    model_config = ConfigDict(frozen=True)

    host: str | None = Field(description="The inventory host; none for a node with no host")
    groups: tuple[str, ...] = Field(default=(), description="The inventory groups of the host")
    in_service: bool | None = Field(
        default=None,
        description="Whether the host is not in the group of hosts out of service; none for a "
        "node with no host",
    )
    node_name: str = Field(description="The name of the Kubernetes node of the host")
    node: NodeState | None = Field(
        default=None, description="The node; none when the cluster has no node of this name"
    )
    ping: HostPing | None = Field(
        default=None, description="The SSH check of the host; none without --ping"
    )


class StatusReport(BaseModel):
    """The hosts of one infra repo with the state of their nodes."""

    model_config = ConfigDict(frozen=True)

    repo: str = Field(description="The GitHub repository of the infra repo, as owner/name")
    path: str = Field(description="The folder of the checkout")
    read: ReadCommit = Field(description="The commit that the report reads")
    kube_context: str = Field(description="The kubeconfig context that gave the nodes")
    rows: tuple[HostStatus, ...] = Field(
        description="One row for each inventory host, then one for each node with no host"
    )


__all__ = [
    "HostPing",
    "HostStatus",
    "NodeState",
    "OnboardReport",
    "OnboardRow",
    "OnboardState",
    "PingState",
    "ReadCommit",
    "StatusReport",
]
