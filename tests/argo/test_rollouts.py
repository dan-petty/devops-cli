"""The metric read of the rollout gate under the read retry policy (#5532).

`evaluate_rollout_gate` reads each metric with the Prometheus client, so the `web` fixture answers
each attempt below it and the `clock` fixture records each wait.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2

from devops_cli.argo.rollouts import evaluate_rollout_gate
from devops_cli.models.argo import RolloutMetricThreshold
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake

_THRESHOLD = RolloutMetricThreshold(
    metric_name="error_rate", query="sum(rate(errors[2m]))", threshold=1.0, operator="lte"
)
_LOW = {
    "status": "success",
    "data": {"resultType": "vector", "result": [{"metric": {}, "value": [1700000000, "0.5"]}]},
}


def test_a_metric_read_after_a_503_passes_the_gate(
    web: WebFake, config: Callable[..., Path], clock: ClockFake
) -> None:
    """A Prometheus that starts again answers the second attempt, and the gate reads the value."""
    config(prometheus={"url": "http://prometheus.example.com:9090"})
    answers = iter([httpx2.Response(503)])
    web.serve(lambda request: next(answers, httpx2.Response(200, json=_LOW)))

    result = evaluate_rollout_gate("web", thresholds=[_THRESHOLD], auto_abort=False)

    assert (result.passed, result.metric_results[0]["value"], len(web.sent)) == (True, 0.5, 2)


def test_a_prometheus_that_stays_down_fails_the_gate_closed(
    web: WebFake, config: Callable[..., Path], clock: ClockFake
) -> None:
    """After the attempts the metric is unavailable, and the gate fails closed."""
    config(prometheus={"url": "http://prometheus.example.com:9090"})
    web.serve(lambda request: httpx2.Response(503))

    result = evaluate_rollout_gate("web", thresholds=[_THRESHOLD], auto_abort=False)

    assert (result.passed, result.action_taken, len(web.sent)) == (
        False,
        "manual_intervention_required",
        4,
    )
