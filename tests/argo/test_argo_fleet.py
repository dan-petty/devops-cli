"""Unit tests for multi-cluster ArgoCD fleet synchronization, progressive rollouts, and rollback gates."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.argo import app
from devops_cli.models.argo import (
    ArgoFleetAppTarget,
    ArgoFleetSyncResult,
    RolloutAnalysisResult,
    RolloutMetricThreshold,
)
from tests.support.fakes.http import WebFake

runner = CliRunner()


def test_argo_fleet_models() -> None:
    """Verify serialization and validation of Argo fleet models."""
    target1 = ArgoFleetAppTarget(
        app_name="payment-service",
        cluster="us-east-dev",
        status="Synced",
        duration_seconds=1.2,
    )
    target2 = ArgoFleetAppTarget(
        app_name="payment-service",
        cluster="us-east-prod",
        status="Failed",
        message="Cluster connection timeout",
        duration_seconds=3.0,
    )
    result = ArgoFleetSyncResult(
        fleet_name="production-fleet",
        targets=[target1, target2],
        total_synced=1,
        total_failed=1,
        success=False,
    )
    data = result.model_dump()
    assert data["fleet_name"] == "production-fleet"
    assert len(data["targets"]) == 2
    assert result.success is False


def test_rollout_metric_threshold_model() -> None:
    """Verify RolloutMetricThreshold model validation."""
    thresh = RolloutMetricThreshold(
        metric_name="http_error_rate",
        query="rate(http_requests_total{status=~'5..'}[5m])",
        threshold=0.01,
        operator="lte",
    )
    assert thresh.threshold == 0.01
    assert thresh.operator == "lte"


def test_sync_fleet_engine_mock() -> None:
    """Verify fleet coordination engine with simulated cluster synchronization."""
    from devops_cli.argo.fleet import sync_fleet

    res = sync_fleet(
        app_name="web-frontend",
        clusters=["dev", "staging", "prod"],
        fleet_name="core-apps",
        max_concurrency=2,
        dry_run=True,
    )
    assert len(res.targets) == 3
    assert res.total_synced == 3
    assert res.total_failed == 0
    assert res.success is True


def test_sync_fleet_engine_partial_failure() -> None:
    """Verify fleet engine correctly handles and aggregates cluster failure."""
    from devops_cli.argo.fleet import sync_single_target

    with patch("devops_cli.argo.fleet._execute_cluster_sync") as mock_sync:
        mock_sync.side_effect = RuntimeError("Sync rejected by cluster admission webhook")
        target = sync_single_target("service-a", "prod-cluster", prune=False, force=False)
        assert target.status == "Failed"
        assert "admission webhook" in target.message


def test_rollouts_promote_abort_and_restart_patch_control_plane_fields() -> None:
    """Rollout helpers patch the control-plane fields the rollouts controller watches."""
    from devops_cli.argo.rollouts import abort_rollout, promote_rollout, restart_rollout

    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = {
        "metadata": {"name": "frontend"},
        "spec": {},
    }
    mock_api.patch_namespaced_custom_object.return_value = {"metadata": {"name": "frontend"}}
    mock_api.patch_namespaced_custom_object_status.return_value = {"metadata": {"name": "frontend"}}

    with patch("devops_cli.argo.crd.ArgoCRDService._api", return_value=mock_api):
        assert promote_rollout("frontend", namespace="web", full=True) is True
        promote_body = mock_api.patch_namespaced_custom_object_status.call_args.kwargs["body"]
        assert promote_body["status"] == {
            "pauseConditions": None,
            "controllerPause": False,
            "promoteFull": True,
        }

        assert abort_rollout("frontend", namespace="web") is True
        assert mock_api.patch_namespaced_custom_object_status.call_args.kwargs["body"] == {
            "status": {"abort": True}
        }

        assert restart_rollout("frontend", namespace="web") is True
        restart_body = mock_api.patch_namespaced_custom_object.call_args.kwargs["body"]
        assert "restartAt" in restart_body["spec"]


def test_rollout_mutation_failure_returns_false() -> None:
    """A rejected Rollout patch is reported as failure rather than raising."""
    from devops_cli.argo.rollouts import promote_rollout

    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = {
        "metadata": {"name": "frontend"},
        "spec": {},
    }
    mock_api.patch_namespaced_custom_object_status.side_effect = RuntimeError(
        "apiserver unavailable"
    )

    with patch("devops_cli.argo.crd.ArgoCRDService._api", return_value=mock_api):
        assert promote_rollout("frontend", namespace="web") is False


def test_evaluate_rollout_gate_passed() -> None:
    """Verify metric evaluation passes when values are within thresholds."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    thresholds = [
        RolloutMetricThreshold(
            metric_name="error_rate",
            query="sum(rate(errors[1m]))",
            threshold=1.0,
            operator="lte",
        )
    ]
    with patch("devops_cli.argo.rollouts._fetch_metric_value", return_value=0.2):
        res = evaluate_rollout_gate("api-gateway", thresholds=thresholds, auto_abort=True)
        assert res.passed is True
        assert res.action_taken == "promoted"


