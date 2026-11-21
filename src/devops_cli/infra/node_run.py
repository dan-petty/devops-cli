"""Drain, uncordon, restart or reboot the nodes of the hosts of an infra repo, one host at a time
(#5128).

`devops infra node <operation> <repo> <host>...` runs these guards and steps for every caller:

1. **Access level.** An agent needs `safe` for `uncordon`, and `full` for `drain`, `restart` and
   `reboot` (`NODE_LEVELS`). A person may run each operation at every level. An agent that gives
   `--force` is refused: only a person passes `--force` to the drain.
2. **Hosts.** The command reads the inventory at the head of the default branch at `origin`
   (`default_branch_tree`). Each given host is a host of the inventory that is not in the group of
   hosts out of service. The node of a host is `devops_infra_node_name`, else its first DNS label.
3. **Unit.** A restart needs `devops_infra_node_service` on each host. A value that is a template
   is rendered with one ad-hoc `ansible.builtin.debug` task, which opens no SSH connection, before
   the first change. The unit must be a systemd unit name, so the value adds no module argument.
4. **Host keys.** An agent restart or reboot is refused when the config or the inventory turns
   host key checks off.
5. **One host at a time, in the given order** (`_STEPS`):
   - `drain`: the health gate, the read of the node, the workloads that only the node can run, the
     drain check and the drain (`Cluster.drain_bound`).
   - `uncordon`: the read of the node, `kubectl uncordon`, then the health gate.
   - `restart`: the steps of `drain`, the ad-hoc restart of the unit with become, the wait for
     Ready with the GPUs of before, the uncordon of a node that was schedulable before, and the
     health gate.
   - `reboot`: the same with the ad-hoc `ansible.builtin.reboot`; the wait for Ready also needs a
     new boot ID.
   The health gate before a host is one read: each node in service is Ready with no pressure, and
   no critical alert fires when `prometheus.url` is set. The health gate after a change is the
   waits of `devops infra apply`: the nodes, then the alerts.
6. **Stop at the first failure.** The node stays as the step left it, cordoned after a drain, and
   the hosts after it do not run. Before the first drain or uncordon the result is `refused`, after
   it `stopped`; the command exits 1 for both.
7. **Audit and telemetry.** Each run that passes the argument checks writes one audit record
   `infra.node.<operation>` and adds one to `devops_cli_infra_runs_total` with the command
   `node <operation>`.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from devops_cli.config.defaults import (
    DEFAULT_INFRA_ANSIBLE_READ_TIMEOUT_SECONDS,
    DEFAULT_INFRA_NODE_RESTART_TIMEOUT_SECONDS,
    DEFAULT_INFRA_NODE_TASK_MARGIN_SECONDS,
    DEFAULT_INFRA_REBOOT_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import InfraRepoConfig, Settings
from devops_cli.core import clock
from devops_cli.crypto.ssh_keys import find_newest_key
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.infra import InfraNodeRefusedError, InfraReadError
from devops_cli.infra.access import AgentAccess, require_agent_level
from devops_cli.infra.ad_hoc import AdHoc, AdHocTask
from devops_cli.infra.ansible_facts import (
    AnsibleInventory,
    ansible_tool,
    inventory_host_key_checks_off,
    is_template,
    read_config,
    read_inventory,
)
from devops_cli.infra.apply import Caller
from devops_cli.infra.nodes import Cluster, boot_id, parse_node
from devops_cli.infra.onboard import NODE_SERVICE_VARIABLE, OnboardTarget
from devops_cli.infra.repo_tree import default_branch_tree
from devops_cli.infra.status import node_name
from devops_cli.lang import ERRORS, MESSAGES
from devops_cli.models.infra import (
    ApplyResult,
    HostNodeRun,
    NodeOperation,
    NodeOutcome,
    NodeReport,
    NodeState,
    NodeStep,
    ReadCommit,
)
from devops_cli.project.profile import resolve_profile
from devops_cli.security.sanitizer import mask_secrets

NODE_LEVELS: Final[dict[NodeOperation, AgentAccess]] = {
    NodeOperation.DRAIN: AgentAccess.FULL,
    NodeOperation.UNCORDON: AgentAccess.SAFE,
    NodeOperation.RESTART: AgentAccess.FULL,
    NodeOperation.REBOOT: AgentAccess.FULL,
}
AUDIT_PREFIX: Final[str] = "infra.node"
DEBUG_MODULE: Final[str] = "ansible.builtin.debug"
SYSTEMD_MODULE: Final[str] = "ansible.builtin.systemd_service"
REBOOT_MODULE: Final[str] = "ansible.builtin.reboot"
# The render of the unit of a host: `debug` runs on the controller and opens no SSH connection.
RENDER_UNIT_ARGS: Final[str] = "msg={{ " + NODE_SERVICE_VARIABLE + " }}"
REBOOT_ARGS: Final[str] = f"reboot_timeout={DEFAULT_INFRA_REBOOT_TIMEOUT_SECONDS}"
# The operations that reach a host with SSH, and the operations that drain the node first.
REMOTE_OPERATIONS: Final[frozenset[NodeOperation]] = frozenset(
    {NodeOperation.RESTART, NodeOperation.REBOOT}
)
DRAIN_OPERATIONS: Final[frozenset[NodeOperation]] = frozenset(
    {NodeOperation.DRAIN, NodeOperation.RESTART, NodeOperation.REBOOT}
)
# A systemd unit name: letters, digits and `:_.@-` (systemd.unit(5)).
_UNIT_NAME: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9:_.@\-]+")
_MESSAGE: Final[str] = "msg"
_KUBE_CONTEXT_KEY: Final[str] = "infra.repos[].kube_context"
_ARROW: Final[str] = " -> "


def node_action(operation: NodeOperation) -> str:
    """The command of `operation`, as a level refusal names it."""
    return f"devops infra node {operation.value}"


def audit_command(operation: NodeOperation) -> str:
    """The command of the audit record of `operation`, such as `infra.node.drain`."""
    return f"{AUDIT_PREFIX}.{operation.value}"


def counter_command(operation: NodeOperation) -> str:
    """The `command` of `devops_cli_infra_runs_total` for `operation`, such as `node drain`."""
    return f"node {operation.value}"


def restart_task(unit: str) -> AdHocTask:
    """The ad-hoc restart of `unit` with become, within its bound."""
    return AdHocTask(
        module=SYSTEMD_MODULE,
        args=f"name={unit} state=restarted",
        become=True,
        task_timeout=DEFAULT_INFRA_NODE_RESTART_TIMEOUT_SECONDS,
    )


def reboot_task() -> AdHocTask:
    """The ad-hoc reboot with become; `reboot_timeout` bounds the wait for the host."""
    return AdHocTask(module=REBOOT_MODULE, args=REBOOT_ARGS, become=True)


def render_task() -> AdHocTask:
    """The ad-hoc render of `devops_infra_node_service`, with no become."""
    return AdHocTask(module=DEBUG_MODULE, args=RENDER_UNIT_ARGS)


@dataclass(frozen=True)
class NodeRequest:
    """What the caller runs: the operation, the inventory hosts in the order to run them, and
    whether the drain passes `--force`."""

    operation: NodeOperation
    hosts: tuple[str, ...]
    force: bool = False


def check_access(entry: InfraRepoConfig, request: NodeRequest, caller: Caller) -> None:
    """Refuse an agent below the level of the operation, and an agent that gives `--force`.

    Raises:
        InfraAccessRefusedError: an agent runs the operation on a repo below its level.
        InfraNodeRefusedError: an agent gives `--force`.
    """
    operation = request.operation
    require_agent_level(
        entry.agent_access, NODE_LEVELS[operation], action=node_action(operation), repo=entry.repo
    )
    if request.force and caller.is_agent:
        raise InfraNodeRefusedError(ERRORS.infra.node_force_agent.format(operation=operation.value))


def check_hosts(
    hosts: tuple[str, ...], inventory: AnsibleInventory, offline_group: str | None, repo: str
) -> None:
    """Refuse a host that is not a host of the inventory, or that is in the group of hosts out of
    service.

    Raises:
        InfraNodeRefusedError: a host is not a host in service.
    """
    offline = set(inventory.groups.get(offline_group, ())) if offline_group else set()
    for host in hosts:
        if host not in inventory.hostvars:
            raise InfraNodeRefusedError(ERRORS.infra.node_host_unknown.format(host=host, repo=repo))
        if host in offline:
            raise InfraNodeRefusedError(
                ERRORS.infra.node_host_offline.format(host=host, group=offline_group, repo=repo)
            )


def resolve_units(
    hosts: tuple[str, ...], inventory: AnsibleInventory, remote: AdHoc, repo: str
) -> dict[str, str]:
    """The unit of `devops_infra_node_service` of each host. A host with no value is refused
    before any process starts; the values that are templates are rendered with one ad-hoc
    `debug` task.

    Raises:
        InfraNodeRefusedError: a host sets no unit, the render fails, or a value is not a systemd
            unit name.
    """
    texts = ERRORS.infra
    raw = {host: inventory.hostvars.get(host, {}).get(NODE_SERVICE_VARIABLE) for host in hosts}
    for host, value in raw.items():
        if not value:
            raise InfraNodeRefusedError(
                texts.node_no_unit.format(host=host, variable=NODE_SERVICE_VARIABLE, repo=repo)
            )
    units = {host: str(value) for host, value in raw.items() if not is_template(value)}
    templated = [host for host, value in raw.items() if is_template(value)]
    if templated:
        outcome = remote.run(
            render_task(), ",".join(templated), timeout=DEFAULT_INFRA_ANSIBLE_READ_TIMEOUT_SECONDS
        )
        for host in templated:
            problem = outcome.problem(host)
            if problem is not None:
                raise InfraNodeRefusedError(
                    texts.node_unit_unread.format(
                        variable=NODE_SERVICE_VARIABLE, host=host, reason=problem
                    )
                )
            units[host] = str(outcome.value(host, _MESSAGE) or "")
            if not units[host]:
                raise InfraNodeRefusedError(
                    texts.node_no_unit.format(host=host, variable=NODE_SERVICE_VARIABLE, repo=repo)
                )
    for host, unit in units.items():
        if not _UNIT_NAME.fullmatch(unit):
            raise InfraNodeRefusedError(
                texts.node_unit_invalid.format(variable=NODE_SERVICE_VARIABLE, host=host, unit=unit)
            )
    return units


@dataclass
class _Progress:
    """What the run knows so far, for the report of a refusal or a stop."""

    read: ReadCommit | None = None
    hosts: list[HostNodeRun] = field(default_factory=list)
    changing: bool = False
    left_out_alerts: list[str] = field(default_factory=list)

    def leave_out(self, line: str) -> None:
        """Keep the line of an alert that the health gate left out, once."""
        if line not in self.left_out_alerts:
            self.left_out_alerts.append(line)


@dataclass(frozen=True)
class _Context:
    """What each step of a run uses."""

    request: NodeRequest
    cluster: Cluster
    remote: AdHoc | None
    units: dict[str, str]
    inventory: AnsibleInventory
    progress: _Progress

    def node(self, host: str) -> str:
        return node_name(host, self.inventory.hostvars.get(host, {}))


@dataclass
class _HostWork:
    """The run of one host as it goes."""

    host: str
    node: str
    unit: str | None
    before: NodeState | None = None
    boot: str | None = None
    down: tuple[str, ...] = ()

    def result(
        self,
        outcome: NodeOutcome,
        *,
        after: NodeState | None = None,
        step: NodeStep | None = None,
        reason: str | None = None,
    ) -> HostNodeRun:
        return HostNodeRun(
            host=self.host,
            node=self.node,
            unit=self.unit,
            outcome=outcome,
            step=step,
            reason=reason,
            down_during_drain=self.down,
            before=self.before,
            after=after,
        )


_Stop = tuple[NodeStep, str]
_Step = Callable[[_Context, _HostWork], "_Stop | None"]


def _health_before(context: _Context, work: _HostWork) -> _Stop | None:
    """One read of the health gate before the drain."""
    problems = context.cluster.health()
    if problems:
        return NodeStep.HEALTH_BEFORE, MESSAGES.infra.node_unhealthy.format(
            problems="; ".join(problems)
        )
    return None


def _read(context: _Context, work: _HostWork) -> _Stop | None:
    """Read the node before the first change: its cordon state, kernel, GPUs and boot ID."""
    read = context.cluster.node(work.node)
    if read.problem is not None or not read.document:
        return NodeStep.READ, read.problem or MESSAGES.infra.apply_no_node.format(node=work.node)
    work.before = parse_node(read.document)
    work.boot = boot_id(read.document)
    return None


def _drain(context: _Context, work: _HostWork) -> _Stop | None:
    """Name the workloads that are down while the node is cordoned, check the drain with a server
    dry run, then drain the node within the longest grace period of its pods."""
    cluster = context.cluster
    force = context.request.force
    pods = cluster.pods(work.node)
    work.down = cluster.down_during_apply(work.node, pods)
    if (problem := cluster.drain_check(work.node, force=force)) is not None:
        return NodeStep.DRAIN_CHECK, problem
    context.progress.changing = True
    if (problem := cluster.drain(work.node, cluster.drain_bound(pods), force=force)) is not None:
        return NodeStep.DRAIN, problem
    return None


def _task(
    context: _Context, work: _HostWork, task: AdHocTask, step: NodeStep, bound: int
) -> _Stop | None:
    """Run `task` on the host within `bound` seconds and the margin, so the task stops first; the
    step and the problem when it does not end well."""
    remote = context.remote
    if remote is None:
        raise AssertionError(step)
    timeout = bound + DEFAULT_INFRA_NODE_TASK_MARGIN_SECONDS
    problem = remote.run(task, work.host, timeout=timeout).problem(work.host)
    return (step, problem) if problem is not None else None


def _restart(context: _Context, work: _HostWork) -> _Stop | None:
    """Restart the unit of the host. The task waits until the unit started."""
    task = restart_task(str(work.unit))
    return _task(context, work, task, NodeStep.RESTART, DEFAULT_INFRA_NODE_RESTART_TIMEOUT_SECONDS)


def _reboot(context: _Context, work: _HostWork) -> _Stop | None:
    """Reboot the host. The task waits until the host answers with a new boot time."""
    return _task(
        context, work, reboot_task(), NodeStep.REBOOT, DEFAULT_INFRA_REBOOT_TIMEOUT_SECONDS
    )


def _ready(context: _Context, work: _HostWork) -> _Stop | None:
    """Wait for Ready and the GPUs of before; after a reboot, also for a new boot ID."""
    before = work.before
    gpus = before.gpu_allocatable if before else None
    old_boot = work.boot if context.request.operation is NodeOperation.REBOOT else None
    if problems := context.cluster.wait_ready(work.node, gpus, old_boot=old_boot):
        return NodeStep.READY, "; ".join(problems)
    return None


def _uncordon(context: _Context, work: _HostWork) -> _Stop | None:
    context.progress.changing = True
    if problems := context.cluster.uncordon(work.node):
        return NodeStep.UNCORDON, "; ".join(problems)
    return None


def _uncordon_schedulable(context: _Context, work: _HostWork) -> _Stop | None:
    """Uncordon the node only when it was schedulable before the drain."""
    if work.before is None or work.before.cordoned:
        return None
    return _uncordon(context, work)


def _health_after(context: _Context, work: _HostWork) -> _Stop | None:
    """Wait for the health of every node in service, then for the critical alerts to clear."""
    cluster = context.cluster
    if problems := cluster.wait_nodes_healthy():
        return NodeStep.HEALTH_AFTER, "; ".join(problems)
    if problems := cluster.wait_alerts_clear():
        return NodeStep.HEALTH_AFTER, "; ".join(problems)
    return None


_DRAIN_STEPS: Final[tuple[_Step, ...]] = (_health_before, _read, _drain)
_SETTLE_STEPS: Final[tuple[_Step, ...]] = (_ready, _uncordon_schedulable, _health_after)
_STEPS: Final[dict[NodeOperation, tuple[_Step, ...]]] = {
    NodeOperation.DRAIN: _DRAIN_STEPS,
    NodeOperation.UNCORDON: (_read, _uncordon, _health_after),
    NodeOperation.RESTART: (*_DRAIN_STEPS, _restart, *_SETTLE_STEPS),
    NodeOperation.REBOOT: (*_DRAIN_STEPS, _reboot, *_SETTLE_STEPS),
}


def _run_host(context: _Context, host: str) -> HostNodeRun:
    """Run the steps of the operation on one host. The first step that stops gives the result,
    with the node as the step left it."""
    work = _HostWork(host=host, node=context.node(host), unit=context.units.get(host))
    for step in _STEPS[context.request.operation]:
        stopped = step(context, work)
        if stopped is not None:
            return work.result(
                NodeOutcome.STOPPED, after=_after(context, work), step=stopped[0], reason=stopped[1]
            )
    return work.result(NodeOutcome.DONE, after=_after(context, work))


def _after(context: _Context, work: _HostWork) -> NodeState | None:
    read = context.cluster.node(work.node)
    return parse_node(read.document) if read.document else None


def run_node(target: OnboardTarget, settings: Settings, request: NodeRequest) -> NodeReport:
    """Run the operation of `request` on its hosts one at a time, and record the audit record and
    the metric of the run. A guard that refuses raises after its record; a step that stops gives
    the report with the result `refused` or `stopped`.

    Raises:
        InfraAccessRefusedError: an agent runs the operation below its level.
        InfraNodeRefusedError: a guard refuses the run.
        ConfigurationError: the repo has no kube context.
        InfraReadError: no Ansible tool environment is installed, or a read of the repo fails.
    """
    caller = Caller.current()
    entry = settings.infra.entry(target.repo) or InfraRepoConfig(repo=target.repo.display)
    progress = _Progress()
    run_id = uuid.uuid4().hex
    started = datetime.now(UTC)
    start = clock.monotonic()

    def report(result: ApplyResult, reason: str | None) -> NodeReport:
        read = progress.read
        return NodeReport(
            id=run_id,
            repo=target.repo.display,
            operation=request.operation,
            commit=read.commit if read else None,
            ref=read.ref if read else None,
            requested=request.hosts,
            force=request.force,
            caller=caller.kind,
            tool=caller.tool,
            level=entry.agent_access.value,
            result=result,
            reason=reason,
            hosts=tuple(progress.hosts),
            left_out_alerts=tuple(progress.left_out_alerts),
            started=started,
            duration_seconds=round(clock.monotonic() - start, 3),
        )

    try:
        check_access(entry, request, caller)
        if entry.kube_context is None:
            raise ConfigurationError(
                ERRORS.infra.no_kube_context.format(repo=target.repo.display),
                key=_KUBE_CONTEXT_KEY,
            )
        result = _run(target, entry, settings, request, caller, progress)
    except BaseException as exc:
        kind = ApplyResult.STOPPED if progress.changing else ApplyResult.REFUSED
        reason = exc.message if isinstance(exc, DevOpsCLIError) else mask_secrets(repr(exc))
        record_node(report(kind, reason))
        raise
    done = report(*result)
    record_node(done)
    return done


def _run(
    target: OnboardTarget,
    entry: InfraRepoConfig,
    settings: Settings,
    request: NodeRequest,
    caller: Caller,
    progress: _Progress,
) -> tuple[ApplyResult, str | None]:
    """Read the inventory at the default branch, run the guards of the hosts, then run each host
    in the given order and stop at the first host that stops."""
    repo = target.repo.display
    operation = request.operation
    tool = ansible_tool()
    if not tool.installed:
        raise InfraReadError(ERRORS.infra.tool_missing)
    with default_branch_tree(target.path) as tree:
        progress.read = tree.read
        ansible = resolve_profile(tree.root).profile.ansible
        sources = tuple(ansible.inventory)
        if not sources:
            raise InfraReadError(ERRORS.infra.no_inventory.format(repo=repo))
        inventory = read_inventory(tool, tree.root, sources)
        check_hosts(request.hosts, inventory, ansible.offline_group, repo)
        remote = None
        units: dict[str, str] = {}
        if operation in REMOTE_OPERATIONS:
            if caller.is_agent:
                found = read_config(tool, tree.root).host_key_checks_off
                found += inventory_host_key_checks_off(inventory)
                if found:
                    raise InfraNodeRefusedError(
                        ERRORS.infra.node_host_key_checks_off.format(
                            operation=operation.value, repo=repo, found="; ".join(found)
                        )
                    )
            key = find_newest_key(settings.ssh.key_dir, prefix=entry.ssh_key_prefix)
            remote = AdHoc(tool=tool, root=tree.root, sources=sources, key=key)
            if operation is NodeOperation.RESTART:
                units = resolve_units(request.hosts, inventory, remote, repo)
        offline = inventory.groups.get(ansible.offline_group, ()) if ansible.offline_group else ()
        cluster = Cluster(
            context=str(entry.kube_context),
            settings=settings,
            offline_nodes=frozenset(
                node_name(host, inventory.hostvars.get(host, {})) for host in offline
            ),
            on_left_out=progress.leave_out,
        )
        context = _Context(request, cluster, remote, units, inventory, progress)
        for host in request.hosts:
            if any(done.outcome is NodeOutcome.STOPPED for done in progress.hosts):
                progress.hosts.append(
                    HostNodeRun(
                        host=host,
                        node=context.node(host),
                        unit=units.get(host),
                        outcome=NodeOutcome.NOT_RUN,
                    )
                )
                continue
            progress.hosts.append(_run_host(context, host))
    stopped = next((h for h in progress.hosts if h.outcome is NodeOutcome.STOPPED), None)
    if stopped is None:
        return ApplyResult.OK, None
    kind = ApplyResult.STOPPED if progress.changing else ApplyResult.REFUSED
    return kind, MESSAGES.infra.apply_stopped_reason.format(
        host=stopped.host, step=stopped.step, reason=stopped.reason
    )


def audit_details(report: NodeReport) -> dict[str, Any]:
    """The details of the audit record of a node run: who, at which level, what, and each host
    with its result and its node before and after. No path of a key and no output of a task."""

    def state(value: NodeState | None, name: str) -> Any:
        return getattr(value, name) if value is not None else None

    return {
        "id": report.id,
        "operation": report.operation.value,
        "caller": report.caller,
        "tool": report.tool,
        "level": report.level,
        "repo": report.repo,
        "commit": report.commit,
        "ref": report.ref,
        "requested": list(report.requested),
        "force": report.force,
        "result": report.result.value,
        "reason": report.reason,
        "hosts": [
            {
                "host": host.host,
                "node": host.node,
                "unit": host.unit,
                "outcome": host.outcome.value,
                "step": host.step.value if host.step else None,
                "reason": host.reason,
                "cordoned_before": state(host.before, "cordoned"),
                "cordoned_after": state(host.after, "cordoned"),
                "kernel_before": state(host.before, "kernel"),
                "kernel_after": state(host.after, "kernel"),
                "down_during_drain": list(host.down_during_drain),
            }
            for host in report.hosts
        ],
        "left_out_alerts": list(report.left_out_alerts),
        "duration_seconds": report.duration_seconds,
    }


def record_node(report: NodeReport) -> None:
    """Write the audit record of a node run and add it to `devops_cli_infra_runs_total`."""
    from devops_cli.core.audit import record_audit_event
    from devops_cli.telemetry import instruments

    record_audit_event(
        audit_command(report.operation),
        status=report.result.value,
        duration_ms=report.duration_seconds * 1000,
        details=audit_details(report),
    )
    instruments.emit(
        instruments.INFRA_RUNS_TOTAL,
        1.0,
        {
            "repo": instruments.bounded_label(report.repo),
            "command": counter_command(report.operation),
            "result": report.result.value,
        },
    )


def _pair(before: object, after: object) -> str:
    """`before -> after`, with an empty side for a value that is not known."""
    marks = ["" if value is None else str(value) for value in (before, after)]
    return _ARROW.join(marks) if any(marks) else ""


def _yes(value: bool | None) -> str | None:
    texts = MESSAGES.infra
    return None if value is None else (texts.status_yes if value else texts.status_no)


def render_node_header(report: NodeReport) -> list[str]:
    """The title of the text report and the line of the caller and the level."""
    texts = MESSAGES.infra
    tool = f" ({report.tool})" if report.tool else ""
    return [
        texts.node_title.format(
            operation=report.operation.value, repo=report.repo, commit=report.commit
        ),
        texts.apply_caller.format(caller=report.caller, tool=tool, level=report.level),
    ]


def node_table(report: NodeReport) -> tuple[list[str], list[list[str]]]:
    """The columns and the cells of the text report, one line for each host."""
    cells = [
        [
            host.host,
            host.node,
            host.unit or "",
            host.outcome.value,
            host.step.value if host.step else "",
            _pair(
                _yes(host.before.cordoned if host.before else None),
                _yes(host.after.cordoned if host.after else None),
            ),
            _pair(
                host.before.gpu_allocatable if host.before else None,
                host.after.gpu_allocatable if host.after else None,
            ),
        ]
        for host in report.hosts
    ]
    return list(MESSAGES.infra.node_columns), cells


def render_node_footer(report: NodeReport) -> list[str]:
    """The lines under the table: the result, each alert that the health gate left out, the
    kernel of each host before and after a reboot, the workloads that were down, and the reason
    of a stop."""
    texts = MESSAGES.infra
    lines = [
        texts.node_done.format(
            operation=report.operation.value,
            id=report.id,
            result=report.result.value,
            seconds=report.duration_seconds,
            audit=audit_command(report.operation),
        ),
        *report.left_out_alerts,
    ]
    if report.operation is NodeOperation.REBOOT:
        lines += [
            texts.node_kernel.format(
                host=host.host,
                kernels=_pair(host.before.kernel, host.after.kernel if host.after else None),
            )
            for host in report.hosts
            if host.before is not None
        ]
    lines += [
        texts.node_down.format(host=host.host, workloads=", ".join(host.down_during_drain))
        for host in report.hosts
        if host.down_during_drain
    ]
    if report.result is not ApplyResult.OK:
        lines.append(texts.node_stopped.format(reason=report.reason))
    return lines


__all__ = [
    "AUDIT_PREFIX",
    "DRAIN_OPERATIONS",
    "NODE_LEVELS",
    "REMOTE_OPERATIONS",
    "NodeRequest",
    "audit_command",
    "audit_details",
    "check_access",
    "check_hosts",
    "counter_command",
    "node_action",
    "node_table",
    "reboot_task",
    "record_node",
    "render_node_footer",
    "render_node_header",
    "render_task",
    "resolve_units",
    "restart_task",
    "run_node",
]
