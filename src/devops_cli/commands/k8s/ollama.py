"""Kubernetes Ollama commands: prune unused models from cluster nodes (#3654)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.commands.k8s.cluster_runtime import _run_cmd
from devops_cli.config.constants import CONST_K8S_OLLAMA_PRUNE_HEADING
from devops_cli.config.defaults import (
    DEFAULT_LLM_GATEWAY_CONFIG_PATH,
    DEFAULT_LLM_NAMESPACE,
    DEFAULT_LLM_SERVICES_PATH,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_repo_root
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.k8s.doctor import get_k8s_client
from devops_cli.k8s.ollama_prune import (
    NodePrune,
    OllamaPod,
    plan_ollama_prune,
    plan_ollama_prune_requests,
    read_ollama_pods,
)
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_success, write_stdout

app = new_typer(help=HELP.k8s.ollama_app, no_args_is_help=True)


def _list_node_models(
    pods_by_node: dict[str, list[OllamaPod]], context: str | None
) -> tuple[dict[str, str | None], dict[str, str]]:
    """Run `ollama list` in one pod for each node."""
    listed: dict[str, str | None] = {}
    pod_by_node: dict[str, str] = {}
    for node, node_pods in pods_by_node.items():
        chosen_pod = node_pods[0].name
        pod_by_node[node] = chosen_pod
        cmd = [
            "kubectl",
            *(["--context", context] if context else []),
            "-n",
            DEFAULT_LLM_NAMESPACE,
            "exec",
            chosen_pod,
            "--",
            "ollama",
            "list",
        ]
        res = _run_cmd(cmd, check=False, capture=True)
        listed[node] = res.stdout if res.returncode == 0 else None
    return listed, pod_by_node


def _display_prune_plan(prune_plan: Sequence[NodePrune]) -> bool:
    """Print the plan for each node. Return True if any node failed listing."""
    has_failed_node = False
    for np in prune_plan:
        write_stdout(f"Node {np.node}:\n")
        if np.list_failed:
            has_failed_node = True
            print_error(MESSAGES.k8s.ollama_prune_node_failed.format(node=np.node))
            continue
        if np.remove:
            write_stdout(f"  Remove: {', '.join(np.remove)}\n")
        else:
            write_stdout("  No models to remove.\n")
        write_stdout(f"  Keep: {', '.join(np.keep)}\n")
    return has_failed_node


def _execute_prune(
    prune_plan: Sequence[NodePrune], pod_by_node: dict[str, str], context: str | None
) -> None:
    """Run `ollama rm` on each removable model in the node's pod."""
    for np in prune_plan:
        if np.list_failed or not np.remove:
            continue
        pod_name = pod_by_node[np.node]
        for model in np.remove:
            rm_cmd = [
                "kubectl",
                *(["--context", context] if context else []),
                "-n",
                DEFAULT_LLM_NAMESPACE,
                "exec",
                pod_name,
                "--",
                "ollama",
                "rm",
                model,
            ]
            _run_cmd(rm_cmd, check=True, capture=True)
            print_success(MESSAGES.k8s.ollama_prune_removed.format(model=model, node=np.node))


@app.command(name="prune", help=HELP.k8s.ollama_prune)
@dry_run_class("request-plan")
def ollama_prune_cmd(
    plan: Annotated[bool, typer.Option("--plan", help=HELP.k8s.ollama_prune_plan)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.k8s.ollama_prune_dry_run)] = False,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.k8s.ollama_prune_context)
    ] = None,
) -> None:
    """Remove Ollama models that no tier of a node serves."""
    repo_root = find_repo_root(Path.cwd())
    gateway_path = repo_root / DEFAULT_LLM_GATEWAY_CONFIG_PATH
    services_path = repo_root / DEFAULT_LLM_SERVICES_PATH

    if dry_run or is_dry_run():
        gateway_text = gateway_path.read_text(encoding="utf-8")
        requests = plan_ollama_prune_requests(gateway_text, context=context)
        render_request_plan(CONST_K8S_OLLAMA_PRUNE_HEADING, requests)
        return

    gateway_text = gateway_path.read_text(encoding="utf-8")
    services_text = services_path.read_text(encoding="utf-8")

    core = get_k8s_client(context=context)
    pods = read_ollama_pods(core, namespace=DEFAULT_LLM_NAMESPACE)

    pods_by_node: dict[str, list[OllamaPod]] = {}
    for p in pods:
        pods_by_node.setdefault(p.node, []).append(p)

    listed, pod_by_node = _list_node_models(pods_by_node, context)
    prune_plan = plan_ollama_prune(gateway_text, services_text, pods, listed)

    if _display_prune_plan(prune_plan):
        raise typer.Exit(1)

    if not plan:
        _execute_prune(prune_plan, pod_by_node, context)
