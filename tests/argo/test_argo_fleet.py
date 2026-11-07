"""Tests for multi-cluster ArgoCD fleet synchronization, progressive rollouts, and rollback gates.

Argo CD and Prometheus answer through the HTTP fake (`web`), and the Rollouts live in the
Kubernetes fake (`cluster`). The commands run through the `cli` fixture, the settings come from the
`config` fixture, and the token from the keyring fake. No test patches a name or imports a private
one: each reads the requests the fake received and the objects the cluster holds.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.config.constants import (
    CONST_ARGO_API_GROUP,
    CONST_ARGO_API_VERSION,
    CONST_ARGO_PLURAL_ROLLOUTS,
)
from devops_cli.models.argo import (
    ArgoFleetAppTarget,
    ArgoFleetSyncResult,
    RolloutAnalysisResult,
    RolloutMetricThreshold,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.http import WebFake
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.kubernetes import FakeCluster, api_exception
from tests.support.fakes.mcp_dispatcher import DispatcherFake

ARGOCD_URL = "https://example.com"
SYNC_URL = f"{ARGOCD_URL}/api/v1/applications/my-app-prod-cluster/sync?appNamespace=argocd"


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


def _argocd(config: Callable[..., Path], keyring_store: FakeKeyring, token: str | None) -> None:
    """Point devops-cli at an Argo CD that stores `token`, with private addresses allowed."""
    config(argocd={"url": ARGOCD_URL}, ai={"allow_private_network": True})
    if token is not None:
        keyring_store.values["argocd_token"] = token


def _prometheus(config: Callable[..., Path]) -> None:
    """Point devops-cli at a Prometheus, with private addresses allowed."""
    config(prometheus={"url": "http://example.com:9090"}, ai={"allow_private_network": True})


def _serve_value(web: WebFake, value: str) -> None:
    """Answer each instant query with one sample of `value`."""

    def prometheus(request: httpx2.Request) -> httpx2.Response | None:
        if request.url.path != "/api/v1/query":
            return None
        return httpx2.Response(200, json={"data": {"result": [{"value": [1234567, value]}]}})

    web.serve(prometheus)


def _seed_rollout(cluster: FakeCluster, name: str, namespace: str = "default") -> None:
    """Put a Rollout in the cluster, as the API server holds it."""
    key = (CONST_ARGO_API_GROUP, CONST_ARGO_API_VERSION, CONST_ARGO_PLURAL_ROLLOUTS)
    cluster.custom_objects.objects.setdefault(key, []).append(
        {"metadata": {"name": name, "namespace": namespace}, "spec": {}, "status": {}}
    )


def _rollout(cluster: FakeCluster, name: str) -> dict[str, Any]:
    """The Rollout that the cluster holds under `name`."""
    key = (CONST_ARGO_API_GROUP, CONST_ARGO_API_VERSION, CONST_ARGO_PLURAL_ROLLOUTS)
    return next(
        obj for obj in cluster.custom_objects.objects[key] if obj["metadata"]["name"] == name
    )


def _threshold(operator: str = "lte", limit: float = 1.0) -> RolloutMetricThreshold:
    return RolloutMetricThreshold(
        metric_name="error_rate", query="sum(rate(errors[1m]))", threshold=limit, operator=operator
    )  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Fleet synchronization
# ─────────────────────────────────────────────────────────────────────────────


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


def test_a_fleet_sync_posts_the_sync_request_with_the_stored_token(
    web: WebFake, config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """A live sync of one target sends one authorized sync request, and the target is Synced."""
    from devops_cli.argo.fleet import sync_single_target

    _argocd(config, keyring_store, "test-token")
    web.respond("POST", SYNC_URL, 200, {})

    target = sync_single_target("my-app", "prod-cluster", prune=True, force=True)

    assert (target.status, target.app_name) == ("Synced", "my-app-prod-cluster")
    [sent] = web.recorded
    assert (sent.method, sent.url, sent.headers["authorization"], sent.json) == (
        "POST",
        SYNC_URL,
        "Bearer test-token",
        {"prune": True, "strategy": {"apply": {"force": True}}, "appNamespace": "argocd"},
    )


def test_a_fleet_sync_sends_no_authorization_for_a_masked_token(
    web: WebFake, config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """A masked token is not a credential, so the sync request carries no Authorization header."""
    from devops_cli.argo.fleet import sync_single_target

    _argocd(config, keyring_store, "******")
    web.respond("POST", SYNC_URL, 200, {})

    target = sync_single_target("my-app", "prod-cluster")

    assert target.status == "Synced"
    assert [("authorization" in request.headers) for request in web.recorded] == [False]


def test_a_refused_sync_request_fails_the_target_and_names_the_status(
    web: WebFake, config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """An Argo CD that refuses the sync fails the target with the status, and the others go on."""
    from devops_cli.argo.fleet import sync_single_target

    _argocd(config, keyring_store, "test-token")
    web.respond("POST", SYNC_URL, 403, {"error": "permission denied"})

    target = sync_single_target("my-app", "prod-cluster")

    assert (target.status, "403" in target.message) == ("Failed", True)


def test_a_fleet_sync_without_an_argocd_url_fails_the_target_and_names_the_setting(
    web: WebFake, config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """With no `argocd.url` the target fails before any request, and the message names the key."""
    from devops_cli.argo.fleet import sync_single_target

    config(argocd={"url": None})

    target = sync_single_target("my-app", "prod-cluster")

    assert (target.status, "argocd.url" in target.message, web.recorded) == ("Failed", True, [])


def test_a_fleet_sync_reports_each_cluster_and_counts_the_failures(
    web: WebFake, config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """One cluster that Argo CD refuses fails the fleet, and the others stay Synced."""
    from devops_cli.argo.fleet import sync_fleet

    _argocd(config, keyring_store, "test-token")
    web.serve(
        lambda request: httpx2.Response(500 if "web-prod" in request.url.path else 200, json={})
    )

    result = sync_fleet("web", clusters=["dev", "prod"], fleet_name="core")

    assert (
        [(target.cluster, target.status) for target in result.targets],
        result.total_synced,
        result.total_failed,
        result.success,
    ) == ([("dev", "Synced"), ("prod", "Failed")], 1, 1, False)


def test_a_fleet_sync_counts_itself_and_times_each_target(
    web: WebFake, config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """A fleet sync adds one to the fleet counter and one observation to the target histogram."""
    from devops_cli.argo.fleet import sync_fleet

    GLOBAL_METRICS.reset()
    _argocd(config, keyring_store, "test-token")
    web.serve(lambda request: httpx2.Response(200, json={}))

    result = sync_fleet("app", clusters=["dev"], fleet_name="test-telemetry-fleet")

    assert result.success is True
    assert (
        GLOBAL_METRICS.get_counter(
            "devops_cli_argo_fleet_sync_total", {"fleet": "test-telemetry-fleet", "success": "true"}
        )
        == 1.0
    )
    assert (
        'devops_cli_argo_target_sync_duration_seconds_count{cluster="dev",status="Synced"} 1.0'
        in GLOBAL_METRICS.export_prometheus_text()
    )


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


def test_the_fleet_sync_command_prints_each_target(
    cli: Callable[..., Any],
    web: WebFake,
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
) -> None:
    """`argo fleet sync` posts one sync request for each cluster and prints the table."""
    _argocd(config, keyring_store, "test-token")
    web.serve(lambda request: httpx2.Response(200, json={}))

    result = cli("argo", "fleet", "sync", "web", "--clusters", "dev,staging")

    assert (result.exit_code, "Fleet Synchronization" in result.output, sorted(web.requested)) == (
        0,
        True,
        [
            f"{ARGOCD_URL}/api/v1/applications/web-dev/sync?appNamespace=argocd",
            f"{ARGOCD_URL}/api/v1/applications/web-staging/sync?appNamespace=argocd",
        ],
    )


def test_the_fleet_sync_command_prints_json(
    cli: Callable[..., Any],
    web: WebFake,
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
) -> None:
    """`argo fleet sync --json` prints the result of the fleet as JSON."""
    _argocd(config, keyring_store, "test-token")
    web.serve(lambda request: httpx2.Response(200, json={}))

    result = cli("argo", "fleet", "sync", "web", "--clusters", "dev", "--json")

    data = json.loads(result.output)
    assert (result.exit_code, data["total_synced"], data["success"]) == (0, 1, True)


def test_the_sync_command_with_fleet_syncs_each_named_cluster(
    cli: Callable[..., Any],
    web: WebFake,
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
) -> None:
    """`argo sync --fleet` is `argo fleet sync`: one request per cluster in `--clusters`."""
    _argocd(config, keyring_store, "test-token")
    web.serve(lambda request: httpx2.Response(200, json={}))

    result = cli("argo", "sync", "web", "--fleet", "--clusters", "dev,staging")

    assert (result.exit_code, sorted(request.url.path for request in web.sent)) == (
        0,
        ["/api/v1/applications/web-dev/sync", "/api/v1/applications/web-staging/sync"],
    )


def test_the_fleet_sync_command_sends_nothing_under_dry_run(
    cli: Callable[..., Any], web: WebFake
) -> None:
    """With `--dry-run` the command plans the requests and sends none."""
    result = cli("argo", "fleet", "sync", "web", "--clusters", "dev", "--dry-run")

    assert (result.exit_code, web.recorded) == (0, [])


# ─────────────────────────────────────────────────────────────────────────────
# 2. Rollout control-plane mutations
# ─────────────────────────────────────────────────────────────────────────────


def test_rollouts_promote_abort_and_restart_patch_control_plane_fields(
    cluster: FakeCluster,
) -> None:
    """Rollout helpers patch the control-plane fields the rollouts controller watches."""
    from devops_cli.argo.rollouts import abort_rollout, promote_rollout, restart_rollout

    _seed_rollout(cluster, "frontend", "web")

    assert promote_rollout("frontend", namespace="web", full=True) is True
    assert _rollout(cluster, "frontend")["status"] == {
        "controllerPause": False,
        "promoteFull": True,
    }

    assert abort_rollout("frontend", namespace="web") is True
    assert _rollout(cluster, "frontend")["status"]["abort"] is True

    assert restart_rollout("frontend", namespace="web") is True
    assert "restartAt" in _rollout(cluster, "frontend")["spec"]


def test_rollout_mutation_failure_returns_false(cluster: FakeCluster) -> None:
    """A rejected Rollout patch is reported as failure rather than raising."""
    from devops_cli.argo.rollouts import promote_rollout

    _seed_rollout(cluster, "frontend", "web")
    cluster.custom_objects.fail(
        "patch_namespaced_custom_object_status", api_exception(503, "Service Unavailable")
    )

    assert promote_rollout("frontend", namespace="web") is False


def test_rollout_dry_run_modes(cluster: FakeCluster) -> None:
    """Verify promote, abort, and restart return True without reaching the Kubernetes API."""
    from devops_cli.argo.rollouts import abort_rollout, promote_rollout, restart_rollout

    assert promote_rollout("web", dry_run=True) is True
    assert abort_rollout("web", dry_run=True) is True
    assert restart_rollout("web", dry_run=True) is True

    assert (cluster.connects, cluster.custom_objects.calls) == ([], [])


@pytest.mark.parametrize(
    ("command", "said"),
    [
        (["rollouts", "promote", "payment-service", "--full"], "promoted"),
        (["rollouts", "abort", "payment-service"], "aborted"),
        (["rollouts", "restart", "payment-service"], "restarted"),
    ],
)
def test_a_rollout_command_changes_the_rollout_and_says_so(
    command: list[str], said: str, cli: Callable[..., Any], cluster: FakeCluster
) -> None:
    """Each rollout command patches the Rollout that the cluster holds and prints the outcome."""
    _seed_rollout(cluster, "payment-service")

    result = cli("argo", *command)

    patched = [name for name, _ in cluster.custom_objects.calls if name.startswith("patch_")]
    assert (result.exit_code, said in result.output.lower(), bool(patched)) == (0, True, True)


@pytest.mark.parametrize(
    ("command", "plan"),
    [
        (["rollouts", "promote", "svc", "--dry-run"], "Plan for promoting rollout"),
        (["rollouts", "abort", "svc", "--dry-run"], "Plan for aborting rollout"),
        (["rollouts", "restart", "svc", "--dry-run"], "Plan for restarting rollout"),
    ],
)
def test_a_rollout_command_under_dry_run_prints_its_plan_and_changes_nothing(
    command: list[str], plan: str, cli: Callable[..., Any], cluster: FakeCluster
) -> None:
    """`--dry-run` prints the plan of the request, and the cluster sees no call."""
    result = cli("argo", *command)

    assert (result.exit_code, plan in result.output, cluster.custom_objects.calls) == (0, True, [])


# ─────────────────────────────────────────────────────────────────────────────
# 3. The rollout gate
# ─────────────────────────────────────────────────────────────────────────────


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
    _prometheus(config)
    _serve_value(web, "3.14")

    assert _gate_value() == 3.14
    assert [request.url.params["query"] for request in web.sent] == ["rate(http_requests[1m])"]


def test_the_rollout_gate_reads_no_metric_from_an_address_the_level_refuses(
    web: WebFake, config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A private address with `ai.allow_private_network` off leaves the metric unavailable."""
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
    config(prometheus={"url": "http://10.0.0.1:9090"}, ai={"allow_private_network": False})

    assert (_gate_value(), web.recorded) == (None, [])


