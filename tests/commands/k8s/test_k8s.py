"""Unit tests for Kubernetes CLI commands (devops_cli.commands.k8s)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.dry_run import set_dry_run
from devops_cli.prometheus.promql import selectors, validate_promql
from devops_cli.tools_lock import load_tools_lock
from tests.support.config_writes import written_keys
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.kubernetes import FakeCluster, api_exception, healthy_pod, node, service
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer
from tests.support.k8s_commands import (
    answer_helm_version,
    argo_cd_manages_the_cluster,
    calls_starting,
    install_kubectl_world,
    minikube_running,
    minikube_stopped,
    name_contexts,
    stock_push_keyring,
)
from tests.support.k8s_tree import pinned_charts
from tests.support.paths import FIXTURES, REPO_ROOT
from tests.support.tcp_probe import TcpProbe

runner = CliRunner()


_KUBE_LINTER_FINDING = json.dumps(
    {
        "Reports": [
            {
                "Check": "run-as-non-root",
                "Diagnostic": {"Message": "Container running as root"},
                "Remediation": "Set runAsNonRoot: true",
                "Object": {"Metadata": {"FilePath": "deployment.yaml"}},
            }
        ]
    }
)


def _serve_infra_services(cluster: FakeCluster, address: str) -> None:
    """Make the fake cluster serve the infra and LLM Services at `address`, each on a node port."""
    names = [
        ("argocd-server", "argocd"),
        ("grafana", "monitoring"),
        ("prometheus-server", "monitoring"),
        ("tempo", "otel"),
        ("pyroscope", "monitoring"),
        ("ollama", "llm"),
        ("open-webui", "llm"),
        ("qdrant", "llm"),
        ("valkey", "llm"),
    ]
    cluster.core.answers["list_namespaced_service"] = [
        service(name, namespace, port=30000 + len(name), load_balancer=address)
        for name, namespace in names
    ]


def test_k8s_contexts_dry_run() -> None:
    """k8s contexts with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["contexts"])
        assert result.exit_code == 0
        assert "devops k8s contexts" in result.output
    finally:
        set_dry_run(False)


def test_k8s_status_dry_run() -> None:
    """k8s status with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "devops k8s status" in result.output
    finally:
        set_dry_run(False)


def test_k8s_bootstrap_dry_run() -> None:
    """k8s bootstrap with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["bootstrap"])
        assert result.exit_code == 0
        assert "devops k8s bootstrap" in result.output
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_dry_run() -> None:
    """k8s deploy-stack with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack"])
        assert result.exit_code == 0
        assert "devops k8s deploy-stack" in result.output
    finally:
        set_dry_run(False)


def test_k8s_teardown_stack_dry_run() -> None:
    """k8s teardown-stack with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["teardown-stack"])
        assert result.exit_code == 0
        assert "devops k8s teardown-stack" in result.output
    finally:
        set_dry_run(False)


def test_k8s_bootstrap_fails_when_minikube_stopped_and_no_auto_start(
    process_fake: ProcessFake,
) -> None:
    """k8s bootstrap --no-auto-start must fail when minikube is not running."""
    minikube_stopped(process_fake)

    result = runner.invoke(app, ["bootstrap", "--no-auto-start"])

    assert result.exit_code == 1
    assert "minikube is not running" in result.output
    assert calls_starting(process_fake, "minikube", "start") == []


def test_k8s_configure_urls_dry_run() -> None:
    """k8s configure-urls with dry-run active must print dry-run notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["configure-urls"])
        assert result.exit_code == 0
        assert "devops k8s configure-urls" in result.output
    finally:
        set_dry_run(False)


def test_k8s_configure_urls_success(
    cluster: FakeCluster,
    process_fake: ProcessFake,
    tcp_probe: TcpProbe,
    isolate_data_dir: Path,
) -> None:
    """k8s configure-urls must query service URLs and update configuration."""
    _serve_infra_services(cluster, "192.0.2.49")

    result = runner.invoke(app, ["configure-urls"])

    assert (
        result.exit_code,
        "Configured Service Targets" in result.output,
        written_keys(isolate_data_dir) != [],
    ) == (0, True, True)


# The keyring check comes first; it is not left to whichever backend an earlier test installed.
def test_k8s_deploy_stack_fails_when_cluster_unreachable(
    process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """k8s deploy-stack must fail gracefully when cluster is unreachable."""
    process_fake.answer("kubectl cluster-info", ProcessAnswer(returncode=1))

    result = runner.invoke(app, ["deploy-stack", "--context", "local-k3s"])

    assert result.exit_code == 1
    assert "Kubernetes cluster is not reachable" in result.output
    assert calls_starting(process_fake, "helm") == []


def test_deploy_stack_warns_on_kubectl_version_skew(
    cluster: FakeCluster, process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """deploy-stack warns when kubectl version skew exceeds one minor version."""
    name_contexts(cluster, "local-k3s")
    cluster.version.git_version = "v1.31.4+k3s1"
    answer_helm_version(process_fake)

    res = runner.invoke(
        app, ["deploy-stack", "--context", "local-k3s", "--no-push-secrets", "--no-wait"]
    )

    assert load_tools_lock().tools()["kubectl"].version in res.output
    assert "1.31.4" in res.output or "v1.31.4" in res.output
    assert "supported" in res.output or "skew" in res.output


def test_resolve_accessible_url_fallback(tcp_probe: TcpProbe) -> None:
    """_resolve_accessible_url falls back to localhost when minikube IP is unreachable."""
    from devops_cli.commands.k8s.networking import _resolve_accessible_url

    tcp_probe.listen_where(lambda host, port: host == "localhost")

    res = _resolve_accessible_url("http://192.0.2.49:30080")

    assert res == "http://localhost:30080"


def test_k8s_deploy_stack_llm_dry_run() -> None:
    """k8s deploy-stack --stack llm must include Ollama, Open-WebUI, Qdrant, and Valkey."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ollama" in result.output
        assert "open-webui" in result.output
        assert "qdrant" in result.output
        assert "valkey.yaml" in result.output
    finally:
        set_dry_run(False)


def _dry_run_details(output: str) -> dict[str, Any]:
    """The details of a dry-run result, after its heading."""
    details: dict[str, Any] = json.loads(output[output.index("{") :])["details"]
    return details


def test_deploy_stack_dry_run_lists_the_secrets_and_key_names_and_runs_nothing() -> None:
    """The dry run lists what the push would write, from the table alone, and runs no command."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "infra"])
        skipped = runner.invoke(app, ["deploy-stack", "--stack", "infra", "--no-push-secrets"])
    finally:
        set_dry_run(False)
    assert (
        result.exit_code,
        _dry_run_details(result.output)["secrets"],
        _dry_run_details(skipped.output)["secrets"],
    ) == (
        0,
        [
            "cloudflared/cloudflared-token: token",
            "devops/crawl4ai: CRAWL4AI_API_TOKEN (if namespace devops exists)",
            "devops/searxng: SEARXNG_SECRET (if namespace devops exists)",
            "devops/mcp-server: DEVOPS_CLI_MCP_TOKEN (if namespace devops exists)",
            "devops/devops-cli: DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY, DEVOPS_CLI_AI_API_KEY, DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS, DEVOPS_CLI_FIRECRAWL_API_KEY, DEVOPS_CLI_VALKEY_PASSWORD, DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN, DEVOPS_CLI_CRAWL4AI_API_TOKEN, DEVOPS_CLI_MCP_STAGE_TOKEN, DEVOPS_CLI_MCP_IMPLEMENT_TOKEN (if namespace devops exists)",
            "devops/qdrant-api-key: api-key (if namespace devops exists)",
            "monitoring/grafana-admin: admin-user, admin-password",
            "monitoring/grafana-image-renderer: token",
            "monitoring/alertmanager-mattermost: url",
            "argocd/argocd-notifications-secret: github-appID, github-installationID, github-privateKey, mattermost-deploys-url",
        ],
        [],
    )


def test_deploy_stack_dry_run_makes_no_request(isolate_devops_cli_config: Path) -> None:
    """No kubectl, helm or gh child, no keyring call and no connection, with the Secret push on
    and the context left to the settings."""
    _configure_service(isolate_devops_cli_config)
    result = runner.invoke(app, ["deploy-stack", "--stack", "all", "--dry-run"])
    assert (result.exit_code, result.exception) == (0, None)


def test_k8s_deploy_stack_all_dry_run(isolate_devops_cli_config: Path) -> None:
    """k8s deploy-stack --stack all must include infra, llm, logging, and devops components."""
    _configure_service(isolate_devops_cli_config)
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "all"])
        assert (
            result.exit_code,
            "argocd" in result.output,
            "k8s-monitoring" in result.output,
            "ollama" in result.output,
            "valkey.yaml" in result.output,
            "portkey" in result.output,
            "roadmap-service" in result.output,
        ) == (0, True, True, True, True, True, True)
    finally:
        set_dry_run(False)


def test_k8s_teardown_stack_llm_dry_run() -> None:
    """k8s teardown-stack --stack llm must include LLM uninstalls and deletions."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["teardown-stack", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ollama" in result.output
        assert "valkey.yaml" in result.output
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_invalid_stack() -> None:
    """k8s deploy-stack with invalid stack option must exit code 1."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "unknown-stack"])
        assert result.exit_code == 1
        assert "Invalid stack" in result.output
    finally:
        set_dry_run(False)


def test_k8s_port_forward_llm_dry_run() -> None:
    """k8s port-forward --stack llm must print LLM port forward targets."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["port-forward", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ollama" in result.output
        assert "valkey" in result.output
    finally:
        set_dry_run(False)


