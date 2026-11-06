"""The sandbox network modes: their names, Docker networks, deploy config and fail-closed whitelists."""

from __future__ import annotations

from pathlib import Path

import pytest

import devops_cli.main  # noqa: F401  # loaded here, not in a test: MCP dispatches through it
from devops_cli.config.constants import (
    CONST_SANDBOX_DOCKER_INTERNAL_NET,
    CONST_SANDBOX_NETWORK_BRIDGE,
    CONST_SANDBOX_NETWORK_ISOLATED,
    CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    CONST_SANDBOX_NETWORK_NAMESPACE,
    CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
)
from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner
from devops_cli.exceptions import SandboxValidationError
from devops_cli.sandbox.models import (
    SandboxDeployConfig,
    SandboxNetworkConfig,
    SandboxNetworkMode,
)
from tests.support.fakes.docker_engine import DockerEngineFake


def test_sandbox_network_mode_enum_and_constants() -> None:
    """Verify SandboxNetworkMode enum values match system constants."""
    assert SandboxNetworkMode.ISOLATED.value == CONST_SANDBOX_NETWORK_ISOLATED
    assert SandboxNetworkMode.SANDBOX_NAMESPACE.value == CONST_SANDBOX_NETWORK_NAMESPACE
    assert SandboxNetworkMode.PUBLIC_WHITELIST.value == CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST
    assert SandboxNetworkMode.LOCAL_WHITELIST.value == CONST_SANDBOX_NETWORK_LOCAL_WHITELIST
    assert SandboxNetworkMode.BRIDGE.value == CONST_SANDBOX_NETWORK_BRIDGE


@pytest.mark.usefixtures("public_dns")
def test_sandbox_network_config_normalization_and_aliases() -> None:
    """Verify string mode normalization and user-friendly aliases."""
    assert SandboxNetworkConfig(mode="isolated").mode == SandboxNetworkMode.ISOLATED
    assert SandboxNetworkConfig(mode="none").mode == SandboxNetworkMode.ISOLATED
    assert SandboxNetworkConfig(mode="isolated_pod").mode == SandboxNetworkMode.ISOLATED

    assert (
        SandboxNetworkConfig(mode="sandbox_namespace").mode == SandboxNetworkMode.SANDBOX_NAMESPACE
    )
    assert (
        SandboxNetworkConfig(mode="sandbox-namespace").mode == SandboxNetworkMode.SANDBOX_NAMESPACE
    )
    assert SandboxNetworkConfig(mode="namespace").mode == SandboxNetworkMode.SANDBOX_NAMESPACE
    assert SandboxNetworkConfig(mode="internal").mode == SandboxNetworkMode.SANDBOX_NAMESPACE

    assert (
        SandboxNetworkConfig(mode="public_whitelist", public_whitelist=["github.com"]).mode
        == SandboxNetworkMode.PUBLIC_WHITELIST
    )
    assert (
        SandboxNetworkConfig(mode="public-whitelist", public_whitelist=["github.com"]).mode
        == SandboxNetworkMode.PUBLIC_WHITELIST
    )
    assert (
        SandboxNetworkConfig(mode="public", public_whitelist=["github.com"]).mode
        == SandboxNetworkMode.PUBLIC_WHITELIST
    )

    assert (
        SandboxNetworkConfig(
            mode="local_whitelist", local_whitelist=["http://localhost:11434"]
        ).mode
        == SandboxNetworkMode.LOCAL_WHITELIST
    )
    assert (
        SandboxNetworkConfig(
            mode="local-whitelist", local_whitelist=["http://localhost:11434"]
        ).mode
        == SandboxNetworkMode.LOCAL_WHITELIST
    )
    assert (
        SandboxNetworkConfig(mode="local", local_whitelist=["http://localhost:11434"]).mode
        == SandboxNetworkMode.LOCAL_WHITELIST
    )

    assert SandboxNetworkConfig(mode="bridge").mode == SandboxNetworkMode.BRIDGE


