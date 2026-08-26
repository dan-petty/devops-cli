"""Kubernetes chaos engineering and resilience experiment runner."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.commands import build_kubectl_cmd
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.output import print_info, print_success, print_warning
from devops_cli.telemetry.tracer import trace_span


class ChaosExperimentResult(BaseModel):
    """Result of a chaos resilience experiment."""

    experiment_name: str
    target_deployment: str
    namespace: str
    duration_seconds: int
    pods_affected: int = 0
    recovered_successfully: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


def execute_chaos_experiment(
    experiment_name: str,
    target_deployment: str,
    namespace: str = "default",
    duration_seconds: int = 30,
    dry_run: bool = False,
) -> ChaosExperimentResult:
    """Execute a controlled resilience and chaos experiment against a target deployment."""
    if dry_run or is_dry_run():
        result = ChaosExperimentResult(
            experiment_name=experiment_name,
            target_deployment=target_deployment,
            namespace=namespace,
            duration_seconds=duration_seconds,
            pods_affected=1,
            recovered_successfully=True,
            details={"simulation": True, "action": "simulated_pod_deletion_and_restart"},
        )
        render_dry_run_result(
            command="devops k8s chaos run",
            action="execute_chaos_experiment",
            details=result.model_dump(),
        )
        return result

    with trace_span(
        "k8s.chaos_experiment",
        attributes={
            "experiment": experiment_name,
            "target": target_deployment,
            "namespace": namespace,
        },
    ):
        print_info(
            f"Initiating chaos experiment '{experiment_name}' on deployment '{target_deployment}'...",
            prefix=False,
        )

        # 1. Fetch matching pods
        get_pods_cmd = build_kubectl_cmd(
            ["get", "pods", "-n", namespace, "-l", f"app={target_deployment}", "-o", "name"]
        )
        res = run_subprocess(get_pods_cmd, check=False)
        pod_names = [p.strip() for p in res.stdout.strip().splitlines() if p.strip()]

        if not pod_names:
            print_warning(
                f"No running pods found for deployment '{target_deployment}' in namespace '{namespace}'."
            )
            return ChaosExperimentResult(
                experiment_name=experiment_name,
                target_deployment=target_deployment,
                namespace=namespace,
                duration_seconds=duration_seconds,
                pods_affected=0,
                recovered_successfully=False,
                details={"error": "no_matching_pods_found"},
            )

        target_pod = pod_names[0]
        print_info(f"Targeting pod '{target_pod}' for disruption...", prefix=False)

        # 2. Delete target pod to simulate sudden failure
        del_cmd = build_kubectl_cmd(["delete", target_pod, "-n", namespace, "--now"])
        run_subprocess(del_cmd, check=False)

        # 3. Wait and monitor recovery
        print_info(
            f"Waiting {duration_seconds}s for deployment replica reconciliation...", prefix=False
        )
        time.sleep(min(duration_seconds, 10))

        # 4. Check rollout status
        rollout_cmd = build_kubectl_cmd(
            [
                "rollout",
                "status",
                f"deployment/{target_deployment}",
                "-n",
                namespace,
                "--timeout=30s",
            ]
        )
        rollout_res = run_subprocess(rollout_cmd, check=False)
        recovered = rollout_res.returncode == 0

        if recovered:
            print_success(
                f"Resilience experiment passed: '{target_deployment}' recovered successfully."
            )
        else:
            print_warning(
                f"Resilience experiment warning: '{target_deployment}' did not reach ready state in time."
            )

        return ChaosExperimentResult(
            experiment_name=experiment_name,
            target_deployment=target_deployment,
            namespace=namespace,
            duration_seconds=duration_seconds,
            pods_affected=1,
            recovered_successfully=recovered,
            details={"rollout_stdout": rollout_res.stdout.strip()},
        )