def test_k8s_configure_urls_llm_dry_run() -> None:
    """k8s configure-urls --stack llm must print LLM target URLs."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["configure-urls", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ai.ollama_urls" in result.output
        assert "valkey.url" in result.output
    finally:
        set_dry_run(False)


def test_require_helm_version(process_fake: ProcessFake) -> None:
    """_require_helm_version requires Helm >= 3.17 and fails on older versions (#1438)."""
    from devops_cli.commands.k8s.stack_lifecycle import _require_helm_version
    from devops_cli.exceptions.k8s import KubernetesDeployError

    answer_helm_version(process_fake, "v3.16.0")
    with pytest.raises(KubernetesDeployError, match=r"3\.16\.0"):
        _require_helm_version()

    answer_helm_version(process_fake, "v3.17.0")
    ver = _require_helm_version()
    assert str(ver) == "3.17.0"

    answer_helm_version(process_fake, "v4.3.0")
    ver = _require_helm_version()
    assert ver.major >= 4


def test_helm_version_older_than_minimum_fails(
    process_fake: ProcessFake, cluster: FakeCluster, keyring_store: FakeKeyring
) -> None:
    """deploy-stack fails with the version error when Helm is older than 3.17 (#1438)."""
    answer_helm_version(process_fake, "v3.16.2")

    res = runner.invoke(app, ["deploy-stack", "--stack", "infra", "--no-push-secrets"])

    assert res.exit_code == 1
    assert "3.16.2" in res.output
    assert calls_starting(process_fake, "helm", "upgrade") == []


def test_build_helm_upgrade_cmd_carries_take_ownership() -> None:
    """Every helm upgrade --install argv carries --take-ownership (#1438)."""
    from devops_cli.commands.k8s.stack_lifecycle import _build_helm_upgrade_cmd

    rel = {
        "name": "argocd",
        "chart": "argo/argo-cd",
        "namespace": "argocd",
        "values": "k8s/argocd/values.yaml",
        "version": "5.51.6",
    }
    cmd_v3 = _build_helm_upgrade_cmd(
        rel, ["--kube-context", "ctx"], wait=True, timeout="10m", is_v4=False
    )
    assert "--take-ownership" in cmd_v3
    assert "--force-conflicts" not in cmd_v3

    cmd_v4 = _build_helm_upgrade_cmd(
        rel, ["--kube-context", "ctx"], wait=True, timeout="10m", is_v4=True
    )
    assert "--take-ownership" in cmd_v4
    assert "--force-conflicts" in cmd_v4


def test_deploy_stack_installs_each_chart_at_the_version_that_its_application_pins() -> None:
    """`deploy-stack` installs on a cluster without Argo CD the charts that the Applications
    install with Argo CD. Renovate's `argocd` manager moves only the Application pins (#1659), so
    a chart update moves the version here too, or the two paths run different releases."""
    from devops_cli.commands.k8s.stack_lifecycle import HELM_RELEASES_BY_STACK

    installed = {
        (release["chart"].rsplit("/", 1)[-1], release["version"])
        for releases in HELM_RELEASES_BY_STACK.values()
        for release in releases
    }

    assert (bool(installed), sorted(installed - pinned_charts())) == (True, [])


def test_recover_stuck_helm_release_rolls_back_pending_upgrade(
    process_fake: ProcessFake,
) -> None:
    """A pending-upgrade release is rolled back with helm rollback before upgrade (#1438)."""
    from devops_cli.commands.k8s.stack_lifecycle import _recover_stuck_helm_release

    status_json = json.dumps({"info": {"status": "pending-upgrade"}, "version": 2})
    process_fake.answer("helm status", ProcessAnswer(stdout=status_json))
    process_fake.answer("helm rollback", ProcessAnswer(stdout="Rollback was a success!"))

    _recover_stuck_helm_release("argocd", "argocd", context="test-ctx")

    assert [call.argv for call in process_fake.calls] == [
        (
            "helm",
            "status",
            "argocd",
            "-n",
            "argocd",
            "-o",
            "json",
            "--kube-context",
            "test-ctx",
        ),
        ("helm", "rollback", "argocd", "-n", "argocd", "--kube-context", "test-ctx"),
    ]


def test_recover_stuck_helm_release_rolls_back_pending_rollback(
    process_fake: ProcessFake,
) -> None:
    """A pending-rollback release is rolled back with helm rollback before upgrade (#1438)."""
    from devops_cli.commands.k8s.stack_lifecycle import _recover_stuck_helm_release

    status_json = json.dumps({"info": {"status": "pending-rollback"}, "version": 3})
    process_fake.answer("helm status", ProcessAnswer(stdout=status_json))

    _recover_stuck_helm_release("argocd", "argocd")

    assert [call.argv for call in process_fake.calls][1:] == [
        ("helm", "rollback", "argocd", "-n", "argocd")
    ]


def test_recover_stuck_helm_release_uninstalls_pending_install(
    process_fake: ProcessFake,
) -> None:
    """A pending-install release is uninstalled with helm uninstall before upgrade (#1438)."""
    from devops_cli.commands.k8s.stack_lifecycle import _recover_stuck_helm_release

    status_json = json.dumps({"info": {"status": "pending-install"}, "version": 1})
    process_fake.answer("helm status", ProcessAnswer(stdout=status_json))

    _recover_stuck_helm_release("argocd", "argocd")

    assert [call.argv for call in process_fake.calls][1:] == [
        ("helm", "uninstall", "argocd", "-n", "argocd")
    ]


def test_recover_stuck_helm_release_deployed_does_nothing(process_fake: ProcessFake) -> None:
    """A deployed release triggers neither rollback nor uninstall (#1438)."""
    from devops_cli.commands.k8s.stack_lifecycle import _recover_stuck_helm_release

    status_json = json.dumps({"info": {"status": "deployed"}, "version": 1})
    process_fake.answer("helm status", ProcessAnswer(stdout=status_json))

    _recover_stuck_helm_release("argocd", "argocd")

    assert process_fake.call_count == 1


def test_teardown_stack_keeps_the_prometheus_operator_crds(
    cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """teardown-stack uninstalls every other infra release but never the CRD release, whose
    uninstall would delete every ServiceMonitor in the cluster; the CRDs also carry Helm's keep
    policy against an uninstall by hand (#819)."""
    from devops_cli.commands.k8s.stack_lifecycle import HELM_RELEASES_BY_STACK

    infra_names = [r["name"] for r in HELM_RELEASES_BY_STACK["infra"]]
    crd_values = yaml.safe_load(
        Path("k8s/monitoring/prometheus-operator-crds-values.yaml").read_text("utf-8")
    )

    result = runner.invoke(app, ["teardown-stack", "--stack", "infra"])

    uninstalled = [argv[2] for argv in calls_starting(process_fake, "helm", "uninstall")]
    assert (
        result.exit_code,
        "prometheus-operator-crds" in infra_names,
        uninstalled,
        crd_values["crds"]["annotations"],
    ) == (
        0,
        True,
        [name for name in reversed(infra_names) if name != "prometheus-operator-crds"],
        {"helm.sh/resource-policy": "keep"},
    )


def test_deploy_stack_with_process_fake_pending_upgrade_rolls_back(
    process_fake: ProcessFake, cluster: FakeCluster, keyring_store: FakeKeyring
) -> None:
    """When the process fake answers helm status with pending-upgrade, deploy-stack runs helm rollback before upgrade (#1438)."""
    answer_helm_version(process_fake)
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "repo"),
        ProcessAnswer(returncode=0, stdout="ok\n"),
    )
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "status"),
        ProcessAnswer(
            returncode=0,
            stdout=json.dumps({"info": {"status": "pending-upgrade"}, "version": 2}),
        ),
    )
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "rollback"),
        ProcessAnswer(returncode=0, stdout="rolled back\n"),
    )
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "upgrade"),
        ProcessAnswer(returncode=0, stdout="Release installed\n"),
    )

    res = runner.invoke(app, ["deploy-stack", "--stack", "infra", "--no-wait", "--no-push-secrets"])
    assert res.exit_code == 0

    rollback_calls = [
        call.argv for call in process_fake.calls if call.argv[:2] == ("helm", "rollback")
    ]
    upgrade_calls = [
        call.argv for call in process_fake.calls if call.argv[:2] == ("helm", "upgrade")
    ]
    assert len(rollback_calls) > 0
    assert len(upgrade_calls) > 0
    assert rollback_calls[0][:5] == (
        "helm",
        "rollback",
        "prometheus-operator-crds",
        "-n",
        "monitoring",
    )
    first_rollback_idx = next(
        i for i, call in enumerate(process_fake.calls) if call.argv[:2] == ("helm", "rollback")
    )
    first_upgrade_idx = next(
        i for i, call in enumerate(process_fake.calls) if call.argv[:2] == ("helm", "upgrade")
    )
    assert first_rollback_idx < first_upgrade_idx
    for cmd in upgrade_calls:
        assert "--take-ownership" in cmd


def test_deploy_stack_with_process_fake_pending_install_uninstalls(
    process_fake: ProcessFake, cluster: FakeCluster, keyring_store: FakeKeyring
) -> None:
    """When the process fake answers helm status with pending-install, deploy-stack runs helm uninstall (#1438)."""
    answer_helm_version(process_fake)
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "repo"),
        ProcessAnswer(returncode=0, stdout="ok\n"),
    )
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "status"),
        ProcessAnswer(
            returncode=0,
            stdout=json.dumps({"info": {"status": "pending-install"}, "version": 1}),
        ),
    )
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "uninstall"),
        ProcessAnswer(returncode=0, stdout="uninstalled\n"),
    )
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "upgrade"),
        ProcessAnswer(returncode=0, stdout="Release installed\n"),
    )

    res = runner.invoke(app, ["deploy-stack", "--stack", "infra", "--no-wait", "--no-push-secrets"])
    assert res.exit_code == 0

    uninstall_calls = [
        call.argv for call in process_fake.calls if call.argv[:2] == ("helm", "uninstall")
    ]
    upgrade_calls = [
        call.argv for call in process_fake.calls if call.argv[:2] == ("helm", "upgrade")
    ]
    assert len(uninstall_calls) > 0
    assert len(upgrade_calls) > 0
    assert uninstall_calls[0][:5] == (
        "helm",
        "uninstall",
        "prometheus-operator-crds",
        "-n",
        "monitoring",
    )
    for cmd in upgrade_calls:
        assert "--take-ownership" in cmd


def test_k8s_apply_and_logs(process_fake: ProcessFake) -> None:
    """Verify k8s apply and logs commands."""
    result = runner.invoke(app, ["apply", "k8s/infra.yaml", "--namespace", "default"])
    assert result.exit_code == 0
    assert len(process_fake.calls) == 1

    process_fake.calls.clear()
    result = runner.invoke(app, ["logs", "my-pod", "-n", "default", "--tail", "50"])
    assert result.exit_code == 0
    assert len(process_fake.calls) == 1


def test_k8s_contexts_and_switch(cluster: FakeCluster, process_fake: ProcessFake) -> None:
    """Verify k8s contexts and switch-context commands."""
    cluster.context_names[:] = ["minikube", "staging"]
    cluster.current = "minikube"
    result = runner.invoke(app, ["contexts"])
    assert result.exit_code == 0
    marked = [line for line in result.output.splitlines() if "●" in line]
    assert len(marked) == 1
    assert "minikube" in marked[0]
    assert "staging" in result.output

    minikube_running(process_fake)
    result = runner.invoke(app, ["switch-context", "minikube"])
    assert result.exit_code == 0
    assert calls_starting(process_fake, "kubectl", "config", "use-context") == [
        ("kubectl", "config", "use-context", "minikube")
    ]


def test_k8s_status(cluster: FakeCluster) -> None:
    """Verify k8s status command with cluster nodes and pods."""
    cluster.core.answers["list_node"] = [node("node-1", addresses={"InternalIP": "192.0.2.49"})]
    cluster.core.answers["list_pod_for_all_namespaces"] = [healthy_pod("pod-1")]

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "node-1" in result.output


def test_k8s_bootstrap_and_stacks(
    cluster: FakeCluster,
    process_fake: ProcessFake,
    keyring_store: FakeKeyring,
    tcp_probe: TcpProbe,
) -> None:
    """Verify k8s bootstrap, deploy-stack, and teardown-stack execution."""
    world = install_kubectl_world(process_fake)
    stock_push_keyring(keyring_store)
    minikube_running(process_fake)

    result = runner.invoke(app, ["bootstrap", "--no-auto-start", "--stack", "infra"])
    # bootstrap keeps the push on: the base rows and the infra stack's.
    pushed = [
        f"{item['metadata']['namespace']}/{item['metadata']['name']}"
        for item in world.applied_items()
    ]
    assert (result.exit_code, pushed) == (0, ["cloudflared/cloudflared-token"])

    result = runner.invoke(app, ["deploy-stack", "--stack", "infra", "--no-push-secrets"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["teardown-stack", "--stack", "infra"])
    assert result.exit_code == 0


def test_k8s_tls_secret_and_audit(tmp_path: Path, process_fake: ProcessFake) -> None:
    """Verify create-tls-secret and enable-tls commands."""
    cert_file = tmp_path / "tls.crt"
    key_file = tmp_path / "tls.key"
    cert_file.write_text("cert", encoding="utf-8")
    key_file.write_text("key", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "create-tls-secret",
            "my-tls-secret",
            "--cert",
            str(cert_file),
            "--key",
            str(key_file),
        ],
    )
    assert result.exit_code == 0

    result = runner.invoke(
        app, ["enable-tls", "--stack", "all", "--tls-dir", str(tmp_path / "tls")]
    )
    assert result.exit_code == 0


