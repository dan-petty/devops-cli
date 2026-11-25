"""The sandbox network modes: their names, Docker networks, deploy config and fail-closed whitelists."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_MAX_K8S_RESOURCE_NAME_LENGTH,
    CONST_SANDBOX_DOCKER_INTERNAL_NET,
    CONST_SANDBOX_NETWORK_BRIDGE,
    CONST_SANDBOX_NETWORK_ISOLATED,
    CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    CONST_SANDBOX_NETWORK_NAMESPACE,
    CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
)
from devops_cli.core.validation import is_valid_k8s_name
from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner
from devops_cli.exceptions import SandboxValidationError
from devops_cli.sandbox.models import (
    SandboxDeployConfig,
    SandboxNetworkConfig,
    SandboxNetworkMode,
)
from tests.support.fakes.dns import DnsFake
from tests.support.fakes.docker_engine import DockerEngineFake


def test_sandbox_network_mode_enum_and_constants() -> None:
    """Verify SandboxNetworkMode enum values match system constants."""
    assert SandboxNetworkMode.ISOLATED.value == CONST_SANDBOX_NETWORK_ISOLATED
    assert SandboxNetworkMode.SANDBOX_NAMESPACE.value == CONST_SANDBOX_NETWORK_NAMESPACE
    assert SandboxNetworkMode.PUBLIC_WHITELIST.value == CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST
    assert SandboxNetworkMode.LOCAL_WHITELIST.value == CONST_SANDBOX_NETWORK_LOCAL_WHITELIST
    assert SandboxNetworkMode.BRIDGE.value == CONST_SANDBOX_NETWORK_BRIDGE


def test_sandbox_network_config_normalization_and_aliases(dns: DnsFake) -> None:
    """Verify string mode normalization and user-friendly aliases."""
    dns.answer_every_name()
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


_EXPECTED_POLICY_RULES_BY_MODE: dict[
    SandboxNetworkMode, tuple[list[dict[str, object]], list[dict[str, object]]]
] = {
    SandboxNetworkMode.ISOLATED: ([], []),
    SandboxNetworkMode.SANDBOX_NAMESPACE: (
        [{"from": [{"podSelector": {}}]}],
        [
            {"to": [{"podSelector": {}}]},
            {
                "to": [
                    {
                        "namespaceSelector": {},
                        "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
                    }
                ],
                "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
            },
        ],
    ),
    SandboxNetworkMode.PUBLIC_WHITELIST: (
        [],
        [
            {
                "to": [
                    {
                        "namespaceSelector": {},
                        "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
                    }
                ],
                "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
            },
            {
                "to": [{"ipBlock": {"cidr": "93.184.215.14/32"}}],
                "ports": [{"protocol": "TCP", "port": 443}],
            },
        ],
    ),
    SandboxNetworkMode.LOCAL_WHITELIST: (
        [],
        [
            {
                "to": [
                    {
                        "namespaceSelector": {},
                        "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
                    }
                ],
                "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
            },
            {
                "to": [{"ipBlock": {"cidr": "192.0.2.1/32"}}],
                "ports": [{"protocol": "TCP", "port": 8080}],
            },
        ],
    ),
    SandboxNetworkMode.BRIDGE: (
        [{"from": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]}],
        [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}]}],
    ),
}


@pytest.mark.parametrize("mode", list(SandboxNetworkMode), ids=lambda mode: mode.value)
def test_every_network_mode_runs_on_one_docker_network(
    mode: SandboxNetworkMode, dns: DnsFake
) -> None:
    """Isolated runs on no network, the bridge on the default bridge, and the other modes on the
    egress-denied internal bridge, whether or not a proxy is set."""
    dns.answer_every_name()
    docker_network, whitelist = _DOCKER_NETWORK_BY_MODE[mode]

    assert SandboxNetworkConfig(mode=mode, **whitelist).to_docker_network_mode() == docker_network


def test_sandbox_network_config_isolated_mode() -> None:
    """Verify isolated pod mode produces zero-ingress Ingress-only and zero-egress Egress-only policies."""
    cfg = SandboxNetworkConfig(mode=SandboxNetworkMode.ISOLATED)

    ingress_policy, egress_policy = cfg.to_k8s_network_policy(
        name="app-sandbox", namespace="sandbox"
    )
    expected_selector = {"matchLabels": {"app.kubernetes.io/name": "app-sandbox"}}
    assert ingress_policy == {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": "app-sandbox-network-policy-ingress", "namespace": "sandbox"},
        "spec": {
            "podSelector": expected_selector,
            "policyTypes": ["Ingress"],
            "ingress": [],
        },
    }
    assert egress_policy == {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": "app-sandbox-network-policy-egress", "namespace": "sandbox"},
        "spec": {
            "podSelector": expected_selector,
            "policyTypes": ["Egress"],
            "egress": [],
        },
    }


def test_sandbox_network_config_sandbox_namespace_mode() -> None:
    """Verify sandbox namespace mode splits intra-namespace ingress and egress into two policies."""
    cfg = SandboxNetworkConfig(
        mode=SandboxNetworkMode.SANDBOX_NAMESPACE, sandbox_namespace="sandbox-app"
    )

    ingress_policy, egress_policy = cfg.to_k8s_network_policy(
        name="app-sandbox", namespace="sandbox-app"
    )
    assert ingress_policy["kind"] == "NetworkPolicy"
    assert egress_policy["kind"] == "NetworkPolicy"
    assert ingress_policy["metadata"]["namespace"] == "sandbox-app"
    assert egress_policy["metadata"]["namespace"] == "sandbox-app"
    assert ingress_policy["spec"]["policyTypes"] == ["Ingress"]
    assert egress_policy["spec"]["policyTypes"] == ["Egress"]
    assert "egress" not in ingress_policy["spec"]
    assert "ingress" not in egress_policy["spec"]

    # Ingress only from pods inside the same namespace
    assert ingress_policy["spec"]["ingress"] == [{"from": [{"podSelector": {}}]}]

    # Egress only to pods inside the same namespace and CoreDNS port 53
    egress_rules = egress_policy["spec"]["egress"]
    assert len(egress_rules) == 2
    assert {"to": [{"podSelector": {}}]} in egress_rules
    has_dns = any(any(p.get("port") == 53 for p in rule.get("ports", [])) for rule in egress_rules)
    assert has_dns, "Sandbox namespace policy must allow CoreDNS egress on port 53"


@pytest.mark.parametrize("mode", list(SandboxNetworkMode), ids=lambda mode: mode.value)
def test_every_network_mode_yields_a_single_type_policy_pair(
    mode: SandboxNetworkMode, dns: DnsFake
) -> None:
    """Every network mode emits two policies with distinct DNS subdomain names and one type each."""
    dns.answer_every_name()
    whitelists: dict[SandboxNetworkMode, dict[str, list[str]]] = {
        SandboxNetworkMode.ISOLATED: {},
        SandboxNetworkMode.SANDBOX_NAMESPACE: {},
        SandboxNetworkMode.PUBLIC_WHITELIST: {"public_whitelist": ["example.com"]},
        SandboxNetworkMode.LOCAL_WHITELIST: {"local_whitelist": ["http://192.0.2.1:8080"]},
        SandboxNetworkMode.BRIDGE: {},
    }
    cfg = SandboxNetworkConfig(mode=mode, **whitelists[mode])
    expected_ingress, expected_egress = _EXPECTED_POLICY_RULES_BY_MODE[mode]

    ingress_policy, egress_policy = cfg.to_k8s_network_policy(
        name="app-sandbox", namespace="sandbox"
    )

    assert ingress_policy["spec"]["policyTypes"] == ["Ingress"]
    assert egress_policy["spec"]["policyTypes"] == ["Egress"]
    assert "egress" not in ingress_policy["spec"]
    assert "ingress" not in egress_policy["spec"]
    assert (
        ingress_policy["spec"]["podSelector"]
        == egress_policy["spec"]["podSelector"]
        == {"matchLabels": {"app.kubernetes.io/name": "app-sandbox"}}
    )
    assert ingress_policy["spec"]["ingress"] == expected_ingress
    assert egress_policy["spec"]["egress"] == expected_egress
    in_name = ingress_policy["metadata"]["name"]
    eg_name = egress_policy["metadata"]["name"]
    assert in_name != eg_name
    assert is_valid_k8s_name(in_name)
    assert is_valid_k8s_name(eg_name)


@pytest.mark.parametrize(
    "long_name",
    ["a" * CONST_MAX_K8S_RESOURCE_NAME_LENGTH, ("a" * 244) + ".end"],
)
def test_long_sandbox_name_keeps_suffix_within_kubernetes_limit(long_name: str) -> None:
    """A long base policy name trims cleanly before `-ingress`/`-egress` as a DNS subdomain."""
    cfg = SandboxNetworkConfig(mode=SandboxNetworkMode.ISOLATED)

    ingress_policy, egress_policy = cfg.to_k8s_network_policy(name=long_name, namespace="sandbox")
    in_name = ingress_policy["metadata"]["name"]
    eg_name = egress_policy["metadata"]["name"]

    assert (
        in_name != eg_name,
        in_name.endswith("-ingress"),
        eg_name.endswith("-egress"),
        len(in_name) <= CONST_MAX_K8S_RESOURCE_NAME_LENGTH,
        len(eg_name) <= CONST_MAX_K8S_RESOURCE_NAME_LENGTH,
        is_valid_k8s_name(in_name),
        is_valid_k8s_name(eg_name),
    ) == (True, True, True, True, True, True, True)


def test_sandbox_deploy_config_integration(tmp_path: Path, dns: DnsFake) -> None:
    """Verify SandboxDeployConfig seamlessly integrates SandboxNetworkConfig."""
    # Default is isolated
    dns.answer_every_name()
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


@pytest.mark.usefixtures("docker_daemon")
def test_docker_runner_whitelist_fail_closed_without_proxy(tmp_path: Path, dns: DnsFake) -> None:
    """Verify WorkloadSandboxRunner fails closed if whitelist modes lack an egress proxy."""
    dns.answer_every_name()
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


def test_sandbox_engine_whitelist_fail_closed_without_proxy(
    tmp_path: Path, docker_daemon: DockerEngineFake, dns: DnsFake
) -> None:
    """Verify WorkloadSandboxEngine fails closed if deploy config whitelist lacks egress proxy."""
    dns.answer_every_name()
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


@pytest.mark.parametrize(
    ("entry", "cidr"),
    [
        ("2606:4700::/48", "2606:4700::/48"),
        ("2606:4700::1/48", "2606:4700::/48"),
        ("2606:4700::1111", "2606:4700::1111/128"),
    ],
)
def test_a_public_ipv6_whitelist_entry_is_accepted(entry: str, cidr: str) -> None:
    """A public IPv6 address or CIDR gives one ipBlock on 443, as an IPv4 CIDR does (#3776)."""
    config = SandboxNetworkConfig(mode="public_whitelist", public_whitelist=[entry])

    _, egress_policy = config.to_k8s_network_policy()
    egress = egress_policy["spec"]["egress"]
    whitelist = [rule for rule in egress if any("ipBlock" in peer for peer in rule.get("to", []))]

    assert whitelist == [
        {"to": [{"ipBlock": {"cidr": cidr}}], "ports": [{"protocol": "TCP", "port": 443}]}
    ]


@pytest.mark.parametrize("entry", ["fd00::/8", "::1/128", "fe80::/10", "fd00:ec2::254"])
def test_a_non_public_ipv6_whitelist_entry_is_refused(entry: str) -> None:
    """A private, loopback, link-local or metadata IPv6 entry is refused (#3776)."""
    with pytest.raises(
        ValueError,
        match=f"Public whitelist entry '{entry}'.*cannot be private, loopback, or metadata",
    ):
        SandboxNetworkConfig(mode="public_whitelist", public_whitelist=[entry])


def test_a_non_public_name_is_refused_with_no_lookup(dns: DnsFake) -> None:
    """The public whitelist validator refuses a name without a DNS lookup (#3776)."""
    with pytest.raises(ValueError, match="cannot be private, loopback, or metadata"):
        SandboxNetworkConfig(mode="public_whitelist", public_whitelist=["localhost"])

    assert dns.lookups == []
