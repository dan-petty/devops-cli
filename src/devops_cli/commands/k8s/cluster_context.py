"""Kubernetes cluster context inspection, switching, node status, and log commands."""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.config.defaults import DEFAULT_K8S_LOGS_TAIL, DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.paths import validate_no_path_traversal
from devops_cli.core.validation import validate_url_egress
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_k8s_contexts_table,
    format_k8s_nodes_table,
    print,
    print_error,
    print_info,
    print_success,
    print_warning,
)


def contexts() -> None:
    """List kubeconfig contexts and mark the active one."""
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s contexts",
            action="list_kube_config_contexts",
            details={"contexts": ["minikube"], "active": "minikube"},
        )
        return
    k8s_config, _ = runtime._k8s_clients()
    try:
        ctx_list, active = k8s_config.list_kube_config_contexts()
    except Exception as exc:
        print_error(f"Failed to load kubeconfig: {exc}", prefix=False)
        raise typer.Exit(1)

    active_name = active["name"] if active else ""
    print(format_k8s_contexts_table(ctx_list, active_name=active_name))


def _sync_configured_k8s_context(name: str) -> None:
    """Synchronize switched context name into devops-cli configuration settings."""
    try:
        from devops_cli.config.settings import load_settings, save_settings

        settings = load_settings()
        if settings.k8s.context != name:
            settings.k8s.context = name
            save_settings(settings)
    except Exception as exc:
        print_warning(
            f"Warning: Switched context to '{name}', but failed to persist to devops-cli configuration: {exc}"
        )


def switch_context(
    name: Annotated[str, typer.Argument(help=HELP.k8s.context_target)],
) -> None:
    """Switch active kubeconfig context and ensure cluster is running."""
    runtime._validate_kubeconfig_context_name(name, "context name")
    is_minikube = name.strip().lower() == "minikube"

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s switch-context",
            target=name,
            action="switch_kube_config_context",
            details={"target_context": name, "start_minikube": is_minikube},
        )
        return

    if is_minikube and not runtime._minikube_running():
        print_info(MESSAGES.k8s.starting_minikube, prefix=False)
        started, start_msg = runtime._start_minikube()
        if not started:
            print_error(MESSAGES.k8s.failed_start_minikube, prefix=False)
            raise typer.Exit(1)
        print_info(start_msg, prefix=False)

    cmd = ["kubectl", "config", "use-context", name]
    runtime._run_cmd(cmd, check=True)

    _sync_configured_k8s_context(name)

    msg = MESSAGES.k8s.switched_context.format(context=name)
    print_success(msg, prefix=False)


def status() -> None:
    """Show node and pod summary for the current context."""
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s status",
            action="query_k8s_status",
            details={"nodes": 1, "status": "Ready"},
        )
        return
    k8s_config, k8s_client = runtime._k8s_clients()
    try:
        k8s_config.load_kube_config()
        core_v1_api = k8s_client.CoreV1Api()
        nodes = core_v1_api.list_node()
    except Exception as exc:
        print_error(f"Failed to query cluster: {exc}", prefix=False)
        raise typer.Exit(1)

    print(format_k8s_nodes_table(nodes.items))


def apply(
    path: Annotated[str, typer.Argument(help=HELP.k8s.manifest_path)],
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
) -> None:
    """Apply a Kubernetes manifest (delegates to kubectl)."""
    if "://" in path:
        validate_url_egress(
            path,
            purpose="manifest",
            allow_private=False,
            schemes=("http", "https"),
            error_cls=KubernetesContextError,
        )
    else:
        validate_no_path_traversal(
            path,
            error_cls=KubernetesContextError,
            label="Manifest path",
        )

    if namespace:
        runtime._validate_k8s_identifier(namespace, "namespace", namespace=True)
    cmd = ["kubectl", "apply", "-f", path]
    if dry_run or is_dry_run():
        cmd += ["--dry-run=client"]
    if namespace:
        cmd += ["--namespace", namespace]
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s apply",
            target=path,
            action="kubectl_apply",
            details={"cmd": " ".join(cmd), "namespace": namespace},
        )
        return
    runtime._run_cmd(cmd, check=True)


def _is_logql_request(pod: str, query: str | None, query_arg: str | None = None) -> bool:
    """Check whether invocation targets LogQL query/stream engine."""
    if query or pod.startswith("{"):
        return True
    if pod in ("query", "tail", "stream") and query_arg:
        return True
    return False


