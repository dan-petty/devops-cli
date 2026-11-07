"""Argo Rollouts progressive delivery orchestration and metric rollback gates."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx2

from devops_cli.argo.crd import ArgoCRDService, get_argo_crd_service
from devops_cli.config.defaults import DEFAULT_K8S_NAMESPACE
from devops_cli.config.settings import load_settings
from devops_cli.core.validation import validate_k8s_name
from devops_cli.exceptions.argo import ArgoError
from devops_cli.http.egress import configured_level
from devops_cli.models.argo import (
    ArgoRolloutState,
    RolloutAnalysisResult,
    RolloutMetricThreshold,
)
from devops_cli.models.prometheus import PrometheusQueryResult
from devops_cli.prometheus.client import PrometheusClient

if TYPE_CHECKING:
    from devops_cli.output.models import TablePayload

logger = logging.getLogger(__name__)

_METRIC_TIMEOUT_SECONDS = 5.0


def promote_rollout(
    name: str,
    namespace: str = DEFAULT_K8S_NAMESPACE,
    full: bool = False,
    dry_run: bool = False,
) -> bool:
    """Promote an Argo Rollout to its next step or to full release."""
    return _mutate_rollout(
        name, namespace, dry_run, lambda svc: svc.promote_rollout(name, namespace, full=full)
    )


def abort_rollout(
    name: str,
    namespace: str = DEFAULT_K8S_NAMESPACE,
    dry_run: bool = False,
) -> bool:
    """Abort an in-progress Argo Rollout and revert to the stable revision."""
    return _mutate_rollout(name, namespace, dry_run, lambda svc: svc.abort_rollout(name, namespace))


def restart_rollout(
    name: str,
    namespace: str = DEFAULT_K8S_NAMESPACE,
    dry_run: bool = False,
) -> bool:
    """Restart an Argo Rollout across all pods."""
    return _mutate_rollout(
        name, namespace, dry_run, lambda svc: svc.restart_rollout(name, namespace)
    )


def _mutate_rollout(
    name: str,
    namespace: str,
    dry_run: bool,
    mutate: Callable[[ArgoCRDService], ArgoRolloutState],
) -> bool:
    """Validate inputs and apply a Rollout control-plane patch through the Kubernetes API."""
    validate_k8s_name(name, "rollout name")
    validate_k8s_name(namespace, "namespace", namespace=True)

    if dry_run:
        return True

    try:
        mutate(get_argo_crd_service())
    except ArgoError as exc:
        logger.debug("Rollout '%s' mutation failed in namespace '%s': %s", name, namespace, exc)
        return False
    return True


def _fetch_metric_value(query: str) -> float | None:
    """Query Prometheus or return None when metric is unavailable.

    The client dials the configured level: loopback, or private with `ai.allow_private_network`.
    A refused address (SSRFBlockedError, a ValueError) leaves the metric unavailable.
    """
    settings = load_settings()
    if not settings.prometheus.url:
        return None

    try:
        with PrometheusClient(
            settings.prometheus.url, configured_level(settings.ai), timeout=_METRIC_TIMEOUT_SECONDS
        ) as prometheus:
            result = PrometheusQueryResult.from_instant_response(prometheus.query(query))
        return float(result.series[0].value) if result.series else None
    except (httpx2.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.debug("Failed to query Prometheus metric: %s", exc)
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
    namespace: str = DEFAULT_K8S_NAMESPACE,
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
