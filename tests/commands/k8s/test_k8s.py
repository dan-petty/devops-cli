"""Unit tests for Kubernetes CLI commands (devops_cli.commands.k8s)."""

from __future__ import annotations

import json
import re
import subprocess
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.config import constants
from devops_cli.config.constants import (
    CONST_CANONICAL_OCI_SOURCE,
    CONST_GIT_NONINTERACTIVE_SSH_CONFIG,
)
from devops_cli.dry_run import set_dry_run
from tests.support.config_writes import written_keys
from tests.support.credential_keys import credential_key_paths
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
    write_path_applications,
)
from tests.support.tcp_probe import TcpProbe
from tests.support.waits import POLL_INTERVAL_SECONDS

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


def test_k8s_deploy_stack_dry_run(process_fake: ProcessFake) -> None:
    """k8s deploy-stack with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack"])
        assert result.exit_code == 0
        assert "devops k8s deploy-stack" in result.output
    finally:
        set_dry_run(False)


def test_k8s_teardown_stack_dry_run(process_fake: ProcessFake) -> None:
    """k8s teardown-stack with dry-run active must print dry-run Pydantic model notice, and the
    devops stack names both ConfigMaps that deploy-stack rendered (#4147)."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["teardown-stack"])
        devops = runner.invoke(app, ["teardown-stack", "--stack", "devops"])
    finally:
        set_dry_run(False)
    details = _dry_run_details(devops.output)
    assert (
        result.exit_code,
        "devops k8s teardown-stack" in result.output,
        details["config_map_delete"],
        details["sandbox_config_map_delete"],
    ) == (
        0,
        True,
        "devops/devops-cli-config",
        "devops/devops-cli-config-sandbox",
    )


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
    process_fake.answer(
        ["kubectl", "version", "--client", "-o", "json"],
        ProcessAnswer(stdout='{"clientVersion":{"gitVersion":"v1.37.1"}}'),
    )

    res = runner.invoke(
        app, ["deploy-stack", "--context", "local-k3s", "--no-push-secrets", "--no-wait"]
    )

    assert "kubectl version 1.37.1 is outside the supported skew" in " ".join(res.output.split())
    assert "v1.31.4+k3s1" in res.output


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


def test_deploy_stack_dry_run_lists_the_secrets_and_key_names_and_runs_nothing(
    process_fake: ProcessFake,
) -> None:
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
            "monitoring/grafana-admin: admin-user, admin-password, secret-key, llm-gateway-key",
            "monitoring/grafana-image-renderer: token",
            "monitoring/alertmanager-mattermost: url",
            "argocd/argocd-notifications-secret: github-appID, github-installationID, github-privateKey, mattermost-deploys-url",
            "object-store/seaweedfs-admin: adminUser, adminPassword",
            "object-store/seaweedfs-s3: s3.json",
            "devops/crawl4ai: CRAWL4AI_API_TOKEN (if namespace devops exists)",
            "devops/searxng: SEARXNG_SECRET (if namespace devops exists)",
            "devops/searxng-metrics-auth: username, password (if namespace devops exists)",
            "devops/mcp-server: DEVOPS_CLI_MCP_TOKEN (if namespace devops exists)",
            "devops/renovate: DEVOPS_CLI_RENOVATE_GITHUB_APP_ID, DEVOPS_CLI_RENOVATE_GITHUB_APP_INSTALLATION_ID, DEVOPS_CLI_RENOVATE_GITHUB_APP_PRIVATE_KEY (if namespace devops exists)",
            "devops/devops-cli: DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY, DEVOPS_CLI_AI_API_KEY, DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS, DEVOPS_CLI_FIRECRAWL_API_KEY, DEVOPS_CLI_VALKEY_PASSWORD, DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN, DEVOPS_CLI_CRAWL4AI_API_TOKEN, DEVOPS_CLI_MCP_STAGE_TOKEN, DEVOPS_CLI_MCP_IMPLEMENT_TOKEN, DEVOPS_CLI_QDRANT_API_KEY (if namespace devops exists)",
            "devops/roadmap-service-llm-key: api-key (if namespace devops exists)",
            "devops/qdrant-api-key: api-key (if namespace devops exists)",
        ],
        [],
    )


def test_deploy_stack_dry_run_makes_no_request(
    isolate_devops_cli_config: Path, process_fake: ProcessFake
) -> None:
    """No connection, no keyring call and no child that reads the cluster, with the Secret push
    on and the context left to the settings. Each child is a local read of the checkout, which
    the process fake answers: git reads its `origin`, and `kubectl kustomize` builds its folders
    (#6681)."""
    _configure_service(isolate_devops_cli_config)
    result = runner.invoke(app, ["deploy-stack", "--stack", "all", "--dry-run"])
    children = {(call.argv[:2], call.local_read) for call in process_fake.calls}
    local_reads = {(("git", "-C"), True), (("kubectl", "kustomize"), True)}
    assert (result.exit_code, result.exception, children <= local_reads) == (0, None, True)


def test_k8s_deploy_stack_all_dry_run(
    isolate_devops_cli_config: Path, process_fake: ProcessFake
) -> None:
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
    from devops_cli.commands.k8s.stack_lifecycle import StackRelease, _build_helm_upgrade_cmd

    rel: StackRelease = {
        "name": "argocd",
        "chart": "argo/argo-cd",
        "namespace": "argocd",
        "values": ["k8s/argocd/values.yaml"],
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


# The `values` source of an Application of a tree outside any repository: the checkout of such a
# tree has no `origin`, so the source of devops-cli stands for it.
_VALUES_SOURCE = {"repoURL": CONST_CANONICAL_OCI_SOURCE, "targetRevision": "main", "ref": "values"}


def _write_chart_application(
    apps: Path, name: str, value_files: list[str], *ref_sources: dict[str, str]
) -> None:
    """Write the Argo CD Application `name` into the folder `apps`: a chart source that pins 1.0.0
    and gives Helm `value_files`, and the sources `ref_sources` that the files name."""
    source: dict[str, Any] = {
        "repoURL": "https://charts.example.com",
        "chart": "c",
        "targetRevision": "1.0.0",
    }
    if value_files:
        source["helm"] = {"valueFiles": value_files}
    application = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": name, "namespace": "argocd"},
        "spec": {"sources": [source, *ref_sources]},
    }
    apps.mkdir(parents=True, exist_ok=True)
    (apps / f"{name}.yaml").write_text(yaml.safe_dump(application), "utf-8")


