"""Dry-run request plans of `devops infra` (#5121).

A dry run starts no process and sends no request: it lists, in order, the commands that the real
run starts, each value that only a read gives as a named placeholder.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.infra.ansible_facts import CONFIG_DUMP_ARGS, ansible_tool, inventory_argv
from devops_cli.infra.onboard import KUBE_CONTEXTS_ARGV, known_hosts_file


def plan_onboard(
    checkout: Path, *, origin_lookup: bool, confirm: bool, config_path: Path
) -> list[PlannedRequest]:
    """The commands of an onboarding of the checkout at `checkout`, and the write of `--confirm`.
    With `origin_lookup`, the repository is named by the remote `origin` of the checkout."""
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
    requests += [
        PlannedRequest(
            method="EXEC",
            target=f"the Ansible config of {checkout}",
            argv=tuple(tool.argv("ansible-config", *CONFIG_DUMP_ARGS)),
            condition=installed,
        ),
        PlannedRequest(
            method="EXEC",
            target=f"the Ansible inventory of {checkout}",
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


__all__ = ["plan_onboard"]
