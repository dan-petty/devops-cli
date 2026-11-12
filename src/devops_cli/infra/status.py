"""The hosts of an infra repo with the state of their Kubernetes nodes, and the SSH check of
`--ping` (#5123).

Each inventory host gets one row: its groups, whether it is in service, and its node from the
Kubernetes API of `infra.repos[].kube_context` (Ready, cordoned, kernel, kubelet, memory capacity
and allocatable memory, and GPUs). The node of a host is the host variable
`devops_infra_node_name`, else the first DNS label of the host. A node that no host names gets a
row after the hosts. The rows start no SSH connection.

`--ping` adds one `ansible-runner` ad-hoc run of `ansible.builtin.stat` on `/run/reboot-required`
on the hosts in service. A host that answers is reachable, and the file tells whether it waits for
a reboot. The run uses the `ansible.cfg` and the inventory of the repo, the key of `devops ssh`,
no `become`, and host key checks on: ansible-runner turns them off unless the environment sets
`ANSIBLE_HOST_KEY_CHECKING`. Its job events (`artifacts/<ident>/job_events/*.json`) give the
result of each host, and their folder is removed after.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import tempfile
import uuid
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from devops_cli.config.defaults import DEFAULT_INFRA_PING_TIMEOUT_SECONDS
from devops_cli.config.settings import InfraRepoConfig, Settings
from devops_cli.core.process import run_subprocess
from devops_cli.crypto.ssh_keys import find_newest_key
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.infra import InfraReadError
from devops_cli.infra.access import AgentAccess, require_agent_level
from devops_cli.infra.ansible_facts import (
    RUNNER_COMMAND,
    AnsibleInventory,
    AnsibleTool,
    ansible_tool,
    is_template,
    read_inventory,
)
from devops_cli.infra.onboard import OnboardTarget
from devops_cli.infra.repo_tree import default_branch_tree, render_read
from devops_cli.lang import ERRORS, MESSAGES
from devops_cli.models.infra import HostPing, HostStatus, NodeState, PingState, StatusReport
from devops_cli.project.profile import resolve_profile

NODE_NAME_VARIABLE: Final[str] = "devops_infra_node_name"
REBOOT_REQUIRED_FILE: Final[str] = "/run/reboot-required"
STAT_MODULE: Final[str] = "ansible.builtin.stat"
# The bound of the SSH connection to one host (`ansible -T`): it ends before the run's bound.
SSH_CONNECT_TIMEOUT_SECONDS: Final[int] = 10
_READY: Final[str] = "Ready"
_UNKNOWN: Final[str] = "Unknown"
_MEMORY: Final[str] = "memory"
_GPU_SUFFIX: Final[str] = "/gpu"
_GIB: Final[int] = 1024**3
_ARTIFACT_PREFIX: Final[str] = "devops-infra-ping-"
_EVENT_OK: Final[str] = "runner_on_ok"
_EVENT_FAILED: Final[str] = "runner_on_failed"
_EVENT_UNREACHABLE: Final[str] = "runner_on_unreachable"
_HOST_EVENTS: Final[dict[str, PingState]] = {
    _EVENT_OK: PingState.REACHABLE,
    _EVENT_FAILED: PingState.FAILED,
    _EVENT_UNREACHABLE: PingState.UNREACHABLE,
}
_NO_VALUE: Final[str] = ""


def _quantity(value: object) -> Decimal | None:
    """A Kubernetes quantity, such as `16310540Ki`, as a number; none when it is absent."""
    if value is None:
        return None
    from kubernetes.utils.quantity import parse_quantity  # type: ignore[import-untyped]

    return Decimal(parse_quantity(str(value)))


def _gpus(resources: dict[str, str] | None) -> int | None:
    """The sum of each `<vendor>/gpu` resource; none when the node has no GPU resource."""
    found = [
        _quantity(value) for name, value in (resources or {}).items() if name.endswith(_GPU_SUFFIX)
    ]
    return int(sum(value for value in found if value is not None)) if found else None


def _bytes(resources: dict[str, str] | None) -> int | None:
    value = _quantity((resources or {}).get(_MEMORY))
    return int(value) if value is not None else None


def node_state(node: Any) -> NodeState:
    """The state of a node of the Kubernetes API (a `V1Node`)."""
    status = node.status
    conditions = (status.conditions if status else None) or []
    ready = next((item.status for item in conditions if item.type == _READY), _UNKNOWN)
    info = status.node_info if status else None
    capacity = status.capacity if status else None
    allocatable = status.allocatable if status else None
    return NodeState(
        name=node.metadata.name,
        ready=ready,
        cordoned=bool(node.spec and node.spec.unschedulable),
        kernel=(info.kernel_version or None) if info else None,
        kubelet=(info.kubelet_version or None) if info else None,
        memory_capacity_bytes=_bytes(capacity),
        memory_allocatable_bytes=_bytes(allocatable),
        gpu_allocatable=_gpus(allocatable),
    )


def node_name(host: str, variables: dict[str, Any]) -> str:
    """The Kubernetes node of a host: `devops_infra_node_name`, else the first DNS label of the
    host. Only Ansible renders a template, so a templated value gives the default."""
    value = variables.get(NODE_NAME_VARIABLE)
    if value and not is_template(value):
        return str(value)
    return host.split(".", 1)[0]


def host_statuses(
    inventory: AnsibleInventory, offline_group: str | None, nodes: Iterable[NodeState]
) -> list[HostStatus]:
    """One row for each inventory host with its node, then one for each node that no host
    names, by name."""
    by_name = {state.name: state for state in nodes}
    offline = set(inventory.groups.get(offline_group, ())) if offline_group else set()
    rows: list[HostStatus] = []
    for host in inventory.hosts:
        name = node_name(host, inventory.hostvars[host])
        rows.append(
            HostStatus(
                host=host,
                groups=tuple(group for group, hosts in inventory.groups.items() if host in hosts),
                in_service=host not in offline,
                node_name=name,
                node=by_name.pop(name, None),
            )
        )
    rows.extend(
        HostStatus(host=None, node_name=name, node=state) for name, state in sorted(by_name.items())
    )
    return rows


def ping_argv(
    tool: AnsibleTool,
    root: Path,
    sources: tuple[str, ...],
    offline_group: str | None,
    key: Path | None,
    *,
    artifact_dir: Path,
    ident: str,
) -> list[str]:
    """`ansible-runner run` of `stat /run/reboot-required` on the hosts in service of the repo
    at `root`. The options after `--cmdline=` go to `ansible`: the inventory, the connection
    bound, no `become`, and the key of `devops ssh` when there is one."""
    words = [word for source in sources for word in ("-i", source)]
    words += ["-T", str(SSH_CONNECT_TIMEOUT_SECONDS), "-e", "ansible_become=false"]
    if key is not None:
        words += ["-e", f"ansible_ssh_private_key_file={key}"]
    argv = tool.argv(
        RUNNER_COMMAND,
        "run",
        str(root),
        "--artifact-dir",
        str(artifact_dir),
        "--ident",
        ident,
        "--omit-env-files",
        "--quiet",
        "--hosts",
        "all",
    )
    if offline_group:
        argv += ["--limit", f"!{offline_group}"]
    return [
        *argv,
        "-m",
        STAT_MODULE,
        "-a",
        f"path={REBOOT_REQUIRED_FILE}",
        f"--cmdline={shlex.join(words)}",
    ]


def ping_env(tool: AnsibleTool) -> dict[str, str]:
    """The environment that the run adds: the tool environment first on PATH, so ansible-runner
    finds `ansible`, and host key checks on."""
    path = os.environ.get("PATH", "")
    return {
        "PATH": os.pathsep.join(filter(None, (str(tool.bin_dir), path))),
        "ANSIBLE_HOST_KEY_CHECKING": "True",
    }


def ping_hosts(
    tool: AnsibleTool,
    root: Path,
    sources: tuple[str, ...],
    offline_group: str | None,
    key: Path | None,
) -> dict[str, HostPing]:
    """The SSH check of each host in service of the repo at `root`, by host.

    Raises:
        InfraReadError: the run exits with a status other than 0 and gives no host result.
    """
    artifact_dir = Path(tempfile.mkdtemp(prefix=_ARTIFACT_PREFIX))
    ident = uuid.uuid4().hex
    try:
        result = run_subprocess(
            ping_argv(
                tool, root, sources, offline_group, key, artifact_dir=artifact_dir, ident=ident
            ),
            env=ping_env(tool),
            quiet=True,
            timeout=DEFAULT_INFRA_PING_TIMEOUT_SECONDS,
        )
        pings = _read_events(artifact_dir / ident / "job_events")
    finally:
        shutil.rmtree(artifact_dir, ignore_errors=True)
    if not pings and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()[-1:] or [""]
        raise InfraReadError(
            ERRORS.infra.read_failed.format(
                command=RUNNER_COMMAND, code=result.returncode, detail=detail[0]
            )
        )
    return pings


def _read_events(folder: Path) -> dict[str, HostPing]:
    """The result of each host from the job events in `folder`, in the order of the run."""
    pings: dict[str, HostPing] = {}
    for path in sorted(folder.glob("*.json"), key=_counter):
        event = json.loads(path.read_text(encoding="utf-8"))
        state = _HOST_EVENTS.get(str(event.get("event")))
        data = event.get("event_data") or {}
        host = data.get("host")
        if state is None or not host:
            continue
        res = data.get("res") or {}
        if state is PingState.REACHABLE:
            exists = (res.get("stat") or {}).get("exists")
            pings[host] = HostPing(state=state, reboot_required=bool(exists))
        else:
            pings[host] = HostPing(state=state, reason=str(res.get("msg") or "") or None)
    return pings


def _counter(path: Path) -> int:
    """The number of an event file, `<counter>-<uuid>.json`."""
    head = path.name.split("-", 1)[0]
    return int(head) if head.isdigit() else 0


def with_pings(rows: Iterable[HostStatus], pings: dict[str, HostPing]) -> list[HostStatus]:
    """The rows with the SSH check of each host in service; a host in service that the run did
    not report has no answer."""
    return [
        row.model_copy(update={"ping": pings.get(row.host, HostPing(state=PingState.NO_ANSWER))})
        if row.host is not None and row.in_service
        else row
        for row in rows
    ]


def _gib(value: int | None) -> str:
    return f"{value / _GIB:.1f}" if value is not None else "?"


def _yes(value: bool | None) -> str:
    texts = MESSAGES.infra
    if value is None:
        return _NO_VALUE
    return texts.status_yes if value else texts.status_no


def status_caption(*, ping: bool) -> str:
    """The line under the table that says what its columns hold."""
    texts = MESSAGES.infra
    return " ".join(
        (texts.status_caption, texts.status_ping_caption) if ping else (texts.status_caption,)
    )


def status_table(report: StatusReport, *, ping: bool) -> tuple[list[str], list[list[str]]]:
    """The columns and the cells of the text report, one line for each row."""
    texts = MESSAGES.infra
    columns = list(texts.status_columns)
    if ping:
        columns += list(texts.status_ping_columns)
    cells: list[list[str]] = []
    for row in report.rows:
        line = [row.host or texts.status_no_host, _yes(row.in_service), row.node_name]
        state = row.node
        if state is None:
            line += [texts.status_no_node, *[_NO_VALUE] * 5]
        else:
            line += [
                state.ready,
                _yes(state.cordoned),
                state.kernel or _NO_VALUE,
                state.kubelet or _NO_VALUE,
                f"{_gib(state.memory_capacity_bytes)} / {_gib(state.memory_allocatable_bytes)}",
                _NO_VALUE if state.gpu_allocatable is None else str(state.gpu_allocatable),
            ]
        if ping:
            line += (
                [row.ping.state.value, _yes(row.ping.reboot_required)]
                if row.ping is not None
                else [_NO_VALUE, _NO_VALUE]
            )
        cells.append(line)
    return columns, cells


PING_ACTION: Final[str] = "devops infra status --ping"
_KUBE_CONTEXT_KEY: Final[str] = "infra.repos[].kube_context"


def status_entry(target: OnboardTarget, settings: Settings, *, ping: bool) -> InfraRepoConfig:
    """The settings entry of the repo, with its kube context, and the level that `--ping` needs.

    Raises:
        ConfigurationError: the repo has no entry, or its entry has no kube context.
        InfraAccessRefusedError: an agent gives `--ping` on a repo below the level `plan`.
    """
    repo = target.repo.display
    entry = settings.infra.entry(target.repo)
    if ping:
        level = entry.agent_access if entry is not None else AgentAccess.NONE
        require_agent_level(level, AgentAccess.PLAN, action=PING_ACTION, repo=repo)
    if entry is None or entry.kube_context is None:
        raise ConfigurationError(
            ERRORS.infra.no_kube_context.format(repo=repo), key=_KUBE_CONTEXT_KEY
        )
    return entry


def check_status(
    target: OnboardTarget, entry: InfraRepoConfig, settings: Settings, *, ping: bool
) -> StatusReport:
    """The hosts of the repo at the head of its default branch, with their nodes, and with the
    SSH check of each host in service when `ping` is set.

    Raises:
        InfraReadError: no Ansible tool environment is installed, the profile names no
            inventory, or a read of the repo fails.
        KubernetesContextError: the Kubernetes API does not answer.
    """
    from devops_cli.k8s.service import KubernetesService

    context = str(entry.kube_context)
    nodes = KubernetesService.get_instance().list_nodes(context=context)
    states = [node_state(item) for item in nodes]
    tool = ansible_tool()
    if not tool.installed:
        raise InfraReadError(ERRORS.infra.tool_missing)
    with default_branch_tree(target.path) as tree:
        ansible = resolve_profile(tree.root).profile.ansible
        sources = tuple(ansible.inventory)
        if not sources:
            raise InfraReadError(ERRORS.infra.no_inventory.format(repo=target.repo.display))
        rows = host_statuses(
            read_inventory(tool, tree.root, sources), ansible.offline_group, states
        )
        if ping:
            key = find_newest_key(settings.ssh.key_dir, prefix=entry.ssh_key_prefix)
            pings = ping_hosts(tool, tree.root, sources, ansible.offline_group, key)
            rows = with_pings(rows, pings)
    return StatusReport(
        repo=target.repo.display,
        path=str(target.path),
        read=tree.read,
        kube_context=context,
        rows=tuple(rows),
    )


def render_status_header(report: StatusReport) -> list[str]:
    """The title of the text report and the lines of the commit that it read."""
    title = MESSAGES.infra.status_title.format(repo=report.repo, context=report.kube_context)
    return [title, *render_read(report.read)]


__all__ = [
    "NODE_NAME_VARIABLE",
    "PING_ACTION",
    "check_status",
    "host_statuses",
    "node_name",
    "node_state",
    "ping_argv",
    "ping_env",
    "ping_hosts",
    "render_status_header",
    "status_caption",
    "status_entry",
    "status_table",
    "with_pings",
]
