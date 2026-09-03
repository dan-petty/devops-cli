"""Multi-pod live log streamer with Stern integration and native kubectl fallback."""

from __future__ import annotations

import shutil

from devops_cli.config.commands import (
    BIN_STERN,
    build_kubectl_cmd,
    build_stern_cmd,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.output import print_info
from devops_cli.telemetry.tracer import trace_span


def stream_multi_pod_logs(
    pod_query: str,
    namespace: str | None = None,
    container: str | None = None,
    tail_lines: int = 100,
    follow: bool = False,
    dry_run: bool = False,
) -> int:
    """Stream logs across multiple pods matching a query pattern."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops k8s stream-logs",
            action="stream_multi_pod_logs",
            details={
                "pod_query": pod_query,
                "namespace": namespace or "default",
                "container": container,
                "tail_lines": tail_lines,
                "follow": follow,
            },
        )
        return 0

    from devops_cli.core.validation import validate_k8s_name

    if namespace:
        validate_k8s_name(namespace, "namespace", namespace=True)
    if container:
        validate_k8s_name(container, "container")

    with trace_span("k8s.stream_logs", attributes={"pod_query": pod_query}):
        has_stern = shutil.which(BIN_STERN) is not None
        if has_stern:
            cmd = build_stern_cmd(
                pod_query=pod_query,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
                follow=follow,
            )
        else:
            print_info(
                "[dim]Stern not found in PATH; falling back to kubectl logs selector[/dim]",
                prefix=False,
            )
            k_args = ["logs", "-l", f"app={pod_query}", f"--tail={tail_lines}"]
            if namespace:
                k_args.extend(["-n", namespace])
            if container:
                k_args.extend(["-c", container])
            if follow:
                k_args.append("-f")
            cmd = build_kubectl_cmd(k_args)

        proc = run_subprocess(cmd, check=False)
        return proc.returncode