def test_k8s_security_tools_and_scans(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """Verify lint, audit, check-deprecated, and validate commands."""
    scanner_fake.script("kube-linter", ToolAnswer(exit_code=1, stdout=_KUBE_LINTER_FINDING))
    res_lint = runner.invoke(app, ["lint", str(tmp_path)])
    assert res_lint.exit_code == 1

    res_lint_dry = runner.invoke(app, ["lint", str(tmp_path), "--dry-run"])
    assert res_lint_dry.exit_code == 0

    scanner_fake.script_run_with_findings("popeye")
    res_audit = runner.invoke(app, ["audit"])
    assert res_audit.exit_code == 0

    res_audit_dry = runner.invoke(app, ["audit", "--dry-run"])
    assert res_audit_dry.exit_code == 0

    scanner_fake.script_run_with_findings("pluto", tree=tmp_path)
    res_pluto = runner.invoke(app, ["check-deprecated", str(tmp_path)])
    assert res_pluto.exit_code == 0

    res_pluto_dry = runner.invoke(app, ["check-deprecated", str(tmp_path), "--dry-run"])
    assert res_pluto_dry.exit_code == 0

    scanner_fake.script_run_with_findings("kubeconform", tree=tmp_path)
    res_val = runner.invoke(app, ["validate", str(tmp_path)])
    assert res_val.exit_code == 0

    res_val_json = runner.invoke(app, ["validate", str(tmp_path), "--json"])
    assert res_val_json.exit_code == 0


def test_k8s_lint_exit_codes(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """k8s lint exits 0 on a clean run, non-zero on findings and when kube-linter is unavailable."""
    manifest = tmp_path / "deploy.yaml"
    manifest.write_text("apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8")

    # An unavailable kube-linter fails: exit non-zero, says so, never reports a pass. The fake
    # puts a scanner on PATH only when a test scripts it, so no kube-linter is installed yet.
    res = runner.invoke(app, ["lint", str(manifest)])
    assert res.exit_code == 1
    assert "Kube-linter audit passed" not in res.output
    assert "unavailable" in res.output

    # A clean run passes: exit 0, reports the audit passed.
    scanner_fake.script("kube-linter", ToolAnswer(stdout=json.dumps({"Reports": []})))
    res = runner.invoke(app, ["lint", str(manifest)])
    assert res.exit_code == 0
    assert "Kube-linter audit passed" in res.output

    # A run with findings fails: exit non-zero, never reports a pass.
    scanner_fake.script("kube-linter", ToolAnswer(exit_code=1, stdout=_KUBE_LINTER_FINDING))
    res = runner.invoke(app, ["lint", str(manifest)])
    assert res.exit_code == 1
    assert "Kube-linter audit passed" not in res.output


def test_k8s_apply_logs_and_urls(
    tmp_path: Path, cluster: FakeCluster, process_fake: ProcessFake, tcp_probe: TcpProbe
) -> None:
    """Verify apply, logs, and configure-urls commands."""
    process_fake.answer("kubectl apply", ProcessAnswer(stdout="applied"))
    res_apply = runner.invoke(app, ["apply", "deploy.yaml", "--dry-run", "--namespace", "test-ns"])
    assert res_apply.exit_code == 0

    res_apply_real = runner.invoke(app, ["apply", "deploy.yaml", "--namespace", "test-ns"])
    assert res_apply_real.exit_code == 0

    process_fake.answer("kubectl logs", ProcessAnswer(stdout="logs"))
    res_logs_f = runner.invoke(
        app, ["logs", "my-pod", "-c", "my-container", "-n", "test-ns", "--follow"]
    )
    assert res_logs_f.exit_code == 0

    _serve_infra_services(cluster, "192.0.2.49")
    res_urls = runner.invoke(app, ["configure-urls", "--stack", "infra"])
    assert res_urls.exit_code == 0


def test_k8s_helpers_and_error_branches(
    tmp_path: Path,
    process_fake: ProcessFake,
    cluster: FakeCluster,
    clock: ClockFake,
    tcp_probe: TcpProbe,
) -> None:
    """Verify k8s client error branches and URL detection helpers."""
    from devops_cli.commands.k8s.networking import (
        _detect_service_url,
        _extract_first_node_ip,
        _parse_minikube_service_url,
        _resolve_k8s_node_port_url,
    )

    # 1. _parse_minikube_service_url
    assert (
        _parse_minikube_service_url("Starting...\nhttp://192.0.2.49:30000\nDone")
        == "http://192.0.2.49:30000"
    )
    assert (
        _parse_minikube_service_url("Starting...\nHTTPS://192.0.2.49:30000\nDone")
        == "HTTPS://192.0.2.49:30000"
    )
    assert _parse_minikube_service_url("No URLs here") is None

    # 2. _extract_first_node_ip
    node_data = {
        "status": {
            "addresses": [
                {"type": "InternalIP", "address": "192.0.2.49"},
                {"type": "Hostname", "address": "minikube"},
            ]
        }
    }
    assert _extract_first_node_ip(node_data) == "192.0.2.49"
    assert _extract_first_node_ip({}) is None

    # 3. _resolve_k8s_node_port_url
    mock_nodes_json = json.dumps({"items": [node_data]})
    process_fake.answer("kubectl get nodes", ProcessAnswer(stdout=mock_nodes_json))
    url = _resolve_k8s_node_port_url([], 30080)
    assert url == "http://192.0.2.49:30080"

    # 4. _detect_service_url with fallback
    process_fake.answer("minikube service", ProcessAnswer(stdout="http://192.0.2.49:31434"))
    res_svc = _detect_service_url("ollama", "llm", context="minikube")
    assert res_svc == "http://192.0.2.49:31434"

    # 5. create-tls-secret missing files
    res_missing_cert = runner.invoke(
        app,
        [
            "create-tls-secret",
            "my-secret",
            "--cert",
            str(tmp_path / "nonexistent.crt"),
            "--key",
            str(tmp_path / "key.pem"),
        ],
    )
    assert res_missing_cert.exit_code == 1

    # 6. status failure: the API server does not answer
    cluster.unreachable()
    res_stat_fail = runner.invoke(app, ["status"])
    assert res_stat_fail.exit_code == 1

    # 7. port-forward command execution, recording its forwards under the test's data directory
    process_fake.calls.clear()
    res_pf = runner.invoke(app, ["port-forward", "--stack", "infra"])
    assert res_pf.exit_code == 0
    assert calls_starting(process_fake, "kubectl", "port-forward") != []


def test_k8s_contexts_fail_when_the_kubeconfig_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`contexts` exits 1 when no kubeconfig can be read."""
    broken = tmp_path / "kubeconfig"
    broken.write_text("contexts: [unclosed", encoding="utf-8")
    monkeypatch.setenv("KUBECONFIG", str(broken))

    res_ctx_fail = runner.invoke(app, ["contexts"])

    assert res_ctx_fail.exit_code == 1


def test_k8s_extended_subcommands(
    tmp_path: Path, cluster: FakeCluster, process_fake: ProcessFake, scanner_fake: ScannerFake
) -> None:
    """Verify switch-context, teardown-stack, enable-tls, check-deprecated, lint, audit, and validate."""
    # 1. switch-context
    cluster.context_names.append("minikube")
    minikube_running(process_fake)
    res_switch = runner.invoke(app, ["switch-context", "minikube"])
    assert res_switch.exit_code == 0

    # 2. teardown-stack
    res_td = runner.invoke(app, ["teardown-stack", "--stack", "infra"])
    assert res_td.exit_code == 0

    # 3. enable-tls
    tls_cert = tmp_path / "server.crt"
    tls_key = tmp_path / "server.key"
    tls_cert.write_text("CERT", encoding="utf-8")
    tls_key.write_text("KEY", encoding="utf-8")

    res_tls = runner.invoke(
        app,
        [
            "enable-tls",
            "--stack",
            "infra",
            "--tls-dir",
            str(tmp_path),
        ],
    )
    assert res_tls.exit_code == 0

    # 4. lint, audit, check-deprecated, validate
    manifest = tmp_path / "deploy.yaml"
    manifest.write_text("apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8")
    scanner_fake.script("kube-linter", ToolAnswer(stdout=json.dumps({"Reports": []})))
    scanner_fake.script("popeye", ToolAnswer(stdout=json.dumps({"popeye": {"sections": []}})))
    scanner_fake.script("pluto", ToolAnswer(stdout=json.dumps({"items": []})))
    scanner_fake.script("kubeconform", ToolAnswer(stdout=json.dumps({"resources": []})))

    res_lint = runner.invoke(app, ["lint", str(manifest)])
    assert res_lint.exit_code == 0

    res_audit = runner.invoke(app, ["audit"])
    assert res_audit.exit_code == 0

    res_depr = runner.invoke(app, ["check-deprecated", str(manifest)])
    assert res_depr.exit_code == 0

    res_val = runner.invoke(app, ["validate", str(manifest)])
    assert res_val.exit_code == 0


def test_k8s_service_url_helpers(process_fake: ProcessFake, tcp_probe: TcpProbe) -> None:
    from devops_cli.commands.k8s.networking import (
        _extract_first_node_ip,
        _parse_minikube_service_url,
        _resolve_accessible_url,
        _resolve_k8s_node_port_url,
        _verify_url_reachability,
    )

    # 1. _parse_minikube_service_url
    assert _parse_minikube_service_url("") is None
    assert (
        _parse_minikube_service_url("Starting tunnel\nhttp://192.0.2.49:30001\nDone")
        == "http://192.0.2.49:30001"
    )

    # 2. _extract_first_node_ip
    node_data_ext = {
        "status": {
            "addresses": [
                {"type": "InternalIP", "address": "192.0.2.49"},
                {"type": "Hostname", "address": "minikube"},
            ]
        }
    }
    assert _extract_first_node_ip(node_data_ext) == "192.0.2.49"
    assert _extract_first_node_ip({}) is None

    # 3. _resolve_k8s_node_port_url
    nodes_json = json.dumps({"items": [node_data_ext]})
    process_fake.answer("kubectl get nodes", ProcessAnswer(stdout=nodes_json))
    url = _resolve_k8s_node_port_url([], 30080)
    assert url == "http://192.0.2.49:30080"

    # 4. _verify_url_reachability
    assert _verify_url_reachability("http://example.com:80") is False

    # 5. _resolve_accessible_url
    assert _resolve_accessible_url(None) is None
    tcp_probe.listen_where(lambda host, port: True)
    assert (
        _resolve_accessible_url("http://192.0.2.49:3000", preferred_localhost_ports=[3000]),
        _resolve_accessible_url("http://192.0.2.49:3000"),
    ) == (
        "http://192.0.2.49:3000",
        "http://192.0.2.49:3000",
    )
    tcp_probe.refuse_all()
    tcp_probe.listen_where(lambda host, port: host in ("localhost", "127.0.0.1"))
    assert (
        _resolve_accessible_url("http://192.0.2.49:3000", preferred_localhost_ports=[3000])
        == "http://localhost:3000"
    )


@pytest.mark.usefixtures("keyring_store")
def test_k8s_bootstrap_openwebui(process_fake: ProcessFake) -> None:
    """Verify bootstrap-openwebui dry-run, success, and failure paths."""
    # Dry-run
    set_dry_run(True)
    try:
        res_dry = runner.invoke(app, ["bootstrap-openwebui", "--email", "admin@localhost"])
        assert res_dry.exit_code == 0
        assert "bootstrap_openwebui_admin" in res_dry.output
    finally:
        set_dry_run(False)

    def open_webui_answers(created: str = "CREATED\n") -> None:
        process_fake.reset()
        process_fake.answer("kubectl get pods", ProcessAnswer(stdout="open-webui-0\n"))
        process_fake.answer("kubectl exec", ProcessAnswer(stdout=created))

    # Success execution
    open_webui_answers()
    res_ok = runner.invoke(
        app,
        [
            "bootstrap-openwebui",
            "--email",
            "admin@localhost",
            "--password",
            "admin123",
            "--context",
            "minikube",
        ],
    )
    assert res_ok.exit_code == 0
    assert "admin@localhost" in res_ok.output

    # Non-localhost email PII masking
    open_webui_answers()
    res_pii = runner.invoke(
        app,
        [
            "bootstrap-openwebui",
            "--email",
            "developer@example.com",
            "--password",
            "admin123",
        ],
    )
    assert res_pii.exit_code == 0
    assert "de***@example.com" in res_pii.output
    assert "developer@example.com" not in res_pii.output

    # Generated password when --password is omitted (masked by default)
    open_webui_answers()
    res_gen = runner.invoke(app, ["bootstrap-openwebui", "--email", "admin@localhost"])
    assert res_gen.exit_code == 0
    assert "Generated secure Open-WebUI admin password" in res_gen.output
    assert "(use --show-password to reveal)" in res_gen.output
    assert "admin123" not in res_gen.output

    # Generated password with --show-password reveals in plain text
    open_webui_answers()
    res_show = runner.invoke(
        app, ["bootstrap-openwebui", "--email", "admin@localhost", "--show-password"]
    )
    assert res_show.exit_code == 0
    assert "Generated secure Open-WebUI admin password" in res_show.output
    assert "(use --show-password to reveal)" not in res_show.output

    # Rerun when account already exists does not claim to generate new password
    open_webui_answers("EXISTING\n")
    res_exist = runner.invoke(app, ["bootstrap-openwebui", "--email", "admin@localhost"])
    assert res_exist.exit_code == 0
    assert "already initialized" in res_exist.output
    assert "Generated secure Open-WebUI admin password" not in res_exist.output

    # Pod not found failure
    process_fake.reset()
    process_fake.answer("kubectl get pods", ProcessAnswer(returncode=1))
    res_fail = runner.invoke(app, ["bootstrap-openwebui"])
    assert res_fail.exit_code == 1


def test_k8s_deploy_stack_no_wait(
    cluster: FakeCluster, process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """Verify k8s deploy-stack with --no-wait omits --wait flag in helm upgrade command."""
    set_dry_run(True)
    try:
        res = runner.invoke(app, ["deploy-stack", "--stack", "infra", "--no-wait"])
        assert res.exit_code == 0
        assert '"wait": false' in res.output
    finally:
        set_dry_run(False)

    answer_helm_version(process_fake, "v4.3.0")
    res_exec = runner.invoke(
        app, ["deploy-stack", "--stack", "infra", "--no-wait", "--no-push-secrets"]
    )
    helm_cmds = [list(argv) for argv in calls_starting(process_fake, "helm", "upgrade")]
    assert res_exec.exit_code == 0
    assert len(helm_cmds) > 0
    for cmd in helm_cmds:
        assert "--wait" not in cmd
        assert "--force-conflicts" in cmd
        assert "--take-ownership" in cmd

    process_fake.calls.clear()
    answer_helm_version(process_fake, "v3.17.0")
    res_exec = runner.invoke(
        app, ["deploy-stack", "--stack", "infra", "--no-wait", "--no-push-secrets"]
    )
    assert res_exec.exit_code == 0
    helm_cmds = [list(argv) for argv in calls_starting(process_fake, "helm", "upgrade")]
    assert len(helm_cmds) > 0
    for cmd in helm_cmds:
        assert "--wait" not in cmd
        assert "--force-conflicts" not in cmd
        assert "--take-ownership" in cmd


def test_k8s_workload_resource_limits_and_probes() -> None:
    """Verify workload resource limits, relaxed memory constraints, and resilient probes."""

    # 1. Ollama DaemonSet: requests 8Gi and 3000m, robust startup, readiness and liveness probes.
    # test_ollama_16gib_tier_limits_its_memory_to_its_request checks its memory limit (#5115).
    ollama_path = REPO_ROOT / "k8s" / "llm" / "profiles" / "ollama-profiles.yaml"
    ollama_docs = list(yaml.safe_load_all(ollama_path.read_text(encoding="utf-8")))
    dep = next(d for d in ollama_docs if d and d.get("kind") in ("Deployment", "DaemonSet"))
    container = dep["spec"]["template"]["spec"]["containers"][0]
    resources = container.get("resources", {})
    startup = container["startupProbe"]
    readiness = container["readinessProbe"]
    liveness = container["livenessProbe"]
    volumes = dep["spec"]["template"]["spec"]["volumes"]
    ollama_vol = next(v for v in volumes if v["name"] == "ollama-data")

    assert (
        ollama_path.is_file(),
        resources["requests"]["memory"],
        resources["requests"]["cpu"],
        startup["initialDelaySeconds"],
        startup["periodSeconds"],
        startup["timeoutSeconds"],
        startup["failureThreshold"],
        ollama_vol["hostPath"]["path"],
        ollama_vol["hostPath"]["type"],
        readiness["initialDelaySeconds"],
        readiness["periodSeconds"],
        readiness["timeoutSeconds"],
        readiness["failureThreshold"],
        liveness["initialDelaySeconds"],
        liveness["periodSeconds"],
        liveness["timeoutSeconds"],
        liveness["failureThreshold"],
    ) == (
        True,
        "8Gi",
        "3000m",
        10,
        5,
        5,
        60,
        "/var/lib/ollama",
        "DirectoryOrCreate",
        5,
        10,
        5,
        3,
        15,
        15,
        10,
        6,
    )

    # 2. Valkey: memory limit >= 2048Mi
    valkey_docs = list(
        yaml.safe_load_all((REPO_ROOT / "k8s" / "llm" / "valkey.yaml").read_text(encoding="utf-8"))
    )
    valkey_dep = next(d for d in valkey_docs if d and d.get("kind") == "Deployment")
    valkey_res = valkey_dep["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert valkey_res["limits"]["memory"] == "2048Mi"

    # The redis_exporter sidecars use 21m or less, but CFS throttled them in 52 to 69% of
    # the periods of 7 d at a 100m limit, and a throttled scrape is slow (#4991).
    devops_valkey_docs = list(
        yaml.safe_load_all(
            (REPO_ROOT / "k8s" / "llm" / "valkey-devops.yaml").read_text(encoding="utf-8")
        )
    )
    devops_valkey_dep = next(d for d in devops_valkey_docs if d and d.get("kind") == "Deployment")
    exporter_cpu_limits = [
        container["resources"]["limits"]["cpu"]
        for dep in (valkey_dep, devops_valkey_dep)
        for container in dep["spec"]["template"]["spec"]["containers"]
        if container["name"] == "redis-exporter"
    ]
    assert exporter_cpu_limits == ["500m", "500m"]

    # 3. Tempo: memory limit >= 2048Mi
    tempo_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "otel" / "tempo-values.yaml").read_text(encoding="utf-8")
    )
    assert tempo_values["tempo"]["resources"]["limits"]["memory"] == "2048Mi"

    # 5. ArgoCD values: elevated memory limits
    argo_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "argocd" / "values.yaml").read_text(encoding="utf-8")
    )
    assert argo_values["controller"]["resources"]["limits"]["memory"] == "2048Mi"
    assert argo_values["repoServer"]["resources"]["limits"]["memory"] == "4096Mi"
    assert argo_values["server"]["resources"]["limits"]["memory"] == "1024Mi"
    assert argo_values["redis"]["resources"]["limits"]["memory"] == "1024Mi"
    assert argo_values["redis"]["exporter"]["resources"]["limits"]["cpu"] == "500m"

    # 6. Open WebUI values: elevated CPU and memory limits
    webui_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "llm" / "values-open-webui.yaml").read_text(encoding="utf-8")
    )
    assert webui_values["resources"]["limits"]["cpu"] == "4000m"
    assert webui_values["resources"]["limits"]["memory"] == "4Gi"

    # 7. OTel values: elevated CPU and memory limits
    otel_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "otel" / "values.yaml").read_text(encoding="utf-8")
    )
    assert otel_values["resources"]["limits"]["cpu"] == "1000m"
    assert otel_values["resources"]["limits"]["memory"] == "1024Mi"

    # 8. Loki values: elevated singleBinary limits
    loki_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "logging" / "loki-values.yaml").read_text(encoding="utf-8")
    )
    assert loki_values["singleBinary"]["resources"]["limits"]["cpu"] == "1000m"
    assert loki_values["singleBinary"]["resources"]["limits"]["memory"] == "2048Mi"

    # 10. K8s monitoring stack values: elevated requests and limits to eliminate OOM kills, and a
    #     node-exporter CPU limit that does not throttle the scrape. The Alloy limits are 2 times
    #     the 7 d peak or more (#4991).
    k8s_mon_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "monitoring" / "k8s-monitoring-values.yaml").read_text(
            encoding="utf-8"
        )
    )
    ksm_res = k8s_mon_values["telemetryServices"]["kube-state-metrics"]["resources"]
    node_res = k8s_mon_values["telemetryServices"]["node-exporter"]["resources"]
    alloy_metrics_res = k8s_mon_values["collectors"]["alloy-metrics"]["alloy"]["resources"]
    alloy_logs_res = k8s_mon_values["collectors"]["alloy-logs"]["alloy"]["resources"]
    assert (
        ksm_res["requests"]["memory"],
        ksm_res["limits"]["memory"],
        node_res["requests"]["memory"],
        node_res["limits"]["memory"],
        node_res["limits"]["cpu"],
        alloy_metrics_res["requests"]["memory"],
        alloy_metrics_res["limits"]["memory"],
        alloy_logs_res["limits"]["memory"],
    ) == (
        "64Mi",
        "256Mi",
        "64Mi",
        "256Mi",
        "500m",
        "256Mi",
        "1536Mi",
        "768Mi",
    )

    # Grafana: its 7 d peak was 1014 MiB of a 1024Mi limit (#4991).
    grafana_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "monitoring" / "grafana-values.yaml").read_text(encoding="utf-8")
    )
    assert grafana_values["resources"] == {
        "requests": {"cpu": "100m", "memory": "512Mi"},
        "limits": {"cpu": "500m", "memory": "2Gi"},
    }

    # 11. GPU Feature Discovery DaemonSet: Burstable QoS requests and limits
    gfd_docs = list(
        yaml.safe_load_all(
            (REPO_ROOT / "k8s" / "gpu-feature-discovery" / "daemonset.yaml").read_text(
                encoding="utf-8"
            )
        )
    )
    gfd_ds = next(d for d in gfd_docs if d and d.get("kind") == "DaemonSet")
    gfd_container = gfd_ds["spec"]["template"]["spec"]["containers"][0]
    assert gfd_container["image"] == "nvcr.io/nvidia/k8s-device-plugin:v0.16.2"
    gfd_res = gfd_container["resources"]
    assert gfd_res["requests"]["cpu"] == "50m"
    assert gfd_res["requests"]["memory"] == "64Mi"
    assert gfd_res["limits"]["cpu"] == "200m"
    assert gfd_res["limits"]["memory"] == "256Mi"


# =============================================================================
# No In-Cluster Image Registry (#1630)
# =============================================================================


# =============================================================================
# Thirty Days Of Logs And Metrics (#550)
# =============================================================================


def _repo_yaml(*parts: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(REPO_ROOT.joinpath(*parts).read_text(encoding="utf-8"))
    return loaded


def _volume_alerts() -> dict[str, dict[str, Any]]:
    """The `log-and-metric-retention` group's rules, by alert name.

    The server's other groups (#549) are pinned in `tests/test_k8s_monitoring_alerting.py`.
    """
    values = _repo_yaml("k8s", "monitoring", "prometheus-values.yaml")
    groups = values["serverFiles"]["alerting_rules.yml"]["groups"]
    (group,) = [group for group in groups if group["name"] == "log-and-metric-retention"]
    return {rule["alert"]: rule for rule in group["rules"]}


def test_loki_deletes_logs_once_they_are_thirty_days_old() -> None:
    """`retention_period` is applied only by the compactor, and only with retention on.

    Without `compactor.retention_enabled` Loki kept every chunk whatever its age. Loki 3
    refuses to start with retention on and no delete-request store, and that store opens
    the unauthenticated log delete API, which `deletion_mode: disabled` closes.
    """
    loki = _repo_yaml("k8s", "logging", "loki-values.yaml")["loki"]
    compactor, limits = loki["compactor"], loki["limits_config"]
    assert (
        compactor["retention_enabled"],
        compactor["delete_request_store"],
        limits["retention_period"],
        limits["deletion_mode"],
    ) == (True, "filesystem", "720h", "disabled")


def test_loki_discovers_log_levels_for_the_warnings_and_errors_panel() -> None:
    """The Warnings & Errors (Loki) panel of sre-service.json depends on discover_log_levels."""
    loki = _repo_yaml("k8s", "logging", "loki-values.yaml")["loki"]
    assert loki["limits_config"]["discover_log_levels"] is True
    raw = REPO_ROOT.joinpath("k8s", "logging", "loki-values.yaml").read_text(encoding="utf-8")
    assert "Warnings & Errors (Loki)" in raw


def test_both_volumes_hold_thirty_days_and_no_size_cap_cuts_them_short() -> None:
    """Loki's volume holds 30 days of logs; Prometheus keeps 30 days under a looser size cap."""
    loki = _repo_yaml("k8s", "logging", "loki-values.yaml")["singleBinary"]["persistence"]
    server = _repo_yaml("k8s", "monitoring", "prometheus-values.yaml")["server"]
    assert (
        loki["enabled"],
        loki["size"],
        server["retention"],
        server["retentionSize"],
        server["persistentVolume"]["size"],
    ) == (True, "20Gi", "30d", "16GB", "20Gi")


def test_an_alert_fires_before_the_log_or_metric_volume_fills() -> None:
    """Each alert is well-formed, waits out blips, and reads series that exist.

    The disk alert follows Loki's and Prometheus's claims to the node holding them, since
    local-path does not hold a volume to its claimed size. The size-cap alert reads only
    series the Prometheus server serves about itself (`tests/fixtures/metrics/`).
    """
    alerts = _volume_alerts()
    disk, cap = alerts["LogOrMetricVolumeDiskLow"], alerts["PrometheusNearRetentionSizeCap"]
    server = FIXTURES / "metrics" / "prometheus-server.yaml"
    served = yaml.safe_load(server.read_text(encoding="utf-8"))["families"]
    cap_series = {selector.metric for selector in selectors(cap["expr"])}
    assert (
        sorted(alerts),
        all(validate_promql(rule["expr"]).valid for rule in alerts.values()),
        all(rule["labels"]["severity"] == "warning" for rule in alerts.values()),
        (disk["for"], cap["for"]),
        'persistentvolumeclaim=~"storage-loki-0|prometheus-server"' in disk["expr"],
        cap_series <= served.keys(),
        "prometheus_tsdb_retention_limit_bytes" in cap_series,
    ) == (
        ["LogOrMetricVolumeDiskLow", "PrometheusNearRetentionSizeCap"],
        True,
        True,
        ("30m", "1h"),
        True,
        True,
        True,
    )


def test_k8s_stack_deploy_ssa_and_manifest_contracts() -> None:
    """Verify deploy-stack enforces --force-conflicts and k8s manifests meet security & chart contracts."""

    # 1. Namespaces: logging has baseline pod-security standard
    ns_docs = list(
        yaml.safe_load_all((REPO_ROOT / "k8s" / "namespaces.yaml").read_text(encoding="utf-8"))
    )
    logging_ns = next(d for d in ns_docs if d and d.get("metadata", {}).get("name") == "logging")
    assert (
        logging_ns["metadata"]["labels"]["pod-security.kubernetes.io/enforce"],
        logging_ns["metadata"]["labels"]["pod-security.kubernetes.io/warn"],
        logging_ns["metadata"]["labels"]["pod-security.kubernetes.io/audit"],
    ) == ("baseline", "baseline", "baseline")

    # 2. Loki values: zeroed scalable target replicas for Monolithic mode
    loki_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "logging" / "loki-values.yaml").read_text(encoding="utf-8")
    )
    assert (
        loki_values["read"]["replicas"],
        loki_values["write"]["replicas"],
        loki_values["backend"]["replicas"],
    ) == (0, 0, 0)

    # 3. Qdrant values: disabled unprivileged volume chown initContainer
    qdrant_values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "llm" / "values-qdrant.yaml").read_text(encoding="utf-8")
    )
    assert qdrant_values["updateVolumeFsOwnership"] is False