_DOCKER_NETWORK_BY_MODE: dict[SandboxNetworkMode, tuple[str, dict[str, list[str]]]] = {
    SandboxNetworkMode.ISOLATED: ("none", {}),
    SandboxNetworkMode.SANDBOX_NAMESPACE: (CONST_SANDBOX_DOCKER_INTERNAL_NET, {}),
    SandboxNetworkMode.PUBLIC_WHITELIST: (
        CONST_SANDBOX_DOCKER_INTERNAL_NET,
        {"public_whitelist": ["example.com"]},
    ),
    SandboxNetworkMode.LOCAL_WHITELIST: (
        CONST_SANDBOX_DOCKER_INTERNAL_NET,
        {"local_whitelist": ["http://localhost:8080"]},
    ),
    SandboxNetworkMode.BRIDGE: ("bridge", {}),
}


@pytest.mark.usefixtures("public_dns")
@pytest.mark.parametrize("mode", list(SandboxNetworkMode), ids=lambda mode: mode.value)
def test_every_network_mode_runs_on_one_docker_network(mode: SandboxNetworkMode) -> None:
    """Isolated runs on no network, the bridge on the default bridge, and the other modes on the
    egress-denied internal bridge, whether or not a proxy is set."""
    docker_network, whitelist = _DOCKER_NETWORK_BY_MODE[mode]

    assert SandboxNetworkConfig(mode=mode, **whitelist).to_docker_network_mode() == docker_network


def test_sandbox_network_config_isolated_mode() -> None:
    """Verify isolated pod mode produces zero-ingress, zero-egress NetworkPolicy."""
    cfg = SandboxNetworkConfig(mode=SandboxNetworkMode.ISOLATED)

    policy = cfg.to_k8s_network_policy(name="app-sandbox", namespace="sandbox")
    assert policy["apiVersion"] == "networking.k8s.io/v1"
    assert policy["kind"] == "NetworkPolicy"
    assert policy["metadata"]["name"] == "app-sandbox-network-policy"
    assert policy["metadata"]["namespace"] == "sandbox"
    assert policy["spec"]["podSelector"] == {
        "matchLabels": {"app.kubernetes.io/name": "app-sandbox"}
    }
    assert sorted(policy["spec"]["policyTypes"]) == ["Egress", "Ingress"]
    assert policy["spec"]["ingress"] == []
    assert policy["spec"]["egress"] == []


def test_sandbox_network_config_sandbox_namespace_mode() -> None:
    """Verify sandbox namespace mode produces intra-namespace only NetworkPolicy."""
    cfg = SandboxNetworkConfig(
        mode=SandboxNetworkMode.SANDBOX_NAMESPACE, sandbox_namespace="sandbox-app"
    )

    policy = cfg.to_k8s_network_policy(name="app-sandbox", namespace="sandbox-app")
    assert policy["kind"] == "NetworkPolicy"
    assert policy["metadata"]["namespace"] == "sandbox-app"
    assert sorted(policy["spec"]["policyTypes"]) == ["Egress", "Ingress"]

    # Ingress only from pods inside the same namespace
    assert policy["spec"]["ingress"] == [{"from": [{"podSelector": {}}]}]

    # Egress only to pods inside the same namespace and CoreDNS port 53
    egress_rules = policy["spec"]["egress"]
    assert len(egress_rules) == 2
    assert {"to": [{"podSelector": {}}]} in egress_rules
    has_dns = any(any(p.get("port") == 53 for p in rule.get("ports", [])) for rule in egress_rules)
    assert has_dns, "Sandbox namespace policy must allow CoreDNS egress on port 53"