def _resolve_logql_query(pod: str, query: str | None, extra_arg: str | None) -> str:
    """Extract LogQL query string from options or positional arguments."""
    if query:
        return query
    if pod.startswith("{"):
        return pod
    if pod in ("query", "tail", "stream") and extra_arg:
        return extra_arg
    return pod


def _render_logql_results(result: Any, output_format: str) -> None:
    """Render LogQL query entries to terminal."""
    from devops_cli.output import escape_text, print, print_info

    if output_format == "json":
        entries_data = [
            {
                "timestamp": e.timestamp,
                "line": e.line,
                "stream": e.stream_labels,
                "fields": e.fields,
                "trace_id": e.trace_id,
            }
            for e in result.entries
        ]
        print(json.dumps({"source": result.source, "entries": entries_data}, indent=2))
        return

    if not result.entries:
        print_info(
            f"[dim]No log entries matched query (source: {result.source}).[/dim]", prefix=False
        )
        return

    for entry in result.entries:
        trace_badge = (
            f" [bold cyan][trace:{entry.trace_id[:8]}][/bold cyan]" if entry.trace_id else ""
        )
        ns_pod = ""
        if entry.stream_labels.get("pod"):
            ns_pod = f"[dim][{entry.stream_labels.get('pod')}][/dim] "
        escaped_line = escape_text(entry.line)
        print(f"{ns_pod}{escaped_line}{trace_badge}")


def _execute_legacy_kubectl_logs(
    pod: str,
    container: str | None,
    namespace: str | None,
    follow: bool,
    tail: int,
) -> None:
    """Execute standard kubectl logs command against a single pod."""
    runtime._validate_k8s_identifier(pod, "pod name")
    if container:
        runtime._validate_k8s_identifier(container, "container name")
    if namespace:
        runtime._validate_k8s_identifier(namespace, "namespace", namespace=True)
    bounded_tail = max(1, min(tail, 10000))
    cmd = ["kubectl", "logs", pod, f"--tail={bounded_tail}"]
    if container:
        cmd += ["--container", container]
    if namespace:
        cmd += ["--namespace", namespace]
    if follow:
        cmd.append("--follow")
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s logs",
            target=pod,
            action="kubectl_logs",
            details={"cmd": " ".join(cmd), "pod": pod, "tail": bounded_tail},
        )
        return
    if follow:
        runtime.run_subprocess(
            cmd,
            check=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            capture_output=False,
        )
    else:
        runtime._run_cmd(cmd, check=True)


def logs(
    pod: Annotated[str, typer.Argument(help=HELP.k8s.pod_name)] = "",
    query_arg: Annotated[
        str | None,
        typer.Argument(help="Optional LogQL query string when using query subcommand"),
    ] = None,
    query: Annotated[
        str | None, typer.Option("--query", "-q", help="LogQL query expression")
    ] = None,
    container: Annotated[
        str | None, typer.Option("--container", "-c", help=HELP.options.container)
    ] = None,
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f", help=HELP.options.follow)] = False,
    tail: Annotated[int, typer.Option("--tail", help=HELP.options.tail)] = DEFAULT_K8S_LOGS_TAIL,
    limit: Annotated[int, typer.Option("--limit", help="Max lines for LogQL query")] = 100,
    since: Annotated[str, typer.Option("--since", help="Time range for LogQL query")] = "1h",
    loki_url: Annotated[
        str | None, typer.Option("--loki-url", help="Loki service endpoint")
    ] = None,
    format: Annotated[str, typer.Option("--format", help="Output format (text, json)")] = "text",
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Stream pod logs or execute LogQL queries across cluster log streams."""
    if _is_logql_request(pod, query, query_arg):
        if follow:
            from devops_cli.output import print_error

            print_error(
                "The --follow flag is only supported for direct pod log streaming, not LogQL queries.",
                prefix=False,
            )
            raise typer.Exit(1)

        from devops_cli.k8s.logql import execute_logql_query

        resolved_query = _resolve_logql_query(pod, query, query_arg)
        if not resolved_query or not resolved_query.strip():
            from devops_cli.output import print_error

            print_error("A LogQL query expression is required.", prefix=False)
            raise typer.Exit(1)
        result = execute_logql_query(
            query=resolved_query,
            namespace=namespace,
            loki_url=loki_url,
            limit=limit,
            since=since,
            dry_run=dry_run,
        )
        _render_logql_results(result, format)
        return

    _execute_legacy_kubectl_logs(pod, container, namespace, follow, tail)