def test_the_rollout_gate_reads_no_metric_from_a_prometheus_that_fails(
    web: WebFake, config: Callable[..., Path]
) -> None:
    """A 500 answer leaves the metric unavailable instead of raising."""
    _prometheus(config)
    web.serve(lambda request: httpx2.Response(500, json={}))

    assert _gate_value() is None


def test_the_rollout_gate_reads_no_metric_from_a_prometheus_with_no_series(
    web: WebFake, config: Callable[..., Path]
) -> None:
    """A query that matches nothing leaves the metric unavailable."""
    _prometheus(config)
    web.serve(lambda request: httpx2.Response(200, json={"data": {"result": []}}))

    assert _gate_value() is None


@pytest.mark.parametrize(
    ("operator", "limit", "passed"),
    [
        ("lt", 3.0, True),
        ("lt", 2.0, False),
        ("lte", 2.0, True),
        ("lte", 1.0, False),
        ("gte", 2.0, True),
        ("gte", 3.0, False),
        ("gt", 1.0, True),
        ("gt", 2.0, False),
        ("eq", 2.0, True),
        ("eq", 3.0, False),
    ],
)
def test_the_rollout_gate_compares_the_value_with_the_operator(
    operator: str,
    limit: float,
    passed: bool,
    web: WebFake,
    config: Callable[..., Path],
) -> None:
    """A metric of 2.0 passes the threshold only when the operator holds."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    _prometheus(config)
    _serve_value(web, "2.0")

    result = evaluate_rollout_gate(
        "api-gateway", thresholds=[_threshold(operator, limit)], auto_abort=False
    )

    assert result.passed is passed


def test_evaluate_rollout_gate_passed(web: WebFake, config: Callable[..., Path]) -> None:
    """Verify metric evaluation passes when values are within thresholds."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    _prometheus(config)
    _serve_value(web, "0.2")

    res = evaluate_rollout_gate("api-gateway", thresholds=[_threshold()], auto_abort=True)

    assert (res.passed, res.action_taken) == (True, "promoted")