@pytest.mark.usefixtures("public_dns")
def test_sandbox_deploy_config_integration(tmp_path: Path) -> None:
    """Verify SandboxDeployConfig seamlessly integrates SandboxNetworkConfig."""
    # Default is isolated
    deploy_cfg = SandboxDeployConfig(workspace_dir=tmp_path)
    assert deploy_cfg.network_config.mode == SandboxNetworkMode.ISOLATED
    assert deploy_cfg.network_mode == "none"

    # Explicit network_mode string initializes network_config
    deploy_cfg2 = SandboxDeployConfig(
        workspace_dir=tmp_path,
        network_mode="sandbox-namespace",
    )
    assert deploy_cfg2.network_config.mode == SandboxNetworkMode.SANDBOX_NAMESPACE
    assert deploy_cfg2.network_mode == "sandbox_namespace"

    # Explicit network_config model overrides and syncs network_mode
    net_cfg = SandboxNetworkConfig(
        mode=SandboxNetworkMode.PUBLIC_WHITELIST,
        public_whitelist=["github.com"],
    )
    deploy_cfg3 = SandboxDeployConfig(workspace_dir=tmp_path, network_config=net_cfg)
    assert deploy_cfg3.network_config.mode == SandboxNetworkMode.PUBLIC_WHITELIST
    assert deploy_cfg3.network_mode == "public_whitelist"


def test_workload_sandbox_config_integration(tmp_path: Path) -> None:
    """Verify WorkloadSandboxConfig seamlessly integrates SandboxNetworkConfig."""
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path,
        command=["echo", "hi"],
        network_mode="isolated",
    )
    assert cfg.network_config.mode == SandboxNetworkMode.ISOLATED
    assert cfg.network_mode == "none"


@pytest.mark.usefixtures("public_dns", "docker_daemon")
def test_docker_runner_whitelist_fail_closed_without_proxy(tmp_path: Path) -> None:
    """Verify WorkloadSandboxRunner fails closed if whitelist modes lack an egress proxy."""
    from devops_cli.exceptions.docker import DockerSandboxError

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    cfg_pub = WorkloadSandboxConfig(
        workspace_dir=workspace,
        command=["echo", "test"],
        network_mode="public_whitelist",
        public_whitelist=["github.com"],
    )
    runner_pub = WorkloadSandboxRunner(cfg_pub)
    with pytest.raises(DockerSandboxError, match="cannot enforce egress whitelist filtering"):
        runner_pub.run()

    cfg_loc = WorkloadSandboxConfig(
        workspace_dir=workspace,
        command=["echo", "test"],
        network_mode="local_whitelist",
        local_whitelist=["http://localhost:11434"],
    )
    runner_loc = WorkloadSandboxRunner(cfg_loc)
    with pytest.raises(DockerSandboxError, match="cannot enforce egress whitelist filtering"):
        runner_loc.run()


def test_workload_sandbox_result_secret_masking() -> None:
    """Verify WorkloadSandboxResult automatically sanitizes sensitive tokens in output."""
    from devops_cli.docker.sandbox import WorkloadSandboxResult

    raw_out = "Authorized with ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 token"
    res = WorkloadSandboxResult(
        exit_code=0,
        stdout=raw_out,
        stderr=raw_out,
    )
    assert "ghp_ABCDE" not in res.stdout
    assert "<masked-github-token>" in res.stdout
    assert "<masked-github-token>" in res.stderr


@pytest.mark.usefixtures("public_dns")
def test_sandbox_engine_whitelist_fail_closed_without_proxy(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """Verify WorkloadSandboxEngine fails closed if deploy config whitelist lacks egress proxy."""
    from devops_cli.sandbox.engine import WorkloadSandboxEngine

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    deploy_cfg = SandboxDeployConfig(
        workspace_dir=workspace,
        network_mode="public_whitelist",
        public_whitelist=["github.com"],
    )
    with pytest.raises(SandboxValidationError, match="cannot enforce egress whitelist boundaries"):
        WorkloadSandboxEngine().deploy(deploy_cfg)
    assert "containers.create" not in docker_daemon.call_names()
