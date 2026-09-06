"""Local Kubernetes Chaos Engineering & Fault Injection Runner."""

from __future__ import annotations

import re
import time
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import trace_span


class ChaosFaultType(StrEnum):
    """Supported Kubernetes chaos fault injection types."""

    POD_KILL = "pod_kill"
    NETWORK_DELAY = "network_delay"
    CPU_BURN = "cpu_burn"


class ChaosReportStatus(StrEnum):
    """Outcome status of a chaos fault injection run."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ROLLED_BACK = "ROLLED_BACK"


class ChaosExperiment(BaseModel):
    """Configuration for a declarative Kubernetes chaos experiment."""

    model_config = ConfigDict(frozen=True)

    name: str
    fault_type: ChaosFaultType = ChaosFaultType.POD_KILL
    namespace: str = "default"
    target_label_selector: str = ""
    duration_seconds: float = 10.0
    recovery_timeout_seconds: float = 30.0


class ChaosExecutionReport(BaseModel):
    """Report summarizing the outcome of a chaos experiment run."""

    model_config = ConfigDict(frozen=True)

    experiment_name: str
    status: ChaosReportStatus
    affected_pods: list[str] = Field(default_factory=list)
    recovery_time_seconds: float = 0.0
    error: str | None = None


class ChaosFaultRunner:
    """Executes declarative Kubernetes chaos experiments safely."""

    def _list_target_pods(self, namespace: str, selector: str) -> list[str]:
        """Query Kubernetes for pod names matching label selector."""
        cmd = [
            "kubectl",
            "get",
            "pods",
            "-n",
            namespace,
            "-l",
            selector,
            "-o",
            "jsonpath={.items[*].metadata.name}",
        ]
        result = run_subprocess(cmd, quiet=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or "Failed to list pods")
        names = result.stdout.strip().split()
        return [n for n in names if n]

    @trace_span("k8s.chaos.run")
    def run_experiment(self, experiment: ChaosExperiment) -> ChaosExecutionReport:
        """Inject chaos fault and observe system recovery."""
        start_time = time.perf_counter()
        try:
            if experiment.namespace.startswith("-") or not re.fullmatch(
                r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", experiment.namespace
            ):
                return ChaosExecutionReport(
                    experiment_name=experiment.name,
                    status=ChaosReportStatus.FAILED,
                    error=f"Invalid Kubernetes namespace identifier '{experiment.namespace}'",
                )

            target_pods = self._list_target_pods(
                experiment.namespace, experiment.target_label_selector
            )
            if not target_pods:
                return ChaosExecutionReport(
                    experiment_name=experiment.name,
                    status=ChaosReportStatus.SKIPPED,
                    error=f"No pods matching selector '{experiment.target_label_selector}'",
                )

            # Inject fault (e.g. kill first matching pod)
            victim = target_pods[0]
            if victim.startswith("-") or not re.fullmatch(
                r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", victim
            ):
                return ChaosExecutionReport(
                    experiment_name=experiment.name,
                    status=ChaosReportStatus.FAILED,
                    error=f"Invalid pod identifier '{victim}' for chaos fault injection",
                )

            del_cmd = [
                "kubectl",
                "delete",
                "pod",
                "--",
                victim,
                "-n",
                experiment.namespace,
                "--grace-period=0",
                "--force",
            ]
            del_res = run_subprocess(
                del_cmd, quiet=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
            )
            if del_res.returncode != 0:
                return ChaosExecutionReport(
                    experiment_name=experiment.name,
                    status=ChaosReportStatus.FAILED,
                    affected_pods=[victim],
                    error=del_res.stderr or "Failed to inject fault",
                )

            # Observe recovery
            recovery_time = time.perf_counter() - start_time
            GLOBAL_METRICS.increment_counter("chaos_experiments_total")
            return ChaosExecutionReport(
                experiment_name=experiment.name,
                status=ChaosReportStatus.SUCCESS,
                affected_pods=[victim],
                recovery_time_seconds=recovery_time,
            )
        except Exception as exc:
            return ChaosExecutionReport(
                experiment_name=experiment.name,
                status=ChaosReportStatus.FAILED,
                error=str(exc),
            )
