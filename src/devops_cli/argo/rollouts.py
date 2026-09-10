"""Argo Rollouts progressive delivery orchestration and metric rollback gates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.core.validation import validate_k8s_name
from devops_cli.models.argo import RolloutAnalysisResult, RolloutMetricThreshold

if TYPE_CHECKING:
    from devops_cli.output.models import TablePayload


def promote_rollout(
    name: str,
    namespace: str = "default",
    full: bool = False,
    dry_run: bool = False,
) -> bool:
    """Promote an Argo Rollout to next step or full release."""
    validate_k8s_name(name, "rollout name")
    validate_k8s_name(namespace, "namespace", namespace=True)

    if dry_run:
        return True

    cmd = ["kubectl", "argo", "rollouts", "promote", name, "--namespace", namespace]
    if full:
        cmd.append("--full")

    proc = run_subprocess(
        cmd,
        check=False,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        capture_output=True,
    )
    return proc.returncode == 0


def abort_rollout(
    name: str,
    namespace: str = "default",
    dry_run: bool = False,
) -> bool:
    """Abort an in-progress Argo Rollout and revert to stable revision."""
    validate_k8s_name(name, "rollout name")
    validate_k8s_name(namespace, "namespace", namespace=True)

    if dry_run:
        return True

    cmd = ["kubectl", "argo", "rollouts", "abort", name, "--namespace", namespace]
    proc = run_subprocess(
        cmd,
        check=False,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        capture_output=True,
    )
    return proc.returncode == 0


def restart_rollout(
    name: str,
    namespace: str = "default",
    dry_run: bool = False,
) -> bool:
    """Restart an Argo Rollout across all pods."""
    validate_k8s_name(name, "rollout name")
    validate_k8s_name(namespace, "namespace", namespace=True)

    if dry_run:
        return True

    cmd = ["kubectl", "argo", "rollouts", "restart", name, "--namespace", namespace]
    proc = run_subprocess(
        cmd,
        check=False,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        capture_output=True,
    )
    return proc.returncode == 0


def _fetch_metric_value(query: str) -> float | None:
    """Query Prometheus or return None when metric is unavailable."""
    from devops_cli.config import load_settings
    from devops_cli.http.validation import validate_service_url

    settings = load_settings()
    prom_url = getattr(settings, "prometheus", None) and getattr(settings.prometheus, "url", None)
    if not prom_url:
        return None

    try:
        import httpx2

        validate_service_url(prom_url, "Prometheus", allow=settings.ai.allow_private_network)
        with httpx2.Client() as client:
            resp = client.get(
                f"{prom_url.rstrip('/')}/api/v1/query",
                params={"query": query},
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", {}).get("result", [])
                if results and "value" in results[0]:
                    return float(results[0]["value"][1])
    except Exception:
        return None

    return None


def _compare_metric(val: float | None, threshold: float, operator: str) -> bool:
    """Evaluate comparison operator predicate with fail-closed semantics for missing metrics."""
    if val is None:
        return False

    ops = {
        "lte": val <= threshold,
        "lt": val < threshold,
        "gte": val >= threshold,
        "gt": val > threshold,
        "eq": val == threshold,
    }
    if operator not in ops:
        raise ValueError(f"Unsupported rollout metric operator '{operator}'")
    return ops[operator]


def _evaluate_single_threshold(
    t: RolloutMetricThreshold,
) -> tuple[dict[str, object], str | None]:
    """Evaluate a single metric threshold gate and return evaluation record and error reason."""
    val = _fetch_metric_value(t.query)
    passed = _compare_metric(val, t.threshold, t.operator)
    record: dict[str, object] = {
        "metric": t.metric_name,
        "query": t.query,
        "value": val,
        "threshold": t.threshold,
        "operator": t.operator,
        "passed": passed,
    }
    if passed:
        return record, None

    if val is None:
        reason = f"{t.metric_name} (metric unavailable / failed closed)"
    else:
        reason = f"{t.metric_name} ({val} not {t.operator} {t.threshold})"
    return record, reason


def _resolve_gate_action(
    rollout_name: str,
    namespace: str,
    all_passed: bool,
    auto_abort: bool,
    dry_run: bool,
    reasons: list[str],
) -> tuple[str, str]:
    """Determine rollout gate outcome action and execute automated rollback if configured."""
    if all_passed:
        return "promoted", "All metric gates passed"

    failure_reason = "; ".join(reasons)
    if not auto_abort:
        return "manual_intervention_required", failure_reason

    abort_success = abort_rollout(rollout_name, namespace=namespace, dry_run=dry_run)
    if abort_success:
        return "aborted", failure_reason

    return "abort_failed", f"{failure_reason}; automated rollback failed"


def evaluate_rollout_gate(
    rollout_name: str,
    namespace: str = "default",
    thresholds: list[RolloutMetricThreshold] | None = None,
    auto_abort: bool = True,
    dry_run: bool = False,
) -> RolloutAnalysisResult:
    """Evaluate metric gates for an active rollout and execute automated rollback on violation."""
    from devops_cli.telemetry.tracer import trace_span

    with trace_span(
        "argo.rollouts.evaluate_gate", {"rollout": rollout_name, "namespace": namespace}
    ):
        validate_k8s_name(rollout_name, "rollout name")
        validate_k8s_name(namespace, "namespace", namespace=True)

        default_thresholds = thresholds or [
            RolloutMetricThreshold(
                metric_name="http_error_rate_percentage",
                query=f'sum(rate(http_requests_total{{status=~"5..",app="{rollout_name}"}}[2m])) / sum(rate(http_requests_total{{app="{rollout_name}"}}[2m])) * 100',
                threshold=1.0,
                operator="lte",
            )
        ]

        metric_evals: list[dict[str, object]] = []
        failure_reasons: list[str] = []

        for t in default_thresholds:
            rec, err = _evaluate_single_threshold(t)
            metric_evals.append(rec)
            if err:
                failure_reasons.append(err)

        all_passed = len(failure_reasons) == 0
        action, reason = _resolve_gate_action(
            rollout_name, namespace, all_passed, auto_abort, dry_run, failure_reasons
        )

        return RolloutAnalysisResult(
            rollout_name=rollout_name,
            namespace=namespace,
            passed=all_passed,
            metric_results=metric_evals,
            action_taken=action,
            reason=reason,
        )


def render_rollout_analysis_table(result: RolloutAnalysisResult) -> TablePayload:
    """Render structured TablePayload displaying rollout analysis and gate action."""
    from devops_cli.output import format_argo_rollout_analysis_table

    return format_argo_rollout_analysis_table(result)