def test_evaluate_rollout_gate_threshold_violation_triggers_abort(
    web: WebFake, config: Callable[..., Path], cluster: FakeCluster
) -> None:
    """Verify metric evaluation aborts rollout when error rate exceeds threshold."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    _prometheus(config)
    _serve_value(web, "4.5")
    _seed_rollout(cluster, "api-gateway")

    res = evaluate_rollout_gate("api-gateway", thresholds=[_threshold()], auto_abort=True)

    assert (res.passed, res.action_taken, _rollout(cluster, "api-gateway")["status"]["abort"]) == (
        False,
        "aborted",
        True,
    )


def test_a_violation_without_auto_abort_leaves_the_rollout_alone(
    web: WebFake, config: Callable[..., Path], cluster: FakeCluster
) -> None:
    """With auto abort off a violation asks for a person and sends no patch."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    _prometheus(config)
    _serve_value(web, "4.5")
    _seed_rollout(cluster, "api-gateway")

    res = evaluate_rollout_gate("api-gateway", thresholds=[_threshold()], auto_abort=False)

    assert (res.action_taken, cluster.custom_objects.calls) == ("manual_intervention_required", [])


def test_evaluate_rollout_gate_refused_abort_reports_abort_failed(
    web: WebFake, config: Callable[..., Path], cluster: FakeCluster
) -> None:
    """When automated rollback abort fails, gate outcome reports abort_failed."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    _prometheus(config)
    _serve_value(web, "4.5")
    _seed_rollout(cluster, "api-gateway")
    cluster.custom_objects.fail(
        "patch_namespaced_custom_object_status", api_exception(500, "Internal Server Error")
    )

    res = evaluate_rollout_gate("api-gateway", thresholds=[_threshold()], auto_abort=True)

    assert (res.passed, res.action_taken, "automated rollback failed" in res.reason) == (
        False,
        "abort_failed",
        True,
    )


def test_rollout_gate_metric_unavailable_fails_closed(
    web: WebFake, config: Callable[..., Path], cluster: FakeCluster
) -> None:
    """Verify evaluate_rollout_gate fails closed when metrics cannot be queried."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate

    config(prometheus={"url": None})
    _seed_rollout(cluster, "payment-svc")

    res = evaluate_rollout_gate("payment-svc", auto_abort=True)

    assert (res.passed, res.action_taken, "failed closed" in res.reason) == (False, "aborted", True)


