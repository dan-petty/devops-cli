"""Unit tests for multi-tier sandbox networking configuration options and NetworkPolicy generator."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.docker import app as docker_app
from devops_cli.commands.sandbox import app as sandbox_app
from devops_cli.config.constants import (
    CONST_SANDBOX_DOCKER_INTERNAL_NET,
    CONST_SANDBOX_NETWORK_BRIDGE,
    CONST_SANDBOX_NETWORK_ISOLATED,
    CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    CONST_SANDBOX_NETWORK_NAMESPACE,
    CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
)
from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner
from devops_cli.sandbox.models import (
    SandboxDeployConfig,
    SandboxNetworkConfig,
    SandboxNetworkMode,
)

runner = CliRunner()


def test_sandbox_network_mode_enum_and_constants() -> None:
    """Verify SandboxNetworkMode enum values match system constants."""
    assert SandboxNetworkMode.ISOLATED.value == CONST_SANDBOX_NETWORK_ISOLATED
    assert SandboxNetworkMode.SANDBOX_NAMESPACE.value == CONST_SANDBOX_NETWORK_NAMESPACE
    assert SandboxNetworkMode.PUBLIC_WHITELIST.value == CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST
    assert SandboxNetworkMode.LOCAL_WHITELIST.value == CONST_SANDBOX_NETWORK_LOCAL_WHITELIST
    assert SandboxNetworkMode.BRIDGE.value == CONST_SANDBOX_NETWORK_BRIDGE


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


def test_sandbox_network_config_isolated_mode() -> None:
    """Verify isolated pod mode produces zero-ingress, zero-egress NetworkPolicy and --network=none."""
    cfg = SandboxNetworkConfig(mode=SandboxNetworkMode.ISOLATED)

    assert cfg.to_docker_args() == ["--network=none"]

    policy = cfg.to_k8s_network_policy(name="app-sandbox", namespace="sandbox")
    assert policy["apiVersion"] == "networking.k8s.io/v1"
    assert policy["kind"] == "NetworkPolicy"
    assert policy["metadata"]["name"] == "app-sandbox-network-policy"
    assert policy["metadata"]["namespace"] == "sandbox"
    assert policy["spec"]["podSelector"] == {}
    assert sorted(policy["spec"]["policyTypes"]) == ["Egress", "Ingress"]
    assert policy["spec"]["ingress"] == []
    assert policy["spec"]["egress"] == []


def test_sandbox_network_config_sandbox_namespace_mode() -> None:
    """Verify sandbox namespace mode produces intra-namespace only NetworkPolicy and internal bridge."""
    cfg = SandboxNetworkConfig(
        mode=SandboxNetworkMode.SANDBOX_NAMESPACE, sandbox_namespace="sandbox-app"
    )

    assert cfg.to_docker_args() == [f"--network={CONST_SANDBOX_DOCKER_INTERNAL_NET}"]

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


def test_sandbox_network_config_public_whitelist_validation_and_policy() -> None:
    """Verify public whitelist validates domain names, rejects private/metadata IPs, and generates egress policy."""
    # Valid public domains and IPs
    cfg = SandboxNetworkConfig(
        mode=SandboxNetworkMode.PUBLIC_WHITELIST,
        public_whitelist=["github.com", "pypi.org", "93.184.216.34"],
    )
    assert cfg.to_docker_args() == ["--network=bridge"]

    policy = cfg.to_k8s_network_policy(name="app-sandbox", namespace="sandbox")
    assert policy["kind"] == "NetworkPolicy"
    egress_rules = policy["spec"]["egress"]
    assert len(egress_rules) >= 1

    # Verify that metadata and private RFC 1918 IPs are blocked in the policy
    ip_blocks = [
        t["ipBlock"] for rule in egress_rules for t in rule.get("to", []) if "ipBlock" in t
    ]
    assert ip_blocks, "Public whitelist policy must define ipBlock constraints"
    for block in ip_blocks:
        except_cidrs = block.get("except", [])
        assert "169.254.169.254/32" in except_cidrs
        assert "10.0.0.0/8" in except_cidrs
        assert "172.16.0.0/12" in except_cidrs
        assert "192.168.0.0/16" in except_cidrs

    # Empty whitelist should raise ValueError
    with pytest.raises(ValueError, match="at least one public domain or IP"):
        SandboxNetworkConfig(mode=SandboxNetworkMode.PUBLIC_WHITELIST, public_whitelist=[])

    # Private IP or cloud metadata in public whitelist should raise ValueError
    with pytest.raises(ValueError, match="private, loopback, or metadata"):
        SandboxNetworkConfig(
            mode=SandboxNetworkMode.PUBLIC_WHITELIST,
            public_whitelist=["169.254.169.254"],
        )
    with pytest.raises(ValueError, match="private, loopback, or metadata"):
        SandboxNetworkConfig(
            mode=SandboxNetworkMode.PUBLIC_WHITELIST,
            public_whitelist=["192.168.1.10"],
        )
    with pytest.raises(ValueError, match="private, loopback, or metadata"):
        SandboxNetworkConfig(
            mode=SandboxNetworkMode.PUBLIC_WHITELIST,
            public_whitelist=["localhost"],
        )


def test_sandbox_network_config_local_whitelist_validation_and_routing() -> None:
    """Verify local whitelist validates endpoints, rejects cloud metadata, and configures routing."""
    cfg = SandboxNetworkConfig(
        mode=SandboxNetworkMode.LOCAL_WHITELIST,
        local_whitelist=[
            "http://localhost:11434",
            "192.168.1.50",
            "http://10.0.0.5:8000",
            "host.docker.internal",
        ],
    )
    docker_args = cfg.to_docker_args()
    assert "--network=bridge" in docker_args
    assert any("--add-host=host.docker.internal:host-gateway" in arg for arg in docker_args)

    policy = cfg.to_k8s_network_policy(name="app-sandbox", namespace="sandbox")
    assert policy["kind"] == "NetworkPolicy"
    egress_rules = policy["spec"]["egress"]
    assert len(egress_rules) >= 1

    # Empty local whitelist should raise ValueError
    with pytest.raises(ValueError, match="at least one local URL or IP"):
        SandboxNetworkConfig(mode=SandboxNetworkMode.LOCAL_WHITELIST, local_whitelist=[])

    # Cloud metadata in local whitelist should raise ValueError
    with pytest.raises(ValueError, match="Cloud metadata .* is forbidden"):
        SandboxNetworkConfig(
            mode=SandboxNetworkMode.LOCAL_WHITELIST,
            local_whitelist=["169.254.169.254"],
        )


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

    runner_inst = WorkloadSandboxRunner(cfg)
    dry = runner_inst.build_dry_run_details()
    assert dry["network_mode"] == "none"
    assert dry["network_config"]["mode"] == "isolated"


def test_cli_sandbox_network_policy_command() -> None:
    """Verify `devops sandbox network-policy` CLI command generates valid Kubernetes YAML."""
    res = runner.invoke(
        sandbox_app,
        [
            "network-policy",
            "--network-mode",
            "isolated",
            "--name",
            "test-pod",
            "--namespace",
            "test-ns",
        ],
    )
    assert res.exit_code == 0
    parsed = yaml.safe_load(res.stdout)
    assert parsed["kind"] == "NetworkPolicy"
    assert parsed["metadata"]["name"] == "test-pod-network-policy"
    assert parsed["metadata"]["namespace"] == "test-ns"
    assert parsed["spec"]["ingress"] == []
    assert parsed["spec"]["egress"] == []

    # Test namespace mode
    res_ns = runner.invoke(
        sandbox_app,
        ["network-policy", "--network-mode", "sandbox-namespace", "--namespace", "custom-ns"],
    )
    assert res_ns.exit_code == 0
    parsed_ns = yaml.safe_load(res_ns.stdout)
    assert parsed_ns["kind"] == "NetworkPolicy"
    assert parsed_ns["metadata"]["namespace"] == "custom-ns"

    # Test public whitelist mode
    res_pub = runner.invoke(
        sandbox_app,
        [
            "network-policy",
            "--network-mode",
            "public-whitelist",
            "--public-whitelist",
            "github.com,pypi.org",
        ],
    )
    assert res_pub.exit_code == 0
    parsed_pub = yaml.safe_load(res_pub.stdout)
    assert parsed_pub["kind"] == "NetworkPolicy"

    # Test local whitelist mode
    res_local = runner.invoke(
        sandbox_app,
        [
            "network-policy",
            "--network-mode",
            "local-whitelist",
            "--local-whitelist",
            "http://localhost:11434,192.168.1.50",
        ],
    )
    assert res_local.exit_code == 0
    parsed_local = yaml.safe_load(res_local.stdout)
    assert parsed_local["kind"] == "NetworkPolicy"


def test_cli_sandbox_deploy_network_options(tmp_path: Path) -> None:
    """Verify `devops sandbox deploy --dry-run` with multi-tier network options."""
    res = runner.invoke(
        sandbox_app,
        [
            "deploy",
            "--dry-run",
            "--workspace",
            str(tmp_path),
            "--network-mode",
            "isolated",
        ],
    )
    assert res.exit_code == 0
    assert "isolated" in res.stdout

    res_ns = runner.invoke(
        sandbox_app,
        [
            "deploy",
            "--dry-run",
            "--workspace",
            str(tmp_path),
            "--network-mode",
            "sandbox-namespace",
        ],
    )
    assert res_ns.exit_code == 0
    assert "sandbox_namespace" in res_ns.stdout


def test_cli_docker_sandbox_network_options(tmp_path: Path) -> None:
    """Verify `devops docker sandbox --dry-run` with multi-tier network options."""
    res = runner.invoke(
        docker_app,
        [
            "sandbox",
            "--dry-run",
            "--workspace",
            str(tmp_path),
            "--network-mode",
            "isolated",
            "echo",
            "hello",
        ],
    )
    assert res.exit_code == 0
    assert "none" in res.stdout
