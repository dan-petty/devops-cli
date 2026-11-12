"""Pydantic models of `devops infra`: the commit that a command read (#5162), the onboarding
report of an infra repo (#5121), the status of its hosts (#5123) and the plan of a playbook
(#5124)."""

from __future__ import annotations

from datetime import datetime
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

    ref: str = Field(
        description="The ref at origin that the command read: origin/<branch>, by default the "
        "default branch, or pull/<number>/head"
    )
    commit: str = Field(description="The commit of the ref that the command read")
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


class PlanTask(BaseModel):
    """One task of a playbook on one host, as its job events name it."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="The name of the task")
    path: str = Field(description="The file and line of the task, relative to the repo root")
    action: str = Field(description="The module or action plugin that ran the task")


class ChangedTask(PlanTask):
    """A task that check mode shows as changed on a host."""

    diff_hidden: bool = Field(
        default=False,
        description="Whether the plan holds no diff of the change, because the task sets "
        "`diff: false` or `no_log`",
    )


class FailedTask(PlanTask):
    """A task that failed on a host, or the task at which the host did not answer."""

    reason: str | None = Field(default=None, description="The message of the result")
    unreachable: bool = Field(default=False, description="Whether the host did not answer")


class HostPlan(BaseModel):
    """What a playbook does on one host, from the job events of its check-mode run."""

    model_config = ConfigDict(frozen=True)

    host: str = Field(description="The inventory host")
    changed: tuple[ChangedTask, ...] = Field(
        default=(), description="The tasks that check mode shows as changed, in run order"
    )
    disruptive: tuple[str, ...] = Field(
        default=(),
        description="The disruptive classes of the changes: reboot, service-restart:<unit> and "
        "drain, in run order",
    )
    unchecked: tuple[PlanTask, ...] = Field(
        default=(),
        description="The tasks that check mode skipped, so the plan does not show what they do",
    )
    failed: tuple[FailedTask, ...] = Field(
        default=(),
        description="The tasks that failed, or the task at which the host did not answer",
    )

    @property
    def hidden_diffs(self) -> tuple[ChangedTask, ...]:
        """The changes whose diff the plan does not hold."""
        return tuple(task for task in self.changed if task.diff_hidden)


class PlanStatus(StrEnum):
    """How the check-mode run of a plan ended. Only a plan that ended `ok` can be applied."""

    OK = "ok"
    FAILED = "failed"


class PlanContent(BaseModel):
    """The facts of a plan that its id covers: what ran, at which commit, and what it shows on
    each host."""

    model_config = ConfigDict(frozen=True)

    repo: str = Field(description="The GitHub repository of the infra repo, as owner/name")
    ref: str = Field(description="The ref at origin that the plan read")
    commit: str = Field(description="The commit that the plan ran")
    playbook: str = Field(description="The playbook, relative to the repo root")
    limit: str | None = Field(description="The --limit that the caller gave; none for all hosts")
    host_pattern: str = Field(
        description="The host pattern that Ansible got: the limit, else all, and not the group "
        "of hosts out of service"
    )
    tags: str | None = Field(description="The --tags that the caller gave; none for all tasks")
    ansible_core: str | None = Field(
        description="The ansible-core version of the tool environment; none when it is not the "
        "pinned install"
    )
    inventory_hash: str = Field(
        description="The SHA-256 of the inventory listing, with its groups and raw host variables"
    )
    status: PlanStatus = Field(description="How the check-mode run ended")
    error: str | None = Field(
        default=None, description="Why the run failed when no task names the failure"
    )
    hosts: tuple[HostPlan, ...] = Field(description="One entry for each host that the run reached")


class InfraPlan(PlanContent):
    """The plan record of a playbook of an infra repo: its facts, its id and when it ran."""

    id: str = Field(description="The SHA-256 of the canonical JSON of the facts of the plan")
    created: datetime = Field(description="When the plan ran, in UTC")
    runner_ident: str = Field(description="The ansible-runner ident of the run's artifacts")
    folder: str = Field(description="The folder of the plan record and the runner artifacts")


__all__ = [
    "ChangedTask",
    "FailedTask",
    "HostPing",
    "HostPlan",
    "HostStatus",
    "InfraPlan",
    "NodeState",
    "OnboardReport",
    "OnboardRow",
    "OnboardState",
    "PingState",
    "PlanContent",
    "PlanStatus",
    "PlanTask",
    "ReadCommit",
    "StatusReport",
]