def test_mask_email_display_variants() -> None:
    """Verify _mask_email_display masks short and long emails while preserving localhost/internal."""
    from devops_cli.commands.k8s.stack_lifecycle import _mask_email_display

    assert _mask_email_display("admin@localhost") == "admin@localhost"
    assert _mask_email_display("user@corp.local") == "user@corp.local"
    assert _mask_email_display("svc@dev.internal") == "svc@dev.internal"

    assert _mask_email_display("alice@example.com") == "al***@example.com"
    assert _mask_email_display("ab@example.com") == "a***@example.com"
    assert _mask_email_display("a@example.com") == "a***@example.com"
    assert _mask_email_display("invalid") == "***"


def test_bootstrap_openwebui_dry_run_masks_email(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify bootstrap_openwebui dry-run outputs masked email in target and details."""
    from devops_cli.commands.k8s.stack_lifecycle import bootstrap_openwebui
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        bootstrap_openwebui(email="operator@example.com")
    finally:
        set_dry_run(False)

    captured = capsys.readouterr()
    assert "operator@example.com" not in captured.out
    assert "op***@example.com" in captured.out


def test_is_helm_v4_or_newer_capability_detection(process_fake: ProcessFake) -> None:
    from devops_cli.commands.k8s.stack_lifecycle import _is_helm_v4_or_newer

    def helm_says(stdout: str, returncode: int = 0) -> None:
        process_fake.answer("helm version", ProcessAnswer(returncode=returncode, stdout=stdout))

    # Helm v4 returns True
    helm_says("v4.0.1\n")
    assert _is_helm_v4_or_newer() is True

    # Helm v3 returns False
    helm_says("v3.16.2\n")
    assert _is_helm_v4_or_newer() is False

    # Command failure returns False
    helm_says("", returncode=1)
    assert _is_helm_v4_or_newer() is False

    # Empty stdout returns False
    helm_says("")
    assert _is_helm_v4_or_newer() is False

    # Malformed output returns False
    helm_says("invalid-version\n")
    assert _is_helm_v4_or_newer() is False


def test_extract_service_url_ingress_and_nodeport(process_fake: ProcessFake) -> None:
    """Verify LoadBalancer ingress and NodePort extraction from service spec."""
    from devops_cli.commands.k8s.networking import _extract_service_ingress_or_nodeport

    ingress_svc = {
        "spec": {"ports": [{"port": 8080}]},
        "status": {"loadBalancer": {"ingress": [{"ip": "1.2.3.4"}]}},
    }
    url_ingress = _extract_service_ingress_or_nodeport(ingress_svc, [])

    nodeport_svc = {
        "spec": {"ports": [{"port": 80, "nodePort": 30080}]},
    }
    loopback_node = {"status": {"addresses": [{"type": "InternalIP", "address": "127.0.0.1"}]}}
    process_fake.answer(
        "kubectl get nodes", ProcessAnswer(stdout=json.dumps({"items": [loopback_node]}))
    )
    url_nodeport = _extract_service_ingress_or_nodeport(nodeport_svc, [])

    url_empty = _extract_service_ingress_or_nodeport({}, [])

    assert (url_ingress, url_nodeport, url_empty) == (
        "http://1.2.3.4:8080",
        "http://127.0.0.1:30080",
        None,
    )


def test_pyroscope_helm_release_and_grafana_datasource() -> None:
    """Verify Pyroscope is configured as an infra Helm release and provisioned in Grafana."""
    from devops_cli.commands.k8s.stack_lifecycle import (
        _HELM_REPOS_BY_STACK,
        HELM_RELEASES_BY_STACK,
    )

    pyro_release = next(
        (r for r in HELM_RELEASES_BY_STACK["infra"] if r["name"] == "pyroscope"), None
    )
    assert pyro_release is not None

    values_path = Path(pyro_release["values"])
    assert values_path.is_file()
    pyro_values = yaml.safe_load(values_path.read_text(encoding="utf-8"))

    grafana_values = yaml.safe_load(
        Path("k8s/monitoring/grafana-values.yaml").read_text(encoding="utf-8")
    )
    k8s_mon_values = yaml.safe_load(
        Path("k8s/monitoring/k8s-monitoring-values.yaml").read_text(encoding="utf-8")
    )
    grafana_datasources = grafana_values["datasources"]["datasources.yaml"]["datasources"]
    pyro_ds = next((ds for ds in grafana_datasources if ds.get("uid") == "pyroscope"), None)

    assert (
        (pyro_release["chart"], pyro_release["namespace"]),
        pyro_release["chart"].split("/")[0] in _HELM_REPOS_BY_STACK["infra"],
        pyro_values["pyroscope"]["service"]["port"],
        pyro_values["architecture"]["microservices"]["enabled"],
        k8s_mon_values["collectors"]["alloy-profiles"]["alloy"]["enableReporting"],
        pyro_ds is not None,
        (pyro_ds["type"], pyro_ds["url"]) if pyro_ds else None,
    ) == (
        ("grafana/pyroscope", "monitoring"),
        True,
        4040,
        False,
        False,
        True,
        ("grafana-pyroscope-datasource", "http://pyroscope.monitoring.svc.cluster.local:4040"),
    )


def test_pyroscope_port_forward_and_proxy_targets() -> None:
    """Verify Pyroscope networking, port-forwarding, and configuration targets."""
    from devops_cli.commands.k8s.networking import (
        _NODEPORT_KEYS_INFRA,
        _PROXY_TARGETS_INFRA,
        _build_port_forward_details,
        _collect_port_forward_services,
    )
    from devops_cli.config.defaults import DEFAULT_PYROSCOPE_PORT, DEFAULT_PYROSCOPE_URL
    from devops_cli.config.settings import Settings

    pyro_proxy = next((t for t in _PROXY_TARGETS_INFRA if t[0] == "pyroscope.url"), None)
    ports = {
        "argocd": 8080,
        "grafana": 8030,
        "prometheus": 8090,
        "tempo": 3200,
        "pyroscope": 4040,
        "otel": 4318,
    }
    services = _collect_port_forward_services(["infra"], ports)
    details = _build_port_forward_details(["infra"], ports)
    pyro_svc = next((s for s in services if s[1] == "svc/pyroscope"), None)

    assert (
        DEFAULT_PYROSCOPE_PORT,
        DEFAULT_PYROSCOPE_URL,
        pyro_proxy,
        "pyroscope.url" in _NODEPORT_KEYS_INFRA,
        pyro_svc,
        details.get("pyroscope.url"),
        Settings().pyroscope.url,
    ) == (
        4040,
        "http://localhost:4040",
        ("pyroscope.url", "monitoring", ("pyroscope",), ("4040", "http2", "http")),
        True,
        ("monitoring", "svc/pyroscope", 4040, 4040),
        "http://localhost:4040",
        None,
    )


def test_is_cluster_argo_managed(cluster: FakeCluster) -> None:
    """_is_cluster_argo_managed probes Application 'cluster' in argocd namespace via ArgoCRDService."""
    from devops_cli.commands.k8s.stack_lifecycle import _is_cluster_argo_managed
    from devops_cli.exceptions.argo import ArgoError

    # No Application 'cluster': the API answers 404
    assert _is_cluster_argo_managed() is False

    argo_cd_manages_the_cluster(cluster)
    cluster.custom_objects.calls.clear()
    assert _is_cluster_argo_managed() is True
    assert [
        (name, kwargs["plural"], kwargs["name"], kwargs["namespace"])
        for name, kwargs in cluster.custom_objects.calls
    ] == [("get_namespaced_custom_object", "applications", "cluster", "argocd")]

    cluster.custom_objects.fail(
        "get_namespaced_custom_object", api_exception(403, "apiserver 403 forbidden")
    )
    with pytest.raises(ArgoError) as exc_info:
        _is_cluster_argo_managed()
    assert "403 forbidden" in str(exc_info.value)


# The configured domain has to differ from the repository's placeholder, example.com, for a
# substitution to show; example.org is reserved for documentation by RFC 2606 like example.com.
_DOMAIN = "example.org"
_CONTEXT = ["--context", "minikube"]


def _ingress(name: str, namespace: str, *hosts: str) -> str:
    rules = "".join(f"    - host: {host}\n" for host in hosts)
    return (
        "apiVersion: networking.k8s.io/v1\nkind: Ingress\n"
        f"metadata:\n  name: {name}\n  namespace: {namespace}\nspec:\n  rules:\n{rules}"
    )


@pytest.fixture
def applications_repo(tmp_path: Path) -> Path:
    """The repository the Applications render."""
    repo = tmp_path / "applications"
    repo.mkdir()
    return repo


type ClusterFactory = Callable[..., "_Cluster"]


@pytest.fixture
def make_cluster(
    applications_repo: Path, process_fake: ProcessFake, cluster: FakeCluster
) -> ClusterFactory:
    """Build the kubectl and git stand-in around a reachable cluster, over the fake API."""

    def make(**options: Any) -> _Cluster:
        return _Cluster(applications_repo, process_fake, cluster, **options)

    return make


_SERVER_SIDE_APPLY = ["kubectl", "apply", "--server-side"]


class _Cluster:
    """kubectl and git around a reachable cluster, Argo CD-managed unless `argo` is False.

    Calls that read or write the cluster are recorded and answered here; git and
    `kubectl kustomize` run for real, against the Applications' repository. Each Application
    renders `k8s/overlays/homelab/<name>` at `main` unless `paths` says otherwise, and a write
    naming `fail` exits 1.
    """

    def __init__(
        self,
        repo: Path,
        process_fake: ProcessFake,
        api: FakeCluster,
        *,
        argo: bool = True,
        fail: str | None = None,
        paths: dict[str, str] | None = None,
        missing_crds: tuple[str, ...] = (),
    ) -> None:
        self.calls: list[tuple[list[str], str | None]] = []
        self.repo = repo
        self.argo = argo
        self.fail = fail
        self.paths = paths or {}
        self.missing_crds = missing_crds
        self.namespaces = {"llm", "cloudflared", "devops"}
        self.revision = "main"
        process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=self))
        name_contexts(api, "minikube")
        if argo:
            argo_cd_manages_the_cluster(api)

    def __call__(self, call: ProcessCall) -> subprocess.CompletedProcess[str]:
        cmd, input = list(call.argv), call.stdin if isinstance(call.stdin, str) else None
        self.calls.append((cmd, input))
        if cmd[0] == "git":
            if "fetch" in cmd:
                self.revision = cmd[-1]
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if len(cmd) > 1 and cmd[1] == "kustomize":
            return self._kustomize(cmd)
        if cmd[0] == "helm" and len(cmd) > 1 and cmd[1] == "version":
            return subprocess.CompletedProcess(cmd, 0, "v4.3.0", "")
        if cmd[1:3] == ["get", "application"]:
            path = self.paths.get(cmd[3], f"k8s/overlays/homelab/{cmd[3]}")
            source = {"repoURL": self.repo.as_uri(), "targetRevision": "main", "path": path}
            return subprocess.CompletedProcess(cmd, 0, json.dumps({"spec": {"source": source}}), "")
        if cmd[1] == "api-resources":
            return self._api_resources(cmd)
        if cmd[1:3] == ["get", "namespace"]:
            found = f"namespace/{cmd[3]}\n" if cmd[3] in self.namespaces else ""
            return subprocess.CompletedProcess(cmd, 0, found, "")
        failed = self.fail is not None and self.fail in cmd
        return subprocess.CompletedProcess(cmd, int(failed), "", "denied" if failed else "")

    def _kustomize(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        target = cmd[2] if len(cmd) > 2 else ""
        if "missing" in target:
            return subprocess.CompletedProcess(
                cmd, 1, "", f"kubectl kustomize: error reading {target}"
            )
        if Path(target).name == "devops":
            out = _ingress("roadmap-service", "devops", "hooks.example.com")
        elif self.revision == "pinned":
            out = _ingress("chat", "llm", "chat.example.org")
        elif self.revision == "release":
            out = _ingress("chat", "llm", "chat.example.com", "ai.example.com")
        else:
            out = _ingress("chat", "llm", "chat.example.com")
        return subprocess.CompletedProcess(cmd, 0, out, "")

    def _api_resources(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        """What `kubectl api-resources` lists: the kinds of the CRDs that the cluster serves."""
        if self.fail is not None and self.fail in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "denied")
        group = next((arg.split("=", 1)[1] for arg in cmd if arg.startswith("--api-group=")), None)
        lines = ["NAME SHORTNAMES APIVERSION NAMESPACED KIND"]
        if group in (None, "argoproj.io") and "argoproj.io" not in self.missing_crds:
            lines.append("workflowtemplates wft,wftmpl argoproj.io/v1alpha1 true WorkflowTemplate")
        if (
            group in (None, "monitoring.coreos.com")
            and "monitoring.coreos.com" not in self.missing_crds
        ):
            lines.append("servicemonitors monitoring.coreos.com/v1 true ServiceMonitor")
        return subprocess.CompletedProcess(cmd, 0, "\n".join(lines) + "\n", "")

    def writes(self) -> list[list[str]]:
        return [
            cmd
            for cmd, _ in self.calls
            if cmd[0] == "kubectl" and cmd[1] in ("apply", "patch", "delete")
        ]

    def stdin_of(self, cmd: list[str]) -> str:
        return next(given or "" for called, given in self.calls if called == cmd)


def _configure_service(config_path: Path) -> None:
    """The active config names the repositories the service works for and its GitHub App."""
    from devops_cli.config.settings import reset_settings_cache

    with config_path.open("a", encoding="utf-8") as config:
        config.write(
            "service:\n  repos:\n    - owner/repo\n"
            "  github_app:\n    app_id: 1001\n    installation_id: 42\n    slug: devops-roadmap\n"
        )
    reset_settings_cache()


def _deploy(cluster: _Cluster, *args: str, push: bool = False) -> Any:
    flag = "--push-secrets" if push else "--no-push-secrets"
    return runner.invoke(app, ["deploy-stack", flag, *_CONTEXT, *args])


def _hosts(application: str, *pinned: tuple[str, str, str, list[str]]) -> list[str]:
    """`kubectl patch` of `application` setting each (kind, name, namespace, hosts) under _DOMAIN."""
    patches = [
        {
            "target": {
                "group": "networking.k8s.io",
                "version": "v1",
                "kind": kind,
                "name": name,
                "namespace": ns,
            },
            "patch": json.dumps(
                [
                    op
                    for i, host in enumerate(hosts)
                    for op in (
                        {"op": "test", "path": f"/spec/rules/{i}/host", "value": host},
                        {
                            "op": "replace",
                            "path": f"/spec/rules/{i}/host",
                            "value": host.replace("example.com", _DOMAIN),
                        },
                    )
                ]
            ),
        }
        for kind, name, ns, hosts in pinned
    ]
    body = json.dumps({"spec": {"source": {"kustomize": {"patches": patches}}}})
    return [
        "kubectl",
        "patch",
        "application",
        application,
        "-n",
        "argocd",
        "--type",
        "merge",
        "-p",
        body,
        *_CONTEXT,
    ]


_APPLY_STDIN = ["kubectl", "apply", "-f", "-", *_CONTEXT]
_DEVOPS_HOSTS = _hosts("devops", ("Ingress", "roadmap-service", "devops", ["hooks.example.com"]))
_INGRESS_HOSTS = _hosts("ingress", ("Ingress", "chat", "llm", ["chat.example.com"]))


def test_deploy_stack_on_argo_cd_applies_the_config_map_and_sets_hosts_from_each_applications_revision(
    isolate_devops_cli_config: Path, make_cluster: ClusterFactory
) -> None:
    """The hosts come from what the Applications render at their revision, not the checkout."""
    _configure_service(isolate_devops_cli_config)
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "devops", "--domain", _DOMAIN)
    config_map = yaml.safe_load(cluster.stdin_of(_APPLY_STDIN))
    service = yaml.safe_load(config_map["data"]["devops-cli.yaml"])["service"]
    assert (
        res.exit_code,
        cluster.writes(),
        config_map["metadata"]["name"],
        (service["repos"], service["github_app"]["slug"]),
    ) == (
        0,
        [_APPLY_STDIN, _DEVOPS_HOSTS, _INGRESS_HOSTS],
        "devops-cli-config",
        (["owner/repo"], "devops-roadmap"),
    )


def test_deploy_stack_leaves_the_service_digest_image_updater_set_on_application_devops(
    isolate_devops_cli_config: Path, make_cluster: ClusterFactory
) -> None:
    """The host patch replaces `kustomize.patches` alone, so `kustomize.images` stays (#1485).

    Image Updater writes the digest of the Service image to `spec.source.kustomize.images` of the
    live Application devops. deploy-stack sends a JSON merge patch (`--type merge`, RFC 7386). A
    merge patch merges each object into the object at its place and changes only the members it
    names, so a patch whose path to `patches` names no other member keeps the digest (#5132).
    """
    _configure_service(isolate_devops_cli_config)
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "devops", "--domain", _DOMAIN)
    sent = next(cmd for cmd in cluster.writes() if cmd[1:4] == ["patch", "application", "devops"])
    patch = json.loads(sent[sent.index("-p") + 1])
    assert (
        res.exit_code,
        sent[sent.index("--type") + 1],
        list(patch),
        list(patch["spec"]),
        list(patch["spec"]["source"]),
        list(patch["spec"]["source"]["kustomize"]),
    ) == (0, "merge", ["spec"], ["source"], ["kustomize"], ["patches"])


def test_deploy_stack_stages_the_hosts_of_a_revision_before_it_merges(
    make_cluster: ClusterFactory,
) -> None:
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "infra", "--domain", _DOMAIN, "--argocd-revision", "release")
    staged = _hosts("ingress", ("Ingress", "chat", "llm", ["chat.example.com", "ai.example.com"]))
    assert (res.exit_code, cluster.writes()) == (0, [staged])


def test_deploy_stack_refuses_a_revision_with_no_placeholder_host_rather_than_clear_staged_hosts(
    make_cluster: ClusterFactory,
) -> None:
    """A revision whose hosts are already real (an older overlay) would leave an empty patch list."""
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "infra", "--domain", _DOMAIN, "--argocd-revision", "pinned")
    assert (
        res.exit_code,
        cluster.writes(),
        "renders no host under the placeholder" in res.output,
    ) == (
        1,
        [],
        True,
    )


def test_deploy_stack_infra_on_argo_cd_sets_only_the_ingress_hosts(
    make_cluster: ClusterFactory,
) -> None:
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "infra", "--domain", _DOMAIN)
    assert (res.exit_code, cluster.writes()) == (0, [_INGRESS_HOSTS])


def test_deploy_stack_llm_on_argo_cd_changes_nothing_itself(make_cluster: ClusterFactory) -> None:
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "llm")
    assert (res.exit_code, cluster.writes(), "Argo CD manages the cluster" in res.output) == (
        0,
        [],
        True,
    )


def test_native_deploy_stack_llm_applies_the_gateway_kustomization_after_the_secret_push(
    make_cluster: ClusterFactory, keyring_store: FakeKeyring
) -> None:
    """Without Argo CD, deploy-stack applies the gateway with `kubectl apply -k k8s/llm/gateway`
    after it pushes the Secrets, so the gateway reads its master key at start. The ConfigMap that
    the kustomization generates from `config.yaml` and the Deployment that names it go in one
    apply, so a changed config rolls the gateway (#1929). The ServiceMonitor follows the charts."""
    gateway = str(Path("k8s", "llm", "gateway"))
    cluster = make_cluster(argo=False)
    stock_push_keyring(keyring_store)
    keyring_store.values["service_github_app_private_key"] = "app-private-key-value-0001"
    res = _deploy(cluster, "--stack", "llm", "--k8s-dir", "k8s", push=True)
    steps = [
        ("<push>",) if cmd[:3] == _SERVER_SIDE_APPLY else tuple(cmd[1:4])
        for cmd, _ in cluster.calls
        if cmd[:3] == _SERVER_SIDE_APPLY or (cmd[1:2] == ["apply"] and cmd[3].startswith(gateway))
    ]
    assert (res.exit_code, steps) == (
        0,
        [
            ("<push>",),
            ("apply", "-k", gateway),
            ("apply", "-f", str(Path(gateway, "servicemonitor.yaml"))),
        ],
    )


def test_native_teardown_stack_llm_deletes_the_gateway_kustomization(
    make_cluster: ClusterFactory,
) -> None:
    """Without Argo CD, teardown-stack deletes the gateway with `kubectl delete -k`, as
    deploy-stack applies it, so the generated ConfigMap goes with the Deployment (#1929)."""
    gateway = str(Path("k8s", "llm", "gateway"))
    cluster = make_cluster(argo=False)
    res = runner.invoke(app, ["teardown-stack", "--stack", "llm", "--k8s-dir", "k8s", *_CONTEXT])
    deletes = [
        tuple(cmd[1:4])
        for cmd in cluster.writes()
        if cmd[1] == "delete" and len(cmd) > 3 and cmd[3].startswith(gateway)
    ]
    assert (res.exit_code, deletes) == (
        0,
        [
            ("delete", "-f", str(Path(gateway, "servicemonitor.yaml"))),
            ("delete", "-k", gateway),
        ],
    )


def test_teardown_stack_skips_post_helm_delete_when_crd_not_installed(
    make_cluster: ClusterFactory,
) -> None:
    """When a post-Helm custom resource kind is not served, teardown-stack skips deleting it
    and warns (#1818)."""
    cluster = make_cluster(argo=False, missing_crds=("argoproj.io",))
    res = runner.invoke(app, ["teardown-stack", "--stack", "infra", "--k8s-dir", "k8s", *_CONTEXT])
    assert res.exit_code == 0
    assert (
        "Skipped workflowtemplate-version.yaml: the cluster does not serve kind "
        "'WorkflowTemplate' (argoproj.io/v1alpha1)." in res.output
    )
    deleted_post_helm = [
        cmd
        for cmd in cluster.writes()
        if cmd[1] == "delete" and "workflowtemplate-version.yaml" in " ".join(cmd)
    ]
    assert deleted_post_helm == []


def test_deploy_stack_reports_post_helm_apply_failure_when_crd_not_installed(
    make_cluster: ClusterFactory, keyring_store: FakeKeyring
) -> None:
    """When a post-Helm custom resource kind is not served, deploy-stack warns and skips applying it (#1818)."""
    cluster = make_cluster(argo=False, missing_crds=("argoproj.io",))
    res = runner.invoke(
        app,
        [
            "deploy-stack",
            "--stack",
            "infra",
            "--k8s-dir",
            "k8s",
            "--no-push-secrets",
            *_CONTEXT,
        ],
    )
    assert res.exit_code == 0
    assert (
        "Failed to apply workflowtemplate-version.yaml: the cluster does not serve kind "
        "'WorkflowTemplate' (argoproj.io/v1alpha1)." in res.output
    )
    applied_post_helm = [
        cmd
        for cmd in cluster.writes()
        if cmd[1] == "apply" and "workflowtemplate-version.yaml" in " ".join(cmd)
    ]
    assert applied_post_helm == []


def test_deploy_stack_on_argo_cd_pushes_secrets_after_deriving_the_hosts_and_before_writing(
    isolate_devops_cli_config: Path, make_cluster: ClusterFactory, keyring_store: FakeKeyring
) -> None:
    _configure_service(isolate_devops_cli_config)
    cluster = make_cluster()
    stock_push_keyring(keyring_store)
    keyring_store.values["service_github_app_private_key"] = "app-private-key-value-0001"
    res = _deploy(cluster, "--stack", "devops", "--domain", _DOMAIN, push=True)
    steps = [
        "<push>" if cmd[:3] == _SERVER_SIDE_APPLY else cmd[0] if cmd[0] == "git" else cmd[1]
        for cmd, _ in cluster.calls
        if cmd[:3] == _SERVER_SIDE_APPLY or cmd[0] == "git" or cmd[1] in ("apply", "patch")
    ]
    assert (
        res.exit_code,
        keyring_store.secret_reads() != set(),
        steps[steps.index("<push>") :],
    ) == (
        0,
        True,
        ["<push>", "apply", "patch", "patch"],
    )


def test_deploy_stack_fails_when_argo_cd_refuses_the_hosts(
    isolate_devops_cli_config: Path, make_cluster: ClusterFactory
) -> None:
    _configure_service(isolate_devops_cli_config)
    cluster = make_cluster(fail="ingress")
    res = _deploy(cluster, "--stack", "devops", "--domain", _DOMAIN)
    assert (res.exit_code, "Application 'ingress'" in res.output, "denied" in res.output) == (
        1,
        True,
        True,
    )


def test_deploy_stack_fails_when_the_cluster_refuses_the_config_map(
    isolate_devops_cli_config: Path, make_cluster: ClusterFactory
) -> None:
    _configure_service(isolate_devops_cli_config)
    cluster = make_cluster(fail="apply")
    res = _deploy(cluster, "--stack", "devops", "--domain", _DOMAIN)
    assert (
        res.exit_code,
        cluster.writes(),
        "Failed to apply ConfigMap devops-cli-config" in res.output,
    ) == (1, [_APPLY_STDIN], True)


def test_deploy_stack_writes_nothing_when_an_application_does_not_build_at_its_revision(
    isolate_devops_cli_config: Path, make_cluster: ClusterFactory
) -> None:
    _configure_service(isolate_devops_cli_config)
    cluster = make_cluster(paths={"ingress": "k8s/overlays/homelab/missing"})
    res = _deploy(cluster, "--stack", "devops", "--domain", _DOMAIN)
    assert (res.exit_code, cluster.writes(), "kubectl kustomize" in res.output) == (1, [], True)


def test_deploy_stack_without_a_domain_writes_nothing_and_names_the_setting(
    isolate_devops_cli_config: Path, make_cluster: ClusterFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("DEVOPS_CLI_K8S_DOMAIN", "DEVOPS_CLI_DOMAIN", "DEVOPS_CLI_CLOUDFLARE_DOMAIN"):
        monkeypatch.delenv(name, raising=False)
    _configure_service(isolate_devops_cli_config)
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "devops")
    assert (res.exit_code, cluster.writes(), "k8s.domain" in res.output) == (1, [], True)


def test_deploy_stack_without_service_repositories_writes_nothing_and_names_the_setting(
    make_cluster: ClusterFactory,
) -> None:
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "devops", "--domain", _DOMAIN)
    assert (res.exit_code, cluster.calls, "service.repos" in res.output) == (1, [], True)


def test_deploy_stack_on_a_native_cluster_applies_the_rendered_config_map_and_no_file_of_it(
    isolate_devops_cli_config: Path, make_cluster: ClusterFactory
) -> None:
    _configure_service(isolate_devops_cli_config)
    cluster = make_cluster(argo=False)
    res = _deploy(cluster, "--stack", "devops", "--domain", _DOMAIN)
    applied = cluster.writes()
    config_map = yaml.safe_load(cluster.stdin_of(_APPLY_STDIN))
    # The only ConfigMap file that the stack applies is the settings of SearXNG (#3924). The
    # ConfigMap `devops-cli-config` has no file: it is rendered and sent on stdin.
    assert (
        res.exit_code,
        applied[:2],
        config_map["metadata"]["name"],
        [cmd for cmd in applied if any("configmap" in part for part in cmd)],
    ) == (
        0,
        [["kubectl", "apply", "-k", "k8s", *_CONTEXT], _APPLY_STDIN],
        "devops-cli-config",
        [["kubectl", "apply", "-f", "k8s/devops/searxng/configmap.yaml", *_CONTEXT]],
    )


def test_teardown_stack_devops_deletes_the_config_map_deploy_stack_rendered(
    make_cluster: ClusterFactory,
) -> None:
    cluster = make_cluster(argo=False)
    res = runner.invoke(app, ["teardown-stack", "--stack", "devops", *_CONTEXT])
    delete = [
        "kubectl",
        "delete",
        "configmap",
        "devops-cli-config",
        "-n",
        "devops",
        "--ignore-not-found",
    ]
    assert (res.exit_code, [*delete, *_CONTEXT] in cluster.writes()) == (0, True)


def test_deploy_stack_dry_run_reports_the_config_map_and_host_overrides_and_runs_nothing(
    isolate_devops_cli_config: Path, make_cluster: ClusterFactory
) -> None:
    _configure_service(isolate_devops_cli_config)
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "devops", "--domain", _DOMAIN, "--dry-run")
    assert (
        res.exit_code,
        cluster.calls,
        "devops/devops-cli-config" in res.output,
        "argocd/devops" in res.output,
        "argocd/ingress" in res.output,
    ) == (0, [], True, True, True)


def test_deploy_stack_dry_run_says_an_argo_cd_cluster_needs_a_domain_and_runs_nothing(
    make_cluster: ClusterFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("DEVOPS_CLI_K8S_DOMAIN", "DEVOPS_CLI_DOMAIN", "DEVOPS_CLI_CLOUDFLARE_DOMAIN"):
        monkeypatch.delenv(name, raising=False)
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "infra", "--dry-run")
    assert (res.exit_code, cluster.calls, "no usable domain" in res.output) == (0, [], True)


def test_deploy_stack_dry_run_refuses_like_the_deploy_without_service_repositories(
    make_cluster: ClusterFactory,
) -> None:
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "devops", "--dry-run")
    assert (res.exit_code, cluster.calls, "service.repos" in res.output) == (1, [], True)


def test_k8s_teardown_stack_when_argo_cd_managed(
    cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """When Argo CD Application 'cluster' exists, teardown-stack exits 1."""
    argo_cd_manages_the_cluster(cluster)

    res = runner.invoke(app, ["teardown-stack", "--stack", "infra"])

    assert (
        res.exit_code,
        "Argo CD manages the cluster" in res.output,
        "Refusing teardown" in res.output,
        calls_starting(process_fake, "helm"),
    ) == (1, True, True, [])


def test_k8s_teardown_stack_refuses_on_argo_check_error(
    cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """When Argo CD Application check raises an API error (403, 500, timeout), teardown-stack refuses."""
    cluster.custom_objects.fail(
        "get_namespaced_custom_object",
        api_exception(403, "403 Forbidden: user cannot get applications.argoproj.io"),
    )

    res = runner.invoke(app, ["teardown-stack", "--stack", "infra"])

    assert res.exit_code == 1
    assert "403 Forbidden" in res.output
    assert "Refusing teardown" in res.output
    assert calls_starting(process_fake, "helm") == []


def test_k8s_teardown_stack_when_argo_not_managed_allows_teardown(
    cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """When Argo CD Application returns 404, teardown-stack proceeds."""
    res = runner.invoke(app, ["teardown-stack", "--stack", "infra"])

    assert res.exit_code == 0
    assert "Refusing teardown" not in res.output
    assert calls_starting(process_fake, "helm", "uninstall") != []


def test_k8s_deploy_and_teardown_dry_run_makes_no_cluster_calls(
    cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """deploy-stack and teardown-stack under --dry-run invoke no kubectl or helm commands."""
    res_deploy = runner.invoke(app, ["deploy-stack", "--stack", "infra", "--dry-run"])
    res_teardown = runner.invoke(app, ["teardown-stack", "--stack", "infra", "--dry-run"])

    assert (
        res_deploy.exit_code,
        res_teardown.exit_code,
        process_fake.calls,
        cluster.core.calls,
        cluster.custom_objects.calls,
        cluster.version.calls,
    ) == (0, 0, [], [], [], [])


def test_k8s_helm_upgrade_command_includes_pinned_version(
    cluster: FakeCluster, process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """Helm upgrade commands built by deploy-stack include --version pinned flag."""
    answer_helm_version(process_fake)

    res = runner.invoke(app, ["deploy-stack", "--stack", "infra", "--no-push-secrets"])

    helm_cmds = [list(argv) for argv in calls_starting(process_fake, "helm", "upgrade")]
    assert res.exit_code == 0
    assert len(helm_cmds) > 0
    for cmd in helm_cmds:
        assert "--version" in cmd
        assert "--take-ownership" in cmd


def test_native_deploy_stack_infra_applies_the_monitoring_kustomization(
    cluster: FakeCluster, process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """Without Argo CD, deploy-stack applies `monitoring` right after the root kustomization.

    The root leaves the `monitoring` kustomization to Argo CD's `monitoring` Application (#1279),
    so nothing else creates the namespace's perimeter (#913) or the Grafana dashboard ConfigMaps
    (#1297) on a natively deployed cluster.
    """
    answer_helm_version(process_fake)

    res = runner.invoke(
        app, ["deploy-stack", "--stack", "infra", "--no-push-secrets", "--k8s-dir", "k8s"]
    )

    kustomize_targets = [
        Path(argv[3]) for argv in calls_starting(process_fake, "kubectl", "apply", "-k")
    ]
    assert (res.exit_code, kustomize_targets) == (
        0,
        [
            Path("k8s"),
            Path("k8s", "monitoring"),
            Path("k8s", "gpu-feature-discovery"),
        ],
    )


@pytest.mark.parametrize(
    ("stack", "kustomizations"),
    [
        (
            "infra",
            [str(Path("k8s", "monitoring")), str(Path("k8s", "gpu-feature-discovery"))],
        ),
        (
            "all",
            [str(Path("k8s", "monitoring")), str(Path("k8s", "gpu-feature-discovery"))],
        ),
        ("llm", []),
    ],
)
def test_deploy_stack_dry_run_lists_the_kustomizations_its_stacks_apply(
    stack: str, kustomizations: list[str], isolate_devops_cli_config: Path
) -> None:
    """The dry run names each kustomization the stacks apply after the root one (#1297)."""
    _configure_service(isolate_devops_cli_config)
    res = runner.invoke(app, ["deploy-stack", "--stack", stack, "--k8s-dir", "k8s", "--dry-run"])
    assert (res.exit_code, _dry_run_details(res.output).get("kustomizations")) == (
        0,
        kustomizations,
    )


@pytest.mark.parametrize(
    ("stack", "removal"),
    [
        ("all", ("kubectl", "delete", "-k", "k8s", "--ignore-not-found")),
        ("infra", ("kubectl", "delete", "namespace", "monitoring", "--ignore-not-found")),
    ],
)
def test_teardown_stack_removes_the_monitoring_perimeter_with_its_namespace(
    stack: str, removal: tuple[str, ...], cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """teardown-stack removes `monitoring-default-perimeter` with namespace `monitoring` (#913).

    `--stack all` deletes the root kustomization's objects, namespace `monitoring` among them, and
    `--stack infra` deletes that namespace; either takes the namespace's NetworkPolicy with it.
    """
    name_contexts(cluster, "minikube")

    res = runner.invoke(app, ["teardown-stack", "--stack", stack, "--k8s-dir", "k8s", *_CONTEXT])

    commands = [call.argv for call in process_fake.calls]
    assert (res.exit_code, (*removal, *_CONTEXT) in commands) == (0, True)


_ARGO_WORKFLOWS_POLICY = str(Path("k8s", "argo-workflows", "networkpolicy.yaml"))
_ARGO_WORKFLOWS_TEMPLATE = str(Path("k8s", "argo-workflows", "workflowtemplate-version.yaml"))


def test_infra_dry_runs_list_the_argo_workflows_release_perimeter_and_template() -> None:
    """Both dry runs name the chart, the perimeter and the WorkflowTemplate. A dry run makes no
    request, which the hermetic floor enforces (#1535)."""
    deploy = runner.invoke(
        app, ["deploy-stack", "--stack", "infra", "--k8s-dir", "k8s", "--dry-run"]
    )
    teardown = runner.invoke(
        app, ["teardown-stack", "--stack", "infra", "--k8s-dir", "k8s", "--dry-run"]
    )
    deployed, torn_down = _dry_run_details(deploy.output), _dry_run_details(teardown.output)
    assert (
        deploy.exit_code,
        "argo-workflows" in deployed["helm_releases"],
        _ARGO_WORKFLOWS_POLICY in deployed["manifests"],
        deployed["post_helm"],
        teardown.exit_code,
        "argo-workflows" in torn_down["helm_uninstalls"],
        _ARGO_WORKFLOWS_POLICY in torn_down["manifest_deletes"],
        torn_down["post_helm_deletes"],
    ) == (
        0,
        True,
        True,
        [_ARGO_WORKFLOWS_TEMPLATE],
        0,
        True,
        True,
        [_ARGO_WORKFLOWS_TEMPLATE],
    )


def test_infra_stack_applies_the_perimeter_before_and_the_template_after_every_chart(
    make_cluster: ClusterFactory, keyring_store: FakeKeyring
) -> None:
    """The WorkflowTemplate needs the CRD its chart installs, so it applies after every Helm
    release; the perimeter applies before them. The stack restarts no service: the `devops` stack
    owns the restart of `roadmap-service` (#1535)."""
    cluster = make_cluster(argo=False)
    res = _deploy(cluster, "--stack", "infra", "--k8s-dir", "k8s")
    commands = [cmd for cmd, _ in cluster.calls]
    upgrades = [i for i, cmd in enumerate(commands) if cmd[:3] == ["helm", "upgrade", "--install"]]
    policy = commands.index(["kubectl", "apply", "-f", _ARGO_WORKFLOWS_POLICY, *_CONTEXT])
    template = commands.index(["kubectl", "apply", "-f", _ARGO_WORKFLOWS_TEMPLATE, *_CONTEXT])
    assert (
        res.exit_code,
        policy < min(upgrades),
        template > max(upgrades),
        [cmd for cmd in commands if "restart" in cmd or any("roadmap-service" in a for a in cmd)],
    ) == (0, True, True, [])


def test_infra_teardown_deletes_the_template_before_the_uninstalls_and_the_namespace_after(
    make_cluster: ClusterFactory,
) -> None:
    """The template is deleted while the chart's CRD still serves it, and the namespace goes after
    the releases that live in it (#1535)."""
    cluster = make_cluster(argo=False)
    res = runner.invoke(app, ["teardown-stack", "--stack", "infra", "--k8s-dir", "k8s", *_CONTEXT])
    commands = [cmd for cmd, _ in cluster.calls]
    uninstalls = [i for i, cmd in enumerate(commands) if cmd[:2] == ["helm", "uninstall"]]
    template = commands.index(
        ["kubectl", "delete", "-f", _ARGO_WORKFLOWS_TEMPLATE, "--ignore-not-found", *_CONTEXT]
    )
    namespace = commands.index(
        ["kubectl", "delete", "namespace", "argo-workflows", "--ignore-not-found", *_CONTEXT]
    )
    assert (res.exit_code, template < min(uninstalls), namespace > max(uninstalls)) == (
        0,
        True,
        True,
    )


def test_llm_stack_applies_gateway_servicemonitor_after_helm_and_deletes_before_uninstall(
    cluster: FakeCluster, process_fake: ProcessFake, keyring_store: FakeKeyring
) -> None:
    """deploy-stack --stack llm applies k8s/llm/gateway/servicemonitor.yaml after Helm releases,
    teardown-stack deletes it before Helm uninstalls, and both dry runs list it (#1367)."""
    monitor = str(Path("k8s", "llm", "gateway", "servicemonitor.yaml"))
    database = str(Path("k8s", "llm", "gateway-db.yaml"))
    name_contexts(cluster, "minikube")
    deploy_dry = runner.invoke(
        app, ["deploy-stack", "--stack", "llm", "--k8s-dir", "k8s", "--dry-run"]
    )
    teardown_dry = runner.invoke(
        app, ["teardown-stack", "--stack", "llm", "--k8s-dir", "k8s", "--dry-run"]
    )
    assert (
        deploy_dry.exit_code,
        teardown_dry.exit_code,
        _dry_run_details(deploy_dry.output).get("post_helm"),
        _dry_run_details(teardown_dry.output).get("post_helm_deletes"),
        process_fake.calls,
        cluster.core.calls,
        cluster.custom_objects.calls,
    ) == (0, 0, [database, monitor], [monitor, database], [], [], [])

    answer_helm_version(process_fake)
    process_fake.answer(
        "kubectl api-resources",
        ProcessAnswer(stdout="servicemonitors monitoring.coreos.com/v1 true ServiceMonitor\n"),
    )
    res_deploy = runner.invoke(
        app,
        ["deploy-stack", "--stack", "llm", "--no-push-secrets", "--k8s-dir", "k8s", *_CONTEXT],
    )
    deploy_cmds = [list(call.argv) for call in process_fake.calls]
    helm_upgrade_indices = [
        idx for idx, cmd in enumerate(deploy_cmds) if cmd[:3] == ["helm", "upgrade", "--install"]
    ]
    monitor_apply_idx = deploy_cmds.index(["kubectl", "apply", "-f", monitor, *_CONTEXT])

    process_fake.calls.clear()
    res_teardown = runner.invoke(
        app, ["teardown-stack", "--stack", "llm", "--k8s-dir", "k8s", *_CONTEXT]
    )
    teardown_cmds = [list(call.argv) for call in process_fake.calls]
    helm_uninstall_indices = [
        idx for idx, cmd in enumerate(teardown_cmds) if cmd[:2] == ["helm", "uninstall"]
    ]
    monitor_delete_idx = teardown_cmds.index(
        ["kubectl", "delete", "-f", monitor, "--ignore-not-found", *_CONTEXT]
    )

    assert (
        res_deploy.exit_code,
        bool(helm_upgrade_indices) and monitor_apply_idx > max(helm_upgrade_indices),
        res_teardown.exit_code,
        bool(helm_uninstall_indices) and monitor_delete_idx < min(helm_uninstall_indices),
    ) == (0, True, 0, True)

    from devops_cli.commands.k8s.stack_lifecycle import (
        _apply_post_helm_paths,
        _delete_post_helm_paths,
    )

    process_fake.calls.clear()
    _apply_post_helm_paths([Path("k8s", "mattermost")], list(_CONTEXT))
    _delete_post_helm_paths([Path("k8s", "mattermost")], list(_CONTEXT))
    assert [list(call.argv) for call in process_fake.calls] == [
        ["kubectl", "apply", "-k", str(Path("k8s", "mattermost")), *_CONTEXT],
        [
            "kubectl",
            "delete",
            "-k",
            str(Path("k8s", "mattermost")),
            "--ignore-not-found",
            *_CONTEXT,
        ],
    ]


def test_k8s_pods_table_builder(cluster: FakeCluster) -> None:
    import datetime

    from devops_cli.commands.k8s.diagnostics import _build_pods_table
    from devops_cli.output import format_timestamp_age

    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    assert format_timestamp_age(now_iso) != "—"
    assert format_timestamp_age("invalid-timestamp") == "—"

    cluster.core.answers["list_namespaced_pod"] = [healthy_pod("web-123")]
    cluster.core.answers["list_pod_for_all_namespaces"] = [healthy_pod("web-123")]

    table = _build_pods_table("default", label_selector=None, all_namespaces=False)
    assert table.row_count == 1

    table_all = _build_pods_table(None, label_selector="app=web", all_namespaces=True)
    assert table_all.row_count == 1


def test_build_pods_table_masks_credentials_in_exceptions(cluster: FakeCluster) -> None:
    from devops_cli.commands.k8s.diagnostics import _build_pods_table

    cluster.core.fail("list_namespaced_pod", RuntimeError("Token secret_token_xyz123 failed"))

    table = _build_pods_table("default", None, False)

    rendered = str(table.rows)
    assert "secret_token_xyz123" not in rendered


def test_k8s_pods_colours_a_status_by_health_not_by_phase(cluster: FakeCluster) -> None:
    """A crashlooping pod in phase Running was printed green."""
    from devops_cli.commands.k8s.diagnostics import _build_pods_table
    from tests.support.fakes.kubernetes import crashlooping_pod, healthy_pod

    cluster.core.answers["list_pod_for_all_namespaces"] = [
        healthy_pod("api-0"),
        crashlooping_pod("exporter-0"),
    ]

    table = _build_pods_table(None, None, all_namespaces=True)

    assert [row[2] for row in table.rows] == [
        "[green]Running[/green]",
        "[red]CrashLoopBackOff[/red]",
    ]


def test_watching_pods_prints_the_reason_a_container_gives(cluster: FakeCluster) -> None:
    """`devops k8s pods --watch` printed the phase, Running, for a crashlooping pod."""
    from kubernetes import client as k8s_client

    from devops_cli.commands.k8s import app as k8s_app
    from tests.support.fakes.kubernetes import crashlooping_pod

    wire_pod = k8s_client.ApiClient().sanitize_for_serialization(crashlooping_pod("exporter-0"))
    cluster.core.watch_events = [{"type": "MODIFIED", "object": wire_pod}]

    result = runner.invoke(k8s_app, ["pods", "--watch", "-A"])

    assert (result.exit_code, "default/exporter-0 (CrashLoopBackOff)" in result.output) == (0, True)
