"""Dry-run request plans of `devops infra` (#5121, #5123, #5124).

A dry run starts no process and sends no request: it lists, in order, the commands that the real
run starts, each value that only a read gives as a named placeholder.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.infra.ansible_facts import (
    CONFIG_DUMP_ARGS,
    RUNNER_COMMAND,
    ansible_tool,
    inventory_argv,
)
from devops_cli.infra.onboard import KUBE_CONTEXTS_ARGV, known_hosts_file
from devops_cli.infra.plan import (
    PLAN_FILE,
    PROJECT_FOLDER,
    REQUIREMENTS_FILE,
    galaxy_argv,
    runner_argv,
)
from devops_cli.infra.repo_tree import read_commands
from devops_cli.infra.status import REBOOT_REQUIRED_FILE, STAT_MODULE


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


__all__ = ["plan_onboard", "plan_plan", "plan_status"]