def test_evaluate_rollout_gate_threshold_violation_triggers_abort() -> None:
    """Verify metric evaluation aborts rollout when error rate exceeds threshold."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    thresholds = [
        RolloutMetricThreshold(
            metric_name="error_rate",
            query="sum(rate(errors[1m]))",
            threshold=1.0,
            operator="lte",
        )
    ]
    with (
        patch("devops_cli.argo.rollouts._fetch_metric_value", return_value=4.5),
        patch("devops_cli.argo.rollouts.abort_rollout", return_value=True) as mock_abort,
    ):
        res = evaluate_rollout_gate("api-gateway", thresholds=thresholds, auto_abort=True)
        assert res.passed is False
        assert res.action_taken == "aborted"
        mock_abort.assert_called_once()


def test_evaluate_rollout_gate_refused_abort_reports_abort_failed() -> None:
    """When automated rollback abort fails, gate outcome reports abort_failed."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    thresholds = [
        RolloutMetricThreshold(
            metric_name="error_rate",
            query="sum(rate(errors[1m]))",
            threshold=1.0,
            operator="lte",
        )
    ]
    with (
        patch("devops_cli.argo.rollouts._fetch_metric_value", return_value=4.5),
        patch("devops_cli.argo.rollouts.abort_rollout", return_value=False) as mock_abort,
    ):
        res = evaluate_rollout_gate("api-gateway", thresholds=thresholds, auto_abort=True)
        assert res.passed is False
        assert res.action_taken == "abort_failed"
        assert "automated rollback failed" in res.reason
        mock_abort.assert_called_once()


def test_cli_argo_fleet_sync() -> None:
    """Verify devops argo fleet sync CLI command with table output."""
    with patch("devops_cli.argo.fleet.sync_fleet") as mock_sync:
        mock_sync.return_value = ArgoFleetSyncResult(
            fleet_name="default-fleet",
            targets=[
                ArgoFleetAppTarget(
                    app_name="web",
                    cluster="dev",
                    status="Synced",
                    duration_seconds=0.5,
                )
            ],
            total_synced=1,
            total_failed=0,
            success=True,
        )
        result = runner.invoke(app, ["fleet", "sync", "web", "--clusters", "dev,staging"])
        assert result.exit_code == 0
        assert "Fleet Synchronization" in result.output or "Synced" in result.output


