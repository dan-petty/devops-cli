"""Dry-run request plans of `devops infra` (#5121, #5123, #5124, #5125).

A dry run starts no process and sends no request: it lists, in order, the commands that the real
run starts, each value that only a read gives as a named placeholder.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from devops_cli.config.defaults import DEFAULT_INFRA_DRAIN_CHECK_TIMEOUT_SECONDS
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.infra.ansible_facts import (
    CONFIG_DUMP_ARGS,
    RUNNER_COMMAND,
    ansible_tool,
    inventory_argv,
)
from devops_cli.infra.nodes import (
    CLAIMS_ARGS,
    CRITICAL_ALERTS_QUERY,
    GET_NODES_ARGS,
    VOLUMES_ARGS,
    drain_args,
    get_node_args,
    kubectl_argv,
    pods_args,
    uncordon_args,
)
from devops_cli.infra.onboard import KUBE_CONTEXTS_ARGV, known_hosts_file
from devops_cli.infra.plan import (
    PLAN_FILE,
    PROJECT_FOLDER,
    REQUIREMENTS_FILE,
    galaxy_argv,
    runner_argv,
)
from devops_cli.infra.repo_tree import apply_read_commands, pull_number, read_commands
from devops_cli.infra.status import REBOOT_REQUIRED_FILE, STAT_MODULE
from devops_cli.models.infra import InfraPlan


def plan_onboard(
    checkout: Path, *, origin_lookup: bool, confirm: bool, config_path: Path
) -> list[PlannedRequest]:
    """The commands of an onboarding of the checkout at `checkout`, and the write of `--confirm`.
    With `origin_lookup`, the repository is named by the remote `origin` of the checkout. The
    Ansible commands run in the export of the default branch (#5162)."""
    tool = ansible_tool()
    installed = "an Ansible tool environment is installed"
    requests: list[PlannedRequest] = []
    if origin_lookup:
        requests.append(
            PlannedRequest(
                method="EXEC",
                target=f"the remote origin of {checkout}",
                argv=("git", "remote", "get-url", "origin"),
            )
        )
    requests += read_commands(checkout)
    requests += [
        PlannedRequest(
            method="EXEC",
            target="the Ansible config of the export",
            argv=tuple(tool.argv("ansible-config", *CONFIG_DUMP_ARGS)),
            condition=installed,
        ),
        PlannedRequest(
            method="EXEC",
            target="the Ansible inventory of the export",
            argv=tuple(inventory_argv(tool, ("<inventory>",))),
            condition=f"{installed} and the project profile names an inventory",
        ),
        PlannedRequest(
            method="EXEC",
            target="the host key of <host> in known_hosts",
            argv=("ssh-keygen", "-F", "<host>", "-f", str(known_hosts_file())),
            condition=f"{known_hosts_file()} exists",
            repeat="for each host in service",
        ),
        PlannedRequest(method="EXEC", target="the kubeconfig contexts", argv=KUBE_CONTEXTS_ARGV),
    ]
    if confirm:
        requests.append(PlannedRequest(method="WRITE", target=f"infra.repos in {config_path}"))
    return requests


def _origin_lookup(checkout: Path) -> PlannedRequest:
    return PlannedRequest(
        method="EXEC",
        target=f"the remote origin of {checkout}",
        argv=("git", "remote", "get-url", "origin"),
    )


def plan_status(
    checkout: Path, *, origin_lookup: bool, kube_context: str | None, ping: bool
) -> list[PlannedRequest]:
    """The requests of `devops infra status` on the checkout at `checkout`: the nodes of the kube
    context, the read of the default branch, the inventory in its export, and the SSH check of
    `--ping`."""
    tool = ansible_tool()
    requests = [_origin_lookup(checkout)] if origin_lookup else []
    requests.append(
        PlannedRequest(
            method="kubernetes.client.CoreV1Api",
            target=f"list_node in the kube context {kube_context or '<kube context of the entry>'}",
        )
    )
    requests += read_commands(checkout)
    requests.append(
        PlannedRequest(
            method="EXEC",
            target="the Ansible inventory of the export",
            argv=tuple(inventory_argv(tool, ("<inventory>",))),
        )
    )
    if ping:
        requests.append(
            PlannedRequest(
                method="EXEC",
                target="the SSH check of each host in service",
                argv=(
                    *tool.argv(RUNNER_COMMAND, "run", "<export>"),
                    "--hosts",
                    "all",
                    "--limit",
                    "!<offline group>",
                    "-m",
                    STAT_MODULE,
                    "-a",
                    f"path={REBOOT_REQUIRED_FILE}",
                ),
            )
        )
    return requests


def plan_plan(
    checkout: Path,
    *,
    origin_lookup: bool,
    plans: Path,
    playbook: str,
    limit: str | None,
    tags: str | None,
    ref: str | None,
) -> list[PlannedRequest]:
    """The requests of `devops infra plan` on the checkout at `checkout`: the export of the commit
    into a new folder under `plans`, the inventory, the install of the pinned collections, the
    check-mode run and the write of the plan record."""
    tool = ansible_tool()
    folder = plans / "<new folder>"
    project = folder / PROJECT_FOLDER
    requests = [_origin_lookup(checkout)] if origin_lookup else []
    requests += read_commands(checkout, ref=ref, export=project)
    requests += [
        PlannedRequest(
            method="EXEC",
            target="the Ansible inventory of the export",
            argv=tuple(inventory_argv(tool, ("<inventory>",))),
        ),
        PlannedRequest(
            method="EXEC",
            target="the install of the pinned collections",
            argv=tuple(
                galaxy_argv(tool, project / REQUIREMENTS_FILE, Path("<collections folder>"))
            ),
            condition=f"the repo has {REQUIREMENTS_FILE} and no install of it is kept",
        ),
        PlannedRequest(
            method="EXEC",
            target="the check-mode run of the playbook on the hosts in service",
            argv=tuple(
                runner_argv(
                    tool,
                    folder,
                    playbook,
                    ident="<ident>",
                    pattern=f"{limit or 'all'}:!<offline group>",
                    sources=("<inventory>",),
                    tags=tags,
                    key=Path("<key of devops ssh>"),
                )
            ),
        ),
        PlannedRequest(method="WRITE", target=str(plans / "<plan id>" / PLAN_FILE)),
    ]
    return requests


@dataclass(frozen=True)
class ApplyTarget:
    """What a dry run of an apply knows: the checkout, whether its origin names the repo, the
    folder of the plans, the plan record when it reads, the plan id, the playbook, the tags, the
    kube context and the drain bound of the entry, and the Prometheus URL."""

    repo: str
    checkout: Path
    origin_lookup: bool
    plans: Path
    plan_id: str
    plan: InfraPlan | None
    playbook: str
    tags: str | None
    kube_context: str | None
    drain_timeout_seconds: int
    prometheus_url: str | None


def plan_apply(target: ApplyTarget) -> list[PlannedRequest]:
    """The requests of `devops infra apply`, in order: the commit at origin and its export, the
    reads of the export, the health gate, the run of the hosts with no disruptive class, and the
    steps of each disruptive host in plan order. With no plan record, the hosts are named
    placeholders."""
    tool = ansible_tool()
    plan = target.plan
    folder = target.plans / target.plan_id / "applies" / "<apply id>"
    commit = plan.commit if plan else "<commit of the plan>"
    ref = plan.ref if plan else "<ref of the plan>"
    context = target.kube_context or "<kube context of the entry>"
    requests = [_origin_lookup(target.checkout)] if target.origin_lookup else []
    requests += apply_read_commands(target.checkout, commit, ref, folder / PROJECT_FOLDER)
    number = pull_number(ref)
    if number is not None:
        requests.append(
            PlannedRequest(
                method="GET",
                target=f"https://api.github.com/repos/{target.repo}/pulls/{number}",
                condition="an agent applies the head of a pull request",
            )
        )
    requests += [
        PlannedRequest(
            method="EXEC",
            target="the Ansible inventory of the export",
            argv=tuple(inventory_argv(tool, ("<inventory>",))),
        ),
        PlannedRequest(
            method="EXEC",
            target="the Ansible config of the export, for its host key checks",
            argv=tuple(tool.argv("ansible-config", *CONFIG_DUMP_ARGS)),
            condition="an agent runs the apply",
        ),
        *_health(context, target.prometheus_url),
        PlannedRequest(
            method="EXEC",
            target="the install of the pinned collections",
            argv=tuple(
                galaxy_argv(
                    tool, folder / PROJECT_FOLDER / REQUIREMENTS_FILE, Path("<collections folder>")
                )
            ),
            condition=f"the repo has {REQUIREMENTS_FILE} and no install of it is kept",
        ),
    ]

    def runner(pattern: str, *, check_mode: bool) -> tuple[str, ...]:
        return tuple(
            runner_argv(
                tool,
                folder,
                plan.playbook if plan else target.playbook,
                ident="<ident>",
                pattern=pattern,
                sources=("<inventory>",),
                tags=target.tags,
                key=Path("<key of devops ssh>"),
                check_mode=check_mode,
            )
        )

    together = [host.host for host in plan.hosts if not host.disruptive] if plan else []
    if together:
        requests.append(
            PlannedRequest(
                method="EXEC",
                target="the run of the hosts with no disruptive class",
                argv=runner(f"{','.join(together)}:!<offline group>", check_mode=False),
            )
        )
    alone = [host.host for host in plan.hosts if host.disruptive] if plan else ["<host>"]
    repeat = "" if plan else "for each disruptive host in plan order"
    for host in alone:
        requests += _host_steps(target, context, host, runner, repeat)
    requests.append(PlannedRequest(method="WRITE", target="the audit record infra.apply"))
    return requests


def _health(context: str, prometheus_url: str | None) -> list[PlannedRequest]:
    requests = [
        PlannedRequest(
            method="EXEC",
            target="the health of each node in service",
            argv=tuple(kubectl_argv(context, *GET_NODES_ARGS)),
        )
    ]
    if prometheus_url:
        requests.append(
            PlannedRequest(
                method="GET",
                target=f"{prometheus_url.rstrip('/')}/api/v1/query?query={CRITICAL_ALERTS_QUERY}",
            )
        )
    return requests


def _host_steps(
    target: ApplyTarget,
    context: str,
    host: str,
    runner: Callable[..., tuple[str, ...]],
    repeat: str,
) -> list[PlannedRequest]:
    """The steps of one disruptive host: read, drain check, drain, fresh check, run, wait for
    Ready, health, uncordon, and the last read of the node."""
    node = f"<node of {host}>"
    pattern = f"{host}:!<offline group>"
    wait = "once each poll interval until it passes twice or the wait ends"

    def kubectl(target_text: str, args: tuple[str, ...], **extra: str) -> PlannedRequest:
        return PlannedRequest(
            method="EXEC",
            target=target_text,
            argv=tuple(kubectl_argv(context, *args)),
            repeat=extra.get("repeat", repeat),
            condition=extra.get("condition", ""),
        )

    timeout = target.drain_timeout_seconds
    return [
        kubectl(f"the node of {host} before the drain", get_node_args(node)),
        kubectl(f"the pods of {host}, for their grace periods and volumes", pods_args(node)),
        kubectl("the PersistentVolumeClaims", CLAIMS_ARGS),
        kubectl("the PersistentVolumes, for the volumes that only one node mounts", VOLUMES_ARGS),
        kubectl(
            f"the server dry run of the drain of {host}",
            drain_args(node, DEFAULT_INFRA_DRAIN_CHECK_TIMEOUT_SECONDS, server_dry_run=True),
        ),
        kubectl(
            f"the drain of {host}, with the longer of {timeout} s and the longest grace period "
            "and 60 s",
            drain_args(node, timeout, server_dry_run=False),
        ),
        PlannedRequest(
            method="EXEC",
            target=f"the fresh check of {host}, which must give its plan",
            argv=runner(pattern, check_mode=True),
            repeat=repeat,
        ),
        PlannedRequest(
            method="EXEC",
            target=f"the run of {host}",
            argv=runner(pattern, check_mode=False),
            repeat=repeat,
        ),
        kubectl(f"Ready and the GPUs of {host}", get_node_args(node), repeat=wait),
        kubectl("the health of each node in service", GET_NODES_ARGS, repeat=wait),
        kubectl(
            f"the uncordon of {host}",
            uncordon_args(node),
            condition="the node was schedulable before the drain",
        ),
        *[
            replace(request, repeat=wait, condition="prometheus.url is set")
            for request in _health(context, target.prometheus_url)[1:]
        ],
        kubectl(f"the node of {host} after the apply", get_node_args(node)),
    ]


__all__ = ["ApplyTarget", "plan_apply", "plan_onboard", "plan_plan", "plan_status"]