def test_the_analyze_command_prints_the_outcome_of_the_gate(
    cli: Callable[..., Any], web: WebFake, config: Callable[..., Path]
) -> None:
    """`argo rollouts analyze` reads the error rate from Prometheus and prints that it passed."""
    _prometheus(config)
    _serve_value(web, "0.1")

    result = cli("argo", "rollouts", "analyze", "cart-service", "--auto-abort")

    assert (result.exit_code, "promoted" in result.output.lower()) == (0, True)


def test_the_analyze_command_aborts_a_rollout_over_the_threshold_and_exits_1(
    cli: Callable[..., Any], web: WebFake, config: Callable[..., Path], cluster: FakeCluster
) -> None:
    """A error rate over the threshold aborts the Rollout, and the command exits 1."""
    _prometheus(config)
    _serve_value(web, "7.5")
    _seed_rollout(cluster, "cart-service")

    result = cli("argo", "rollouts", "analyze", "cart-service", "--auto-abort")

    assert (result.exit_code, _rollout(cluster, "cart-service")["status"]["abort"]) == (1, True)


def test_rollout_metric_threshold_invalid_operator() -> None:
    """Verify RolloutMetricThreshold rejects unsupported operators."""
    with pytest.raises(ValueError, match="Input should be"):
        RolloutMetricThreshold(
            metric_name="bad_operator",
            query="sum(rate(http_requests[1m]))",
            threshold=1.0,
            operator="invalid_op",  # type: ignore[arg-type]
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. MCP tools
# ─────────────────────────────────────────────────────────────────────────────


def test_mcp_argo_fleet_sync_tool(mcp_dispatcher: DispatcherFake) -> None:
    """Verify FastMCP tool argo_fleet_sync."""
    from devops_cli.ai.mcp.server import argo_fleet_sync

    mcp_dispatcher.answer('{"success": true}')

    out = argo_fleet_sync(app_name="web", clusters="dev,staging")

    assert ("true" in out, "argo" in mcp_dispatcher.last.argv) == (True, True)


def test_mcp_argo_rollout_analyze_tool(mcp_dispatcher: DispatcherFake) -> None:
    """Verify FastMCP tool argo_rollouts_analyze."""
    from devops_cli.ai.mcp.server import argo_rollouts_analyze

    mcp_dispatcher.answer('{"passed": true}')

    out = argo_rollouts_analyze(name="cart", auto_abort=True)

    assert ("true" in out, "analyze" in mcp_dispatcher.last.argv) == (True, True)


def test_mcp_argo_rollout_analyze_no_auto_abort(mcp_dispatcher: DispatcherFake) -> None:
    """Verify FastMCP tool passes --no-auto-abort when auto_abort is False."""
    from devops_cli.ai.mcp.server import argo_rollouts_analyze

    mcp_dispatcher.answer('{"passed": true}')

    out = argo_rollouts_analyze(name="cart", auto_abort=False)

    assert ("true" in out, "--no-auto-abort" in mcp_dispatcher.last.argv) == (True, True)


def test_mcp_argo_fleet_status_resource(mcp_dispatcher: DispatcherFake) -> None:
    """Verify FastMCP resource get_argo_fleet_status_resource queries read-only apps list."""
    from devops_cli.ai.mcp.server import get_argo_fleet_status_resource

    mcp_dispatcher.answer("argocd   Synced")

    get_argo_fleet_status_resource()

    assert list(mcp_dispatcher.last.argv) == ["uv", "run", "devops", "argo", "cd", "apps", "list"]