def test_cli_argo_fleet_sync_json() -> None:
    """Verify devops argo fleet sync --json output format."""
    with patch("devops_cli.argo.fleet.sync_fleet") as mock_sync:
        mock_sync.return_value = ArgoFleetSyncResult(
            fleet_name="default-fleet",
            targets=[
                ArgoFleetAppTarget(
                    app_name="web",
                    cluster="dev",
                    status="Synced",
                    duration_seconds=0.5,
                )
            ],
            total_synced=1,
            total_failed=0,
            success=True,
        )
        result = runner.invoke(app, ["fleet", "sync", "web", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_synced"] == 1
        assert data["success"] is True


def test_cli_argo_rollouts_promote() -> None:
    """Verify devops argo rollouts promote CLI command."""
    with patch("devops_cli.argo.rollouts.promote_rollout", return_value=True):
        result = runner.invoke(app, ["rollouts", "promote", "payment-service", "--full"])
        assert result.exit_code == 0
        assert "promoted" in result.output.lower()


def test_cli_argo_rollouts_abort() -> None:
    """Verify devops argo rollouts abort CLI command."""
    with patch("devops_cli.argo.rollouts.abort_rollout", return_value=True):
        result = runner.invoke(app, ["rollouts", "abort", "payment-service"])
        assert result.exit_code == 0
        assert "aborted" in result.output.lower()


def test_cli_argo_rollouts_restart() -> None:
    """Verify devops argo rollouts restart CLI command."""
    with patch("devops_cli.argo.rollouts.restart_rollout", return_value=True):
        result = runner.invoke(app, ["rollouts", "restart", "payment-service"])
        assert result.exit_code == 0
        assert "restarted" in result.output.lower()


def test_cli_argo_rollouts_analyze() -> None:
    """Verify devops argo rollouts analyze CLI command."""
    with patch("devops_cli.argo.rollouts.evaluate_rollout_gate") as mock_eval:
        mock_eval.return_value = RolloutAnalysisResult(
            rollout_name="cart-service",
            passed=True,
            action_taken="promoted",
            metric_results=[{"metric": "error_rate", "value": 0.1, "passed": True}],
        )
        result = runner.invoke(app, ["rollouts", "analyze", "cart-service", "--auto-abort"])
        assert result.exit_code == 0
        assert "promoted" in result.output.lower() or "passed" in result.output.lower()


def test_mcp_argo_fleet_sync_tool() -> None:
    """Verify FastMCP tool argo_fleet_sync."""
    from devops_cli.ai.mcp.server import argo_fleet_sync

    with patch(
        "devops_cli.ai.mcp.server._run_mcp_cmd", return_value='{"success": true}'
    ) as mock_cmd:
        out = argo_fleet_sync(app_name="web", clusters="dev,staging")
        assert "true" in out
        assert "argo" in mock_cmd.call_args[0][0]


def test_mcp_argo_rollout_analyze_tool() -> None:
    """Verify FastMCP tool argo_rollouts_analyze."""
    from devops_cli.ai.mcp.server import argo_rollouts_analyze

    with patch(
        "devops_cli.ai.mcp.server._run_mcp_cmd", return_value='{"passed": true}'
    ) as mock_cmd:
        out = argo_rollouts_analyze(name="cart", auto_abort=True)
        assert "true" in out
        assert "analyze" in mock_cmd.call_args[0][0]


def test_mcp_argo_fleet_status_resource() -> None:
    """Verify FastMCP resource get_argo_fleet_status_resource queries read-only apps list."""
    from devops_cli.ai.mcp.server import get_argo_fleet_status_resource

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="argocd   Synced") as mock_cmd:
        get_argo_fleet_status_resource()

    assert mock_cmd.call_args.args[0] == ["uv", "run", "devops", "argo", "cd", "apps", "list"]


def _fleet_argocd(config: Callable[..., Path], keyring_store: Any, token: str) -> str:
    """Point devops-cli at a fake Argo CD that stores `token`; return the sync URL of `my-app`."""
    config(argocd={"url": "https://example.com"}, ai={"allow_private_network": True})
    keyring_store.values["argocd_token"] = token
    return "https://example.com/api/v1/applications/my-app-prod-cluster/sync?appNamespace=argocd"


def test_a_fleet_sync_posts_the_sync_request_with_the_stored_token(
    web: WebFake, config: Callable[..., Path], keyring_store: Any
) -> None:
    """A live sync of one target sends one authorized sync request, and the target is Synced."""
    from devops_cli.argo.fleet import sync_single_target

    url = _fleet_argocd(config, keyring_store, "test-token")
    web.respond("POST", url, 200, {})

    target = sync_single_target("my-app", "prod-cluster", prune=True, force=True)

    assert (target.status, target.app_name) == ("Synced", "my-app-prod-cluster")
    [sent] = web.recorded
    assert (sent.method, sent.url, sent.headers["authorization"], sent.json) == (
        "POST",
        url,
        "Bearer test-token",
        {"prune": True, "strategy": {"apply": {"force": True}}, "appNamespace": "argocd"},
    )


def test_a_fleet_sync_sends_no_authorization_for_a_masked_token(
    web: WebFake, config: Callable[..., Path], keyring_store: Any
) -> None:
    """A masked token is not a credential, so the sync request carries no Authorization header."""
    from devops_cli.argo.fleet import sync_single_target

    url = _fleet_argocd(config, keyring_store, "******")
    web.respond("POST", url, 200, {})

    target = sync_single_target("my-app", "prod-cluster")

    assert target.status == "Synced"
    assert [("authorization" in request.headers) for request in web.recorded] == [False]


def test_execute_cluster_sync_missing_url() -> None:
    """Verify _execute_cluster_sync raises ConfigurationError when ArgoCD URL is missing."""
    from devops_cli.argo.fleet import _execute_cluster_sync
    from devops_cli.exceptions.config import ConfigurationError

    mock_settings = MagicMock()
    mock_settings.argocd.url = ""

    with patch("devops_cli.argo.fleet.load_settings", return_value=mock_settings):
        with pytest.raises(ConfigurationError, match="ArgoCD URL is not configured"):
            _execute_cluster_sync("app", "cluster")


def test_rollout_dry_run_modes() -> None:
    """Verify promote, abort, and restart return True without reaching the Kubernetes API."""
    from devops_cli.argo.rollouts import abort_rollout, promote_rollout, restart_rollout

    with patch("devops_cli.argo.crd.ArgoCRDService._api") as mock_api:
        assert promote_rollout("web", dry_run=True) is True
        assert abort_rollout("web", dry_run=True) is True
        assert restart_rollout("web", dry_run=True) is True
        mock_api.assert_not_called()


def _gate_value(metric_query: str = "rate(http_requests[1m])") -> object:
    """The value that the rollout gate read for one metric, or None when it was unavailable."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    threshold = RolloutMetricThreshold(
        metric_name="requests", query=metric_query, threshold=10.0, operator="lte"
    )
    result = evaluate_rollout_gate("web", thresholds=[threshold], auto_abort=False)
    return result.metric_results[0]["value"]


def test_the_rollout_gate_reads_no_metric_without_a_prometheus_url(
    web: WebFake, config: Callable[..., Path]
) -> None:
    """With no Prometheus URL the metric is unavailable and no request is sent."""
    config(prometheus={"url": None})

    assert (_gate_value(), web.recorded) == (None, [])


def test_the_rollout_gate_reads_the_value_of_a_prometheus_answer(
    web: WebFake, config: Callable[..., Path]
) -> None:
    """The gate takes the first sample of an instant query answer as the metric value."""
    config(prometheus={"url": "http://example.com:9090"}, ai={"allow_private_network": True})

    def prometheus(request: httpx2.Request) -> httpx2.Response | None:
        if request.url.path != "/api/v1/query":
            return None
        return httpx2.Response(200, json={"data": {"result": [{"value": [1234567, "3.14"]}]}})

    web.serve(prometheus)

    assert _gate_value() == 3.14
    assert [request.url.params["query"] for request in web.sent] == ["rate(http_requests[1m])"]


def test_the_rollout_gate_reads_no_metric_from_an_address_the_level_refuses(
    web: WebFake, config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A private address with `ai.allow_private_network` off leaves the metric unavailable."""
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
    config(prometheus={"url": "http://10.0.0.1:9090"}, ai={"allow_private_network": False})

    assert (_gate_value(), web.recorded) == (None, [])


def test_compare_metric_operators() -> None:
    """Verify _compare_metric for all supported comparison operators."""
    from devops_cli.argo.rollouts import _compare_metric

    assert _compare_metric(1.0, 2.0, "lt") is True
    assert _compare_metric(2.0, 2.0, "lt") is False
    assert _compare_metric(3.0, 2.0, "gte") is True
    assert _compare_metric(1.0, 2.0, "gte") is False
    assert _compare_metric(3.0, 2.0, "gt") is True
    assert _compare_metric(2.0, 2.0, "gt") is False
    assert _compare_metric(2.0, 2.0, "eq") is True
    assert _compare_metric(2.0, 3.0, "eq") is False
    # Fail-closed on None
    assert _compare_metric(None, 2.0, "lte") is False
    # Unsupported operator raises ValueError
    with pytest.raises(ValueError, match="Unsupported"):
        _compare_metric(1.0, 2.0, "unknown_op")


def test_render_table_formatters() -> None:
    """Verify render_fleet_sync_table and render_rollout_analysis_table."""
    from devops_cli.argo.fleet import render_fleet_sync_table
    from devops_cli.argo.rollouts import render_rollout_analysis_table

    fleet_res = ArgoFleetSyncResult(
        fleet_name="demo-fleet",
        targets=[
            ArgoFleetAppTarget(
                app_name="svc",
                cluster="dev",
                status="Synced",
                duration_seconds=0.8,
            ),
            ArgoFleetAppTarget(
                app_name="svc",
                cluster="prod",
                status="Failed",
                message="Error",
                duration_seconds=1.2,
            ),
        ],
        total_synced=1,
        total_failed=1,
        success=False,
    )
    tbl1 = render_fleet_sync_table(fleet_res)
    assert tbl1.title.startswith("Argo Fleet Synchronization")
    assert len(tbl1.rows) == 2

    rollout_res = RolloutAnalysisResult(
        rollout_name="worker",
        passed=False,
        action_taken="aborted",
        metric_results=[
            {
                "metric": "error_rate",
                "value": 2.5,
                "operator": "lte",
                "threshold": 1.0,
                "passed": False,
            }
        ],
    )
    tbl2 = render_rollout_analysis_table(rollout_res)
    assert tbl2.title.startswith("Argo Rollout Analysis")
    assert len(tbl2.rows) == 1


def test_rollout_metric_threshold_invalid_operator() -> None:
    """Verify RolloutMetricThreshold rejects unsupported operators."""
    with pytest.raises(ValueError, match="Input should be"):
        RolloutMetricThreshold(
            metric_name="bad_operator",
            query="sum(rate(http_requests[1m]))",
            threshold=1.0,
            operator="invalid_op",  # type: ignore[arg-type]
        )


def test_cli_argo_sync_fleet_alias() -> None:
    """Verify devops argo sync --fleet delegates to fleet sync."""
    with patch("devops_cli.argo.fleet.sync_fleet") as mock_sync:
        mock_sync.return_value = ArgoFleetSyncResult(
            fleet_name="default-fleet",
            targets=[
                ArgoFleetAppTarget(
                    app_name="web",
                    cluster="dev",
                    status="Synced",
                    duration_seconds=0.5,
                )
            ],
            total_synced=1,
            total_failed=0,
            success=True,
        )
        result = runner.invoke(app, ["sync", "web", "--fleet", "--clusters", "dev,staging"])
        assert result.exit_code == 0
        mock_sync.assert_called_once()
        assert mock_sync.call_args[1]["clusters"] == ["dev", "staging"]


def test_rollout_gate_metric_unavailable_fails_closed() -> None:
    """Verify evaluate_rollout_gate fails closed when metrics cannot be queried."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    with (
        patch("devops_cli.argo.rollouts._fetch_metric_value", return_value=None),
        patch("devops_cli.argo.rollouts.abort_rollout", return_value=True) as mock_abort,
    ):
        res = evaluate_rollout_gate("payment-svc", auto_abort=True)
        assert res.passed is False
        assert res.action_taken == "aborted"
        assert "failed closed" in res.reason
        mock_abort.assert_called_once()


def test_rollout_gate_abort_failed() -> None:
    """Verify evaluate_rollout_gate sets action_taken to abort_failed when abort fails."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    with (
        patch("devops_cli.argo.rollouts._fetch_metric_value", return_value=5.0),
        patch("devops_cli.argo.rollouts.abort_rollout", return_value=False),
    ):
        res = evaluate_rollout_gate("cart-svc", auto_abort=True)
        assert res.passed is False
        assert res.action_taken == "abort_failed"
        assert "automated rollback failed" in res.reason


