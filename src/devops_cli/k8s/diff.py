"""Helm release diff previewer using the helm-diff plugin."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devops_cli.config.commands import build_helm_diff_cmd
from devops_cli.core.process import run_subprocess
from devops_cli.output import print_error
from devops_cli.telemetry.tracer import trace_span


def diff_helm_release(
    release_name: str,
    chart_path: Path,
    namespace: str | None = None,
    values_files: Sequence[Path] | None = None,
    dry_run: bool = False,
) -> tuple[int, str]:
    """Preview manifest changes between deployed Helm release and updated local chart/values."""
    if dry_run:
        mock_diff = (
            f"******************** {namespace or 'default'}, {release_name}, Deployment (apps) ********************\n"
            f"[-] spec.replicas: 1\n"
            f"[+] spec.replicas: 3\n"
        )
        return 0, mock_diff

    with trace_span("k8s.diff_helm", attributes={"release_name": release_name}):
        cmd = build_helm_diff_cmd(
            release_name=release_name,
            chart_path=chart_path,
            namespace=namespace,
            values_files=values_files,
        )
        from devops_cli.security.sanitizer import mask_secrets

        res = run_subprocess(cmd, check=False)
        output = mask_secrets(res.stdout or res.stderr)
        if res.returncode not in (0, 2):  # 2 is helm-diff exit code when differences exist
            print_error(f"Helm diff failed: {output.strip()}", prefix=False)
        return res.returncode, output