def _pinned_tree(root: Path, unpinned: str | None = None) -> Path:
    """An environment tree whose Argo CD Applications pin each chart of stack `infra` at 1.0.0,
    except the release `unpinned`: the shape that deploy-stack reads, not the committed tree."""
    from devops_cli.commands.k8s.stack_lifecycle import HELM_RELEASES_BY_STACK

    for release in HELM_RELEASES_BY_STACK["infra"]:
        if release["name"] != unpinned:
            _write_chart_application(root / "argocd" / "apps", release["name"], [])
    write_path_applications(root, "infra")
    return root


def _values_options(upgrade: list[str]) -> list[str]:
    """The value of each `--values` option of the helm command `upgrade`, in their order."""
    return [upgrade[i + 1] for i, arg in enumerate(upgrade) if arg == "--values"]


def test_deploy_stack_gives_the_prometheus_chart_the_values_files_of_its_application(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """The helm command of the prometheus release names the environment values, then the alert
    rules of the product base (#5292), in the order of its Application (#6680), at the version
    that the Application pins (#6060)."""
    env = _pinned_tree(tmp_path / "env")
    _write_chart_application(
        env / "argocd" / "apps",
        "prometheus",
        [
            "$values/env/monitoring/prometheus-values.yaml",
            "$values/env/devops/monitoring/prometheus-rules-values.yaml",
        ],
        _VALUES_SOURCE,
    )

    res = cli("k8s", "deploy-stack", "--stack", "infra", "--k8s-dir", str(env), "--dry-run")
    (upgrade,) = [
        cmd
        for cmd in _dry_run_details(res.output)["helm_commands"]
        if cmd[:3] == ["helm", "upgrade", "--install"] and cmd[4] == "prometheus"
    ]

    assert (res.exit_code, upgrade[upgrade.index("--version") + 1], _values_options(upgrade)) == (
        0,
        "1.0.0",
        [
            str(env / "monitoring" / "prometheus-values.yaml"),
            str(env / "devops" / "monitoring" / "prometheus-rules-values.yaml"),
        ],
    )


def test_deploy_stack_gives_a_chart_the_values_files_of_its_application_in_their_order(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """A values template of another repository comes before the environment values, as Argo CD
    gives them to the chart (#6680). The dry run fetches nothing: it lists the fetch of the
    repository of the template at the revision of its source."""
    env = tmp_path / "env"
    infra = {"repoURL": "https://example.com/infra.git", "targetRevision": "v1.0.0", "ref": "infra"}
    _write_chart_application(
        env / "argocd" / "apps",
        "loki",
        ["$infra/helm/loki/values.yaml", "$values/env/logging/loki-values.yaml"],
        infra,
        _VALUES_SOURCE,
    )
    write_path_applications(env, "logging")

    res = cli("k8s", "deploy-stack", "--stack", "logging", "--k8s-dir", str(env), "--dry-run")
    details = _dry_run_details(res.output)
    (upgrade,) = [cmd for cmd in details["helm_commands"] if cmd[:2] == ["helm", "upgrade"]]
    fetched = Path(details["source_fetches"][0][-1])

    assert (
        res.exit_code,
        _values_options(upgrade),
        details["source_fetches"],
        calls_starting(process_fake, "git", "init"),
    ) == (
        0,
        [str(fetched / "helm" / "loki" / "values.yaml"), str(env / "logging" / "loki-values.yaml")],
        [
            ["git", "init", "--quiet", str(fetched)],
            [
                "git", "-C", str(fetched), "-c", CONST_GIT_NONINTERACTIVE_SSH_CONFIG, "fetch",
                "--quiet", "--depth", "1", "--end-of-options", "https://example.com/infra", "v1.0.0",
            ],
            ["git", "-C", str(fetched), "checkout", "--quiet", "FETCH_HEAD"],
        ],
        [],
    )  # fmt: skip


def test_deploy_stack_stops_on_a_release_that_no_application_pins(
    cli: Callable[..., Any], tmp_path: Path
) -> None:
    env = _pinned_tree(tmp_path / "env", unpinned="prometheus")

    res = cli("k8s", "deploy-stack", "--stack", "infra", "--k8s-dir", str(env), "--dry-run")

    assert (res.exit_code, "Application" in res.output, "prometheus" in res.output) == (
        1,
        True,
        True,
    )


# The NetworkPolicy of the folder `logging` of a tree, and the NetworkPolicy of the Kustomize
# component that the folder takes. A test starts no kustomize (ADR 0007): the process fake gives
# their build.
_LOKI_PERIMETER = (
    "apiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\n"
    "metadata:\n  name: loki-perimeter\n  namespace: logging\nspec:\n  podSelector: {}\n"
)
_DEFAULT_DENY = (
    "apiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\n"
    "metadata:\n  name: default-deny\n  namespace: logging\nspec:\n  podSelector: {}\n"
)
_PERIMETER_BUILD = f"{_LOKI_PERIMETER}---\n{_DEFAULT_DENY}"


def _path_source_tree(root: Path, source: dict[str, str] | None = None) -> Path:
    """An environment tree at `root` with the chart Application `loki` and the Application
    `logging`, whose path source (`source`, else the folder `logging` of the tree) takes the local
    Kustomize component `components/perimeter`: the shape that Argo CD builds, not the committed
    tree. The tree is outside any repository, so the source of devops-cli stands for its origin."""
    apps = root / "argocd" / "apps"
    _write_chart_application(apps, "loki", [])
    path = {"repoURL": CONST_CANONICAL_OCI_SOURCE, "targetRevision": "main"}
    application = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": "logging", "namespace": "argocd"},
        "spec": {"source": source or {**path, "path": f"{root.name}/logging"}},
    }
    (apps / "logging.yaml").write_text(yaml.safe_dump(application), "utf-8")
    component = root / "components" / "perimeter"
    component.mkdir(parents=True)
    (component / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1alpha1\nkind: Component\n"
        "resources:\n  - default-deny.yaml\n",
        "utf-8",
    )
    (component / "default-deny.yaml").write_text(_DEFAULT_DENY, "utf-8")
    (root / "logging").mkdir()
    (root / "logging" / "kustomization.yaml").write_text(
        "resources:\n  - networkpolicy.yaml\ncomponents:\n  - ../components/perimeter\n", "utf-8"
    )
    (root / "logging" / "networkpolicy.yaml").write_text(_LOKI_PERIMETER, "utf-8")
    return root


def test_deploy_stack_dry_run_lists_the_objects_of_the_build_of_each_path_source(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """The dry run builds the path source of Application `logging`, which takes a local
    component, as a local read, and lists the objects of the build in place of a raw manifest
    path (#6681)."""
    env = _path_source_tree(tmp_path / "env")
    process_fake.answer(("kubectl", "kustomize"), ProcessAnswer(stdout=_PERIMETER_BUILD))

    res = cli("k8s", "deploy-stack", "--stack", "logging", "--k8s-dir", str(env), "--dry-run")
    details = _dry_run_details(res.output)
    builds = [call for call in process_fake.calls if call.argv[:2] == ("kubectl", "kustomize")]

    assert (
        res.exit_code,
        details["path_sources"],
        details["kustomize_fetches"],
        details["manifests"],
        [(call.argv, call.local_read) for call in builds],
    ) == (
        0,
        {
            "logging: env/logging": [
                "NetworkPolicy logging/loki-perimeter",
                "NetworkPolicy logging/default-deny",
            ]
        },
        {},
        [],
        [(("kubectl", "kustomize", str((env / "logging").resolve())), True)],
    )


# The answer of the real `kubectl kustomize` (v1.37.2) in a dry run for a folder whose
# `patchesStrategicMerge` names a remote file: Kustomize logs a warning first, and kubectl starts
# its error with `error:`. The error holds the config of the builtin transformer on lines of its
# own, and the cause comes last: Go sends the download to the closed proxy.
_REFUSED_FETCH = (
    "# Warning: 'patchesStrategicMerge' is deprecated. Please use 'patches' instead. Run "
    "'kustomize edit fix' to update your Kustomization automatically.\n"
    "error: trouble configuring builtin PatchStrategicMergeTransformer with config: `\n"
    "paths:\n"
    "- https://192.0.2.1/patches/loki.yaml\n"
    '`: Get "https://192.0.2.1/patches/loki.yaml": proxyconnect tcp: dial tcp 127.0.0.1:9: '
    "connect: connection refused\n"
)
_REFUSED_FETCH_ERROR = (
    "error: trouble configuring builtin PatchStrategicMergeTransformer with config: ` paths: - "
    'https://192.0.2.1/patches/loki.yaml `: Get "https://192.0.2.1/patches/loki.yaml": '
    "proxyconnect tcp: dial tcp 127.0.0.1:9: connect: connection refused"
)


def test_dry_runs_list_a_build_that_fails_and_go_on(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """A dry-run build that fails, such as one that Kustomize cannot fetch, gives no objects: the
    dry runs of deploy-stack and teardown-stack list it in `details.kustomize_fetches` with
    kubectl's error as one line, from its prefix to its cause, and exit 0 (#6681)."""
    env = _path_source_tree(tmp_path / "env")
    process_fake.answer(
        ("kubectl", "kustomize"), ProcessAnswer(returncode=1, stderr=_REFUSED_FETCH)
    )
    stack = ["--stack", "logging", "--k8s-dir", str(env), "--dry-run"]

    deploy = cli("k8s", "deploy-stack", *stack)
    teardown = cli("k8s", "teardown-stack", *stack)
    deployed, removed = _dry_run_details(deploy.output), _dry_run_details(teardown.output)

    assert (
        deploy.exit_code,
        teardown.exit_code,
        deployed["path_sources"],
        deployed["kustomize_fetches"],
        removed["path_source_deletes"],
        removed["kustomize_fetches"],
    ) == (
        0,
        0,
        {"logging: env/logging": None},
        {"logging: env/logging": _REFUSED_FETCH_ERROR},
        {"logging: env/logging": None},
        {"logging: env/logging": _REFUSED_FETCH_ERROR},
    )


def test_only_the_dry_runs_build_a_path_source_with_no_route_to_the_network(
    cli: Callable[..., Any], cluster: FakeCluster, process_fake: ProcessFake, tmp_path: Path
) -> None:
    """The dry runs build each folder with an environment that sends each HTTP and HTTPS request
    of Go to a host that is not a loopback address to a closed local port, and lets git use only
    the `file` transport. The real runs build with the normal environment (#6681)."""
    env = _path_source_tree(tmp_path / "env")
    name_contexts(cluster, "minikube")
    answer_helm_version(process_fake)
    process_fake.answer(("kubectl", "kustomize"), ProcessAnswer(stdout=_PERIMETER_BUILD))
    stack = ["--stack", "logging", "--k8s-dir", str(env)]
    proxy = constants.CONST_K8S_OFFLINE_PROXY_URL
    offline = {
        "HTTP_PROXY": proxy,
        "HTTPS_PROXY": proxy,
        "ALL_PROXY": proxy,
        "http_proxy": proxy,
        "https_proxy": proxy,
        "all_proxy": proxy,
        "NO_PROXY": "",
        "no_proxy": "",
        "GIT_ALLOW_PROTOCOL": "file",
        "GIT_SSH_COMMAND": "false",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
    }

    exit_codes = [
        cli("k8s", "deploy-stack", *stack, "--dry-run").exit_code,
        cli("k8s", "teardown-stack", *stack, "--dry-run").exit_code,
        runner.invoke(app, ["deploy-stack", "--no-push-secrets", *stack, *_CONTEXT]).exit_code,
        runner.invoke(app, ["teardown-stack", *stack, *_CONTEXT]).exit_code,
    ]
    builds = [call for call in process_fake.calls if call.argv[:2] == ("kubectl", "kustomize")]

    assert (exit_codes, [call.env for call in builds]) == (
        [0, 0, 0, 0],
        [offline, offline, None, None],
    )


# A kustomization of the folder `env/logging` for each form of a remote target that Kustomize
# loads: a remote base by an https URL, a `git::` URL, an ssh URL, the SCP form and a path on
# github.com, the `path` of a PatchTransformer inline, in a local file of `transformers` and in
# `patches`, and a file and an env file of a ConfigMapGenerator. Each URL host is the RFC 5737
# address 192.0.2.1, so no real host exists. A path on github.com names its host, and git refuses
# the transport before it resolves the name. An ssh base at the loopback address 127.0.0.1 shows
# that git refuses a remote at a loopback address too.
_CONFIG_MAP = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: loki-extra\n"
_PATCH_TRANSFORMER = (
    "apiVersion: builtin\nkind: PatchTransformer\nmetadata:\n  name: loki-patch\n"
    "path: https://192.0.2.1/patches/loki.yaml\n"
)
_REMOTE_TARGETS: dict[str, dict[str, str]] = {
    "https base": {
        "kustomization.yaml": "resources:\n  - https://192.0.2.1/infra.git//k8s/loki?ref=main\n"
    },
    "git:: base": {
        "kustomization.yaml": (
            "resources:\n  - git::https://192.0.2.1/infra.git//k8s/loki?ref=main\n"
        )
    },
    "ssh base": {
        "kustomization.yaml": (
            "resources:\n  - ssh://git@192.0.2.1/example/infra.git//k8s/loki?ref=main\n"
        )
    },
    "scp base": {
        "kustomization.yaml": "resources:\n  - git@192.0.2.1:example/infra//k8s/loki?ref=main\n"
    },
    "github.com path": {
        "kustomization.yaml": "resources:\n  - github.com/example/infra//k8s/loki?ref=main\n"
    },
    "inline PatchTransformer": {
        "kustomization.yaml": (
            "resources:\n  - configmap.yaml\ntransformers:\n  - |-\n"
            + "".join(f"    {line}\n" for line in _PATCH_TRANSFORMER.splitlines())
        ),
        "configmap.yaml": _CONFIG_MAP,
    },
    "PatchTransformer file": {
        "kustomization.yaml": "resources:\n  - configmap.yaml\ntransformers:\n  - patch.yaml\n",
        "configmap.yaml": _CONFIG_MAP,
        "patch.yaml": _PATCH_TRANSFORMER,
    },
    "patches path": {
        "kustomization.yaml": (
            "resources:\n  - configmap.yaml\npatches:\n"
            "  - path: https://192.0.2.1/patches/loki.yaml\n"
        ),
        "configmap.yaml": _CONFIG_MAP,
    },
    "loopback ssh base": {
        "kustomization.yaml": (
            "resources:\n  - ssh://git@127.0.0.1/example/infra.git//k8s/loki?ref=main\n"
        )
    },
    "ConfigMapGenerator files": {
        "kustomization.yaml": (
            "configMapGenerator:\n  - name: loki-files\n    files:\n"
            "      - https://192.0.2.1/files/loki.conf\n"
        )
    },
    "ConfigMapGenerator envs": {
        "kustomization.yaml": (
            "configMapGenerator:\n  - name: loki-envs\n    envs:\n"
            "      - https://192.0.2.1/files/loki.env?ref=main\n"
        )
    },
}
# The error of Go for a request to the closed proxy, and the error of git for a refused transport.
_NO_ROUTE = re.compile(r"proxyconnect tcp: .*connection refused|transport '\w+' not allowed")


# A dry-run build of a remote target fails at once on the closed proxy (about 0.2 s here). The bound
# leaves room for a loaded CI runner and is still far below the TCP connect timeout of a blackholed
# RFC 5737 address (about 127 s on Linux), so a direct connect still fails the test.
_OFFLINE_BUILD_BOUND_SECONDS = 30


@pytest.mark.live("kubectl")
@pytest.mark.timeout(_OFFLINE_BUILD_BOUND_SECONDS)
@pytest.mark.parametrize("files", _REMOTE_TARGETS.values(), ids=_REMOTE_TARGETS.keys())
def test_the_dry_run_build_of_a_remote_target_fails_at_once_and_is_listed(
    cli: Callable[..., Any], tmp_path: Path, files: dict[str, str]
) -> None:
    """The real `kubectl kustomize` of a folder that names a remote target fails at once in the
    dry run, with the error of the closed proxy or of a refused git transport, and the dry run
    lists the folder in `details.kustomize_fetches` (#6681)."""
    env = _path_source_tree(tmp_path / "env")
    for name, text in files.items():
        (env / "logging" / name).write_text(text, "utf-8")

    res = cli("k8s", "deploy-stack", "--stack", "logging", "--k8s-dir", str(env), "--dry-run")
    details = _dry_run_details(res.output)
    reason = details["kustomize_fetches"].get("logging: env/logging", "")

    assert (res.exit_code, details["path_sources"], _NO_ROUTE.search(reason) is not None) == (
        0,
        {"logging: env/logging": None},
        True,
    ), reason


class _ConfigMapFiles(BaseHTTPRequestHandler):
    """A file server of the host that gives the ConfigMap `loki-extra` at each path."""

    def do_GET(self) -> None:
        body = _CONFIG_MAP.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Write no line for a request."""


@pytest.mark.live("kubectl")
@pytest.mark.timeout(_OFFLINE_BUILD_BOUND_SECONDS)
def test_the_dry_run_build_loads_a_file_of_a_loopback_address(
    cli: Callable[..., Any], tmp_path: Path
) -> None:
    """Go sends a request to a loopback address with no proxy, so the real `kubectl kustomize` of
    the dry run downloads a file of an http URL of a loopback address. The environment of the dry
    run does not block this request (#6681)."""
    server = HTTPServer(("127.0.0.1", 0), _ConfigMapFiles)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": POLL_INTERVAL_SECONDS}, daemon=True
    )
    thread.start()
    env = _path_source_tree(tmp_path / "env")
    (env / "logging" / "kustomization.yaml").write_text(
        f"resources:\n  - http://127.0.0.1:{server.server_port}/loki.yaml\n", "utf-8"
    )
    try:
        res = cli("k8s", "deploy-stack", "--stack", "logging", "--k8s-dir", str(env), "--dry-run")
    finally:
        server.shutdown()
        server.server_close()
    details = _dry_run_details(res.output)

    assert (res.exit_code, details["path_sources"], details["kustomize_fetches"]) == (
        0,
        {"logging: env/logging": ["ConfigMap loki-extra"]},
        {},
    )


def test_deploy_stack_applies_the_build_of_each_path_source_and_teardown_deletes_it(
    cluster: FakeCluster, process_fake: ProcessFake, tmp_path: Path
) -> None:
    """On a cluster without Argo CD, deploy-stack applies the build of the path source before the
    chart, and teardown-stack deletes it before the chart uninstalls (#6681)."""
    env = _path_source_tree(tmp_path / "env")
    name_contexts(cluster, "minikube")
    answer_helm_version(process_fake)
    process_fake.answer(("kubectl", "kustomize"), ProcessAnswer(stdout=_PERIMETER_BUILD))
    stack = ["--stack", "logging", "--k8s-dir", str(env), *_CONTEXT]

    deploy = runner.invoke(app, ["deploy-stack", "--no-push-secrets", *stack])
    deployed = [(list(call.argv), call.stdin) for call in process_fake.calls]
    process_fake.calls.clear()
    teardown = runner.invoke(app, ["teardown-stack", *stack])
    removed = [(list(call.argv), call.stdin) for call in process_fake.calls]
    apply = (["kubectl", "apply", "-f", "-", *_CONTEXT], _PERIMETER_BUILD)
    delete = (["kubectl", "delete", "-f", "-", "--ignore-not-found", *_CONTEXT], _PERIMETER_BUILD)
    upgrade = next(i for i, (cmd, _) in enumerate(deployed) if cmd[:2] == ["helm", "upgrade"])
    uninstall = next(i for i, (cmd, _) in enumerate(removed) if cmd[:2] == ["helm", "uninstall"])

    assert (
        deploy.exit_code,
        teardown.exit_code,
        apply in deployed[:upgrade],
        delete in removed[:uninstall],
    ) == (0, 0, True, True)


def test_deploy_stack_stops_before_the_charts_when_the_cluster_refuses_a_build(
    cluster: FakeCluster, process_fake: ProcessFake, tmp_path: Path
) -> None:
    """A build that kubectl refuses stops the deploy with kubectl's reason, so no chart starts
    without the perimeter of its namespace (#6681)."""
    env = _path_source_tree(tmp_path / "env")
    name_contexts(cluster, "minikube")
    answer_helm_version(process_fake)
    process_fake.answer(("kubectl", "kustomize"), ProcessAnswer(stdout=_PERIMETER_BUILD))
    process_fake.answer(
        ("kubectl", "apply", "-f", "-"), ProcessAnswer(returncode=1, stderr="admission denied")
    )

    res = runner.invoke(
        app,
        ["deploy-stack", "--no-push-secrets", "--stack", "logging", "--k8s-dir", str(env)]
        + _CONTEXT,
    )

    assert (
        res.exit_code,
        "admission denied" in res.output,
        calls_starting(process_fake, "helm", "upgrade"),
    ) == (1, True, [])


def test_deploy_stack_dry_run_fetches_no_path_source_of_another_repository(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """A path source of another repository is fetched only in the real run: the dry run lists the
    fetch, builds nothing and gives no objects (#6681)."""
    infra = {"repoURL": "https://example.com/infra.git", "targetRevision": "v1.0.0"}
    env = _path_source_tree(tmp_path / "env", {**infra, "path": "k8s/logging"})

    res = cli("k8s", "deploy-stack", "--stack", "logging", "--k8s-dir", str(env), "--dry-run")
    details = _dry_run_details(res.output)

    assert (
        res.exit_code,
        details["path_sources"],
        [command[-2:] for command in details["source_fetches"] if "fetch" in command],
        calls_starting(process_fake, "git", "init"),
        calls_starting(process_fake, "kubectl", "kustomize"),
    ) == (
        0,
        {"logging: k8s/logging": None},
        [["https://example.com/infra", "v1.0.0"]],
        [],
        [],
    )


def test_deploy_stack_stops_on_an_application_that_the_tree_does_not_hold(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """A stack whose Application is missing from the tree stops before it touches the cluster, so
    a perimeter never goes away with no message (#6681)."""
    env = _path_source_tree(tmp_path / "env")
    (env / "argocd" / "apps" / "logging.yaml").unlink()

    res = cli("k8s", "deploy-stack", "--stack", "logging", "--k8s-dir", str(env), "--dry-run")

    assert (res.exit_code, "Application logging" in " ".join(res.output.split())) == (1, True)


def test_deploy_stack_stops_on_a_path_source_that_leaves_the_repository(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """A path source whose folder is outside its repository stops the dry runs of deploy-stack and
    teardown-stack before any build, as Argo CD builds no such path, so the dry runs read only the
    checkout (#6681)."""
    source = {"repoURL": CONST_CANONICAL_OCI_SOURCE, "targetRevision": "main"}
    env = _path_source_tree(tmp_path / "repo" / "env", {**source, "path": "../outside"})
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "kustomization.yaml").write_text("resources: []\n", "utf-8")
    stack = ["--stack", "logging", "--k8s-dir", str(env), "--dry-run"]

    results = [cli("k8s", command, *stack) for command in ("deploy-stack", "teardown-stack")]

    assert (
        [(res.exit_code, "../outside" in res.output) for res in results],
        calls_starting(process_fake, "kubectl", "kustomize"),
    ) == ([(1, True), (1, True)], [])


# A namespaced object and an object of the cluster scope, the build of a second path source.
_EXTRA_BUILD = (
    "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: logging\n---\n"
    "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: loki-extra\n  namespace: logging\n"
)


def _two_source_tree(root: Path, process_fake: ProcessFake) -> Path:
    """The tree of `_path_source_tree`, whose Application `logging` has a second path source
    `env/extra`, with the process fake that gives the build of each folder."""
    env = _path_source_tree(root)
    (env / "extra").mkdir()
    (env / "extra" / "kustomization.yaml").write_text("resources: []\n", "utf-8")
    file = env / "argocd" / "apps" / "logging.yaml"
    application = yaml.safe_load(file.read_text("utf-8"))
    first = application["spec"].pop("source")
    application["spec"]["sources"] = [first, {**first, "path": f"{root.name}/extra"}]
    file.write_text(yaml.safe_dump(application), "utf-8")
    process_fake.answer(("kubectl", "kustomize"), ProcessAnswer(stdout=_PERIMETER_BUILD))
    process_fake.answer(
        ("kubectl", "kustomize", str((env / "extra").resolve())),
        ProcessAnswer(stdout=_EXTRA_BUILD),
    )
    return env


def test_teardown_dry_run_lists_the_builds_in_the_order_of_the_deletes(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """The deploy dry run lists the builds in the order of the deploy, and the teardown dry run
    lists them in the reverse order, as the teardown deletes them (#6681)."""
    env = _two_source_tree(tmp_path / "env", process_fake)
    stack = ["--stack", "logging", "--k8s-dir", str(env), "--dry-run"]

    deploy = _dry_run_details(cli("k8s", "deploy-stack", *stack).output)
    teardown = _dry_run_details(cli("k8s", "teardown-stack", *stack).output)
    perimeter = ["NetworkPolicy logging/loki-perimeter", "NetworkPolicy logging/default-deny"]
    extra = ["Namespace logging", "ConfigMap logging/loki-extra"]

    assert (
        list(deploy["path_sources"].items()),
        list(teardown["path_source_deletes"].items()),
    ) == (
        [("logging: env/logging", perimeter), ("logging: env/extra", extra)],
        [("logging: env/extra", extra), ("logging: env/logging", perimeter)],
    )


@pytest.mark.parametrize("failure", ["refused build", "missing Application"])
def test_teardown_stack_stops_before_the_cluster_when_a_build_fails(
    cli: Callable[..., Any],
    cluster: FakeCluster,
    process_fake: ProcessFake,
    tmp_path: Path,
    failure: str,
) -> None:
    """A build that Kustomize refuses, or an Application that the tree does not hold, stops the
    teardown with exit 1 and the reason, before it deletes an object or uninstalls a chart
    (#6681)."""
    env = _path_source_tree(tmp_path / "env")
    name_contexts(cluster, "minikube")
    if failure == "refused build":
        process_fake.answer(
            ("kubectl", "kustomize"), ProcessAnswer(returncode=1, stderr="missing resource")
        )
        reason = "missing resource"
    else:
        (env / "argocd" / "apps" / "logging.yaml").unlink()
        reason = "Application logging"

    res = cli("k8s", "teardown-stack", "--stack", "logging", "--k8s-dir", str(env), *_CONTEXT)

    assert (
        res.exit_code,
        reason in " ".join(res.output.split()),
        calls_starting(process_fake, "kubectl", "delete"),
        calls_starting(process_fake, "helm"),
    ) == (1, True, [], [])


def test_deploy_stack_installs_the_barman_cloud_plugin_after_the_operator_and_cert_manager() -> (
    None
):
    """The plugin chart renders a cert-manager Issuer and Certificates, and the plugin must run in
    the namespace of the CloudNativePG operator. So stack `infra` installs it after both, in
    `cnpg-system`, and no other stack lists the three releases (#4764)."""
    from devops_cli.commands.k8s.stack_lifecycle import HELM_RELEASES_BY_STACK

    releases = {
        stack: [release["name"] for release in stack_releases]
        for stack, stack_releases in HELM_RELEASES_BY_STACK.items()
    }
    namespaces = {
        release["name"]: release["namespace"]
        for stack_releases in HELM_RELEASES_BY_STACK.values()
        for release in stack_releases
    }
    infra = releases["infra"]
    elsewhere = {name for stack, names in releases.items() if stack != "infra" for name in names}

    assert (
        infra.index("cloudnative-pg") < infra.index("plugin-barman-cloud"),
        infra.index("cert-manager") < infra.index("plugin-barman-cloud"),
        namespaces["cert-manager"],
        namespaces["plugin-barman-cloud"] == namespaces["cloudnative-pg"],
        elsewhere & {"cloudnative-pg", "cert-manager", "plugin-barman-cloud"},
    ) == (True, True, "cert-manager", True, set())


def test_deploy_stack_installs_the_object_store_operator_after_cert_manager_and_the_store_last() -> (
    None
):
    """The operator chart issues its webhook certificate with cert-manager, and the Seaweed CR of
    `object-store` needs the CRD of that chart. So stack `infra` installs the release into
    `object-store` after cert-manager, applies the store after the charts, and no other stack
    lists the release (#4750)."""
    from devops_cli.commands.k8s.stack_lifecycle import (
        HELM_RELEASES_BY_STACK,
        HELM_REPOS_BY_STACK,
        POST_HELM_BY_STACK,
    )

    releases = {
        stack: {release["name"]: release for release in stack_releases}
        for stack, stack_releases in HELM_RELEASES_BY_STACK.items()
    }
    infra = list(releases["infra"])
    operator = releases["infra"].get("seaweedfs-operator", {})
    elsewhere = {name for stack, names in releases.items() if stack != "infra" for name in names}

    assert (
        HELM_REPOS_BY_STACK["infra"].get("seaweedfs-operator"),
        (operator.get("chart"), operator.get("namespace"), operator.get("values")),
        "seaweedfs-operator" in infra
        and infra.index("cert-manager") < infra.index("seaweedfs-operator"),
        POST_HELM_BY_STACK["infra"][-1],
        "seaweedfs-operator" in elsewhere,
    ) == (
        "https://seaweedfs.github.io/seaweedfs-operator",
        (
            "seaweedfs-operator/seaweedfs-operator",
            "object-store",
            ["object-store/operator-values.yaml"],
        ),
        True,
        Path("object-store"),
        False,
    )


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
    uninstall would delete every ServiceMonitor in the cluster (#819)."""
    from devops_cli.commands.k8s.stack_lifecycle import HELM_RELEASES_BY_STACK

    infra_names = [r["name"] for r in HELM_RELEASES_BY_STACK["infra"]]

    result = runner.invoke(app, ["teardown-stack", "--stack", "infra"])

    uninstalled = [argv[2] for argv in calls_starting(process_fake, "helm", "uninstall")]
    assert (
        result.exit_code,
        "prometheus-operator-crds" in infra_names,
        uninstalled,
    ) == (
        0,
        True,
        [name for name in reversed(infra_names) if name != "prometheus-operator-crds"],
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


_LINTED_APPLICATION = """apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: web
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example/repo
    path: k8s/web
  destination:
    namespace: web
"""


@pytest.mark.parametrize("has_config", [True, False], ids=["config", "no-config"])
def test_k8s_lint_of_the_tree_lints_the_build_of_each_application(
    tmp_path: Path, scanner_fake: ScannerFake, process_fake: ProcessFake, has_config: bool
) -> None:
    """With no target, `k8s lint` builds each path source of the Applications of the tree into one
    folder, and kube-linter reads that folder with the config file of the repository, when the
    repository holds one. A finding fails the command."""
    root = tmp_path / "repo"
    (root / "k8s" / "argocd" / "apps").mkdir(parents=True)
    (root / "k8s" / "argocd" / "apps" / "web.yaml").write_text(_LINTED_APPLICATION, "utf-8")
    (root / "k8s" / "web").mkdir()
    (root / "k8s" / "web" / "kustomization.yaml").write_text("resources: []\n", "utf-8")
    if has_config:
        (root / ".kube-linter.yaml").write_text("checks: {}\n", "utf-8")
    process_fake.answer(("kubectl", "kustomize"), ProcessAnswer(stdout="kind: Deployment\n"))
    process_fake.answer(
        lambda call: "remote.origin.url" in call.argv,
        ProcessAnswer(stdout="https://github.com/example/repo.git\n"),
    )
    linted: list[tuple[list[str], tuple[str, ...]]] = []

    def kube_linter(request: Any) -> ToolAnswer:
        folder = Path(request.arguments[1])
        linted.append(
            (
                [f"{p.name}: {p.read_text('utf-8')}" for p in sorted(folder.iterdir())],
                request.arguments[2:],
            )
        )
        return ToolAnswer(exit_code=1, stdout=_KUBE_LINTER_FINDING)

    scanner_fake.answer_with("kube-linter", kube_linter)

    res = runner.invoke(app, ["lint", "--k8s-dir", str(root / "k8s")])

    config = ("--config", str(root / ".kube-linter.yaml")) if has_config else ()
    assert (res.exit_code, linted) == (
        1,
        [(["web-0.yaml: kind: Deployment\n"], ("--format", "json", *config))],
    )


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


# =============================================================================
# No In-Cluster Image Registry (#1630)
# =============================================================================


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

    assert (
        (pyro_release["chart"], pyro_release["namespace"]),
        pyro_release["chart"].split("/")[0] in _HELM_REPOS_BY_STACK["infra"],
    ) == (("grafana/pyroscope", "monitoring"), True)


def test_pyroscope_port_forward_and_proxy_targets() -> None:
    """Verify Pyroscope networking, port-forwarding, and configuration targets."""
    from devops_cli.commands.k8s.networking import (
        _NODEPORT_KEYS_INFRA,
        _PROXY_TARGETS_INFRA,
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
    pyro_svc = next((s for s in services if s[1] == "svc/pyroscope"), None)

    assert (
        DEFAULT_PYROSCOPE_PORT,
        DEFAULT_PYROSCOPE_URL,
        pyro_proxy,
        "pyroscope.url" in _NODEPORT_KEYS_INFRA,
        pyro_svc,
        Settings().pyroscope.url,
    ) == (
        4040,
        "http://localhost:4040",
        ("pyroscope.url", "monitoring", ("pyroscope",), ("4040", "http2", "http")),
        True,
        ("monitoring", "svc/pyroscope", 4040, 4040),
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


_ORIGINS = (
    "---\napiVersion: v1\nkind: ConfigMap\n"
    "metadata:\n  name: open-webui-origins\n  namespace: llm\n"
    "data:\n  CORS_ALLOW_ORIGIN: https://chat.example.com\n"
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
        if call.local_read:
            # A read of the checkout reads no cluster: its `origin` gets the empty answer of a
            # checkout outside any repository, and the build of a path source holds no object.
            return subprocess.CompletedProcess(cmd, int(cmd[0] == "git"), "", "")
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
        elif self.revision == "origins":
            out = _ingress("open-webui-ingress", "llm", "chat.example.com") + _ORIGINS
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


def _stdin_payloads(cluster: _Cluster) -> list[str]:
    """The manifest of each `kubectl apply -f -` call, in the order the command sent them."""
    return [given or "" for cmd, given in cluster.calls if cmd == _APPLY_STDIN]


def test_deploy_stack_on_argo_cd_applies_the_config_map_and_sets_hosts_from_each_applications_revision(
    isolate_devops_cli_config: Path, make_cluster: ClusterFactory
) -> None:
    """The hosts come from what the Applications render at their revision, not the checkout, and
    the ConfigMap and its credential-free copy come from the active config (#4147)."""
    _configure_service(isolate_devops_cli_config)
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "devops", "--domain", _DOMAIN)
    config_map, sandbox = (yaml.safe_load(payload) for payload in _stdin_payloads(cluster)[:2])
    service = yaml.safe_load(config_map["data"]["devops-cli.yaml"])["service"]
    assert (
        res.exit_code,
        cluster.writes(),
        config_map["metadata"]["name"],
        sandbox["metadata"]["name"],
        (service["repos"], service["github_app"]["slug"]),
    ) == (
        0,
        [_APPLY_STDIN, _APPLY_STDIN, _DEVOPS_HOSTS, _INGRESS_HOSTS],
        "devops-cli-config",
        "devops-cli-config-sandbox",
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


def test_deploy_stack_on_argo_cd_sets_the_open_webui_origins_under_the_configured_domain(
    make_cluster: ClusterFactory,
) -> None:
    """Open WebUI allows only the origins of its Ingress hosts: the ConfigMap that holds them
    gets the configured domain as a Kustomize patch on Application `ingress`, with the hosts
    (#5306)."""
    cluster = make_cluster()
    res = _deploy(cluster, "--stack", "infra", "--domain", _DOMAIN, "--argocd-revision", "origins")
    (sent,) = cluster.writes()
    patches = json.loads(sent[sent.index("-p") + 1])["spec"]["source"]["kustomize"]["patches"]
    origins = next(p for p in patches if p["target"]["kind"] == "ConfigMap")
    assert (res.exit_code, sent[:4], origins["target"]["name"], json.loads(origins["patch"])) == (
        0,
        ["kubectl", "patch", "application", "ingress"],
        "open-webui-origins",
        [
            {"op": "test", "path": "/data/CORS_ALLOW_ORIGIN", "value": "https://chat.example.com"},
            {
                "op": "replace",
                "path": "/data/CORS_ALLOW_ORIGIN",
                "value": f"https://chat.{_DOMAIN}",
            },
        ],
    )


def test_native_deploy_stack_llm_applies_the_open_webui_origins_before_its_chart(
    make_cluster: ClusterFactory,
) -> None:
    """Without Argo CD, the llm deploy applies the CORS origins of Open WebUI under the
    configured domain before it installs the chart, so the pod finds its ConfigMap (#5306)."""
    cluster = make_cluster(argo=False)
    res = _deploy(cluster, "--stack", "llm", "--k8s-dir", "k8s", "--domain", _DOMAIN, "--no-wait")
    steps = [
        ("origins", yaml.safe_load(given)["data"]["CORS_ALLOW_ORIGIN"])
        if "open-webui-origins" in (given or "")
        else ("release", next(arg for arg in cmd[3:] if not arg.startswith("--")))
        for cmd, given in cluster.calls
        if "open-webui-origins" in (given or "") or cmd[:3] == ["helm", "upgrade", "--install"]
    ]
    assert (
        res.exit_code,
        [step for step, _ in steps[:2]],
        steps[1][1],
        "example.com" in steps[0][1],
        _DOMAIN in steps[0][1],
    ) == (0, ["origins", "release"], "open-webui", False, True)


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
    keyring_store.values["searxng_metrics_password"] = "deploy-searxng-metrics-0001"
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
    keyring_store.values["searxng_metrics_password"] = "deploy-searxng-metrics-0001"
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
        ["<push>", "apply", "apply", "patch", "patch"],
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
    config_map, sandbox = (yaml.safe_load(payload) for payload in _stdin_payloads(cluster)[:2])
    # The ConfigMaps `devops-cli-config` and `devops-cli-config-sandbox` have no file: they are
    # rendered and sent on stdin, and no command applies their template.
    assert (
        res.exit_code,
        applied[0][:3],
        applied[1],
        applied[2],
        config_map["metadata"]["name"],
        sandbox["metadata"]["name"],
        [cmd for cmd in applied if any("configmap.example" in part for part in cmd)],
    ) == (
        0,
        ["kubectl", "apply", "-k"],
        _APPLY_STDIN,
        _APPLY_STDIN,
        "devops-cli-config",
        "devops-cli-config-sandbox",
        [],
    )


def test_deploy_stack_applies_the_credential_free_sandbox_config_map(
    isolate_devops_cli_config: Path, make_cluster: ClusterFactory
) -> None:
    """The devops stack applies the credential-free copy of the config right after the ConfigMap
    itself, so the planner run Job mounts a config that holds no credential key (#4147)."""
    _configure_service(isolate_devops_cli_config)
    cluster = make_cluster(argo=False)
    res = _deploy(cluster, "--stack", "devops", "--domain", _DOMAIN)
    payloads = _stdin_payloads(cluster)
    config_map, sandbox = (yaml.safe_load(payload) for payload in payloads[:2])
    inner = yaml.safe_load(sandbox["data"]["devops-cli.yaml"])
    assert (
        res.exit_code,
        config_map["metadata"]["name"],
        sandbox["metadata"]["name"],
        sandbox["metadata"]["namespace"],
        list(sandbox["data"]),
        credential_key_paths(inner),
    ) == (
        0,
        "devops-cli-config",
        "devops-cli-config-sandbox",
        "devops",
        ["devops-cli.yaml"],
        [],
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
    sandbox_delete = [
        "kubectl",
        "delete",
        "configmap",
        "devops-cli-config-sandbox",
        "-n",
        "devops",
        "--ignore-not-found",
    ]
    assert (
        res.exit_code,
        [*delete, *_CONTEXT] in cluster.writes(),
        [*sandbox_delete, *_CONTEXT] in cluster.writes(),
    ) == (0, True, True)


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
        "devops/devops-cli-config-sandbox" in res.output,
        "argocd/devops" in res.output,
        "argocd/ingress" in res.output,
    ) == (0, [], True, True, True, True)


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
    """deploy-stack and teardown-stack under --dry-run invoke no kubectl or helm commands. A
    local read of the checkout, such as its `origin`, is no cluster call."""
    res_deploy = runner.invoke(app, ["deploy-stack", "--stack", "infra", "--dry-run"])
    res_teardown = runner.invoke(app, ["teardown-stack", "--stack", "infra", "--dry-run"])

    assert (
        res_deploy.exit_code,
        res_teardown.exit_code,
        [call for call in process_fake.calls if not call.local_read],
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
            # The object store, after the charts: its Seaweed CR needs the operator's CRD (#4750).
            Path("k8s", "object-store"),
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
    stack: str,
    kustomizations: list[str],
    isolate_devops_cli_config: Path,
    process_fake: ProcessFake,
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
    """teardown-stack removes `monitoring-default-perimeter-ingress` and
    `monitoring-default-perimeter-egress` with namespace `monitoring` (#913, #6708).

    `--stack all` deletes the root kustomization's objects, namespace `monitoring` among them, and
    `--stack infra` deletes that namespace; either takes the namespace's NetworkPolicies with it.
    """
    name_contexts(cluster, "minikube")

    res = runner.invoke(app, ["teardown-stack", "--stack", stack, "--k8s-dir", "k8s", *_CONTEXT])

    commands = [call.argv for call in process_fake.calls]
    assert (res.exit_code, (*removal, *_CONTEXT) in commands) == (0, True)


_ARGO_WORKFLOWS_POLICY = str(Path("k8s", "argo-workflows", "networkpolicy.yaml"))
_ARGO_WORKFLOWS_TEMPLATE = str(Path("k8s", "argo-workflows", "workflowtemplate-version.yaml"))
# The object store, the last post-Helm path of stack infra (#4750).
_OBJECT_STORE = str(Path("k8s", "object-store"))


def test_infra_dry_runs_list_the_argo_workflows_release_perimeter_and_template(
    process_fake: ProcessFake,
) -> None:
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
        [_ARGO_WORKFLOWS_TEMPLATE, _OBJECT_STORE],
        0,
        True,
        True,
        [_OBJECT_STORE, _ARGO_WORKFLOWS_TEMPLATE],
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
        [call for call in process_fake.calls if not call.local_read],
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