def test_rollout_dry_run_propagation() -> None:
    """Verify CLI rollout commands propagate dry-run mode and prevent execution."""
    with (
        patch("devops_cli.argo.rollouts.promote_rollout", return_value=True) as mock_promote,
        patch("devops_cli.argo.rollouts.abort_rollout", return_value=True) as mock_abort,
        patch("devops_cli.argo.rollouts.restart_rollout", return_value=True) as mock_restart,
    ):
        res1 = runner.invoke(app, ["rollouts", "promote", "svc", "--dry-run"])
        assert res1.exit_code == 0
        mock_promote.assert_not_called()
        assert "Plan for promoting rollout" in res1.output

        res2 = runner.invoke(app, ["rollouts", "abort", "svc", "--dry-run"])
        assert res2.exit_code == 0
        mock_abort.assert_not_called()
        assert "Plan for aborting rollout" in res2.output

        res3 = runner.invoke(app, ["rollouts", "restart", "svc", "--dry-run"])
        assert res3.exit_code == 0
        mock_restart.assert_not_called()
        assert "Plan for restarting rollout" in res3.output


def test_mcp_argo_rollout_analyze_no_auto_abort() -> None:
    """Verify FastMCP tool passes --no-auto-abort when auto_abort is False."""
    from devops_cli.ai.mcp.server import argo_rollouts_analyze

    with patch(
        "devops_cli.ai.mcp.server._run_mcp_cmd", return_value='{"passed": true}'
    ) as mock_cmd:
        out = argo_rollouts_analyze(name="cart", auto_abort=False)
        assert "true" in out
        cmd = mock_cmd.call_args[0][0]
        assert "--no-auto-abort" in cmd


def test_fleet_sync_telemetry_and_metrics() -> None:
    """Verify fleet synchronization instruments OpenTelemetry span and Prometheus metrics."""
    from devops_cli.argo.fleet import sync_fleet

    with (
        patch("devops_cli.argo.fleet._execute_cluster_sync"),
        patch("devops_cli.telemetry.metrics.GLOBAL_METRICS.increment_counter") as mock_counter,
        patch("devops_cli.telemetry.metrics.GLOBAL_METRICS.record_histogram") as mock_histo,
    ):
        result = sync_fleet("app", clusters=["dev"], fleet_name="test-telemetry-fleet")
        assert result.success is True
        mock_counter.assert_called_once_with(
            "devops_cli_argo_fleet_sync_total",
            value=1.0,
            labels={"fleet": "test-telemetry-fleet", "success": "true"},
        )
        mock_histo.assert_called_once()
