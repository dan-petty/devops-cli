"""Unit tests for multi-tier sandbox networking configuration options and NetworkPolicy generator."""

from __future__ import annotations

import re
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError as PydanticValidationError
from typer.testing import CliRunner

from devops_cli.commands.docker import app as docker_app
from devops_cli.commands.sandbox import app as sandbox_app
from devops_cli.config.constants import (
    CONST_EXIT_FAILURE,
    CONST_SANDBOX_DOCKER_INTERNAL_NET,
    CONST_SANDBOX_NETWORK_BRIDGE,
    CONST_SANDBOX_NETWORK_ISOLATED,
    CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    CONST_SANDBOX_NETWORK_NAMESPACE,
    CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
)
from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner
from devops_cli.exceptions import SandboxValidationError, SSRFBlockedError
from devops_cli.sandbox.models import (
    SandboxDeployConfig,
    SandboxNetworkConfig,
    SandboxNetworkMode,
    _build_dns_egress_rule,
    _build_whitelist_egress,
    _parse_whitelist_entry,
    _resolve_local_host,
    _resolve_public_host,
)
from tests.web_fakes import PUBLIC_ADDRESS, scripted_resolver

runner = CliRunner()

# Every whitelist configuration these tests build a policy from, so that one test can check
# that each of their rules names its ports. Names resolve through `public_dns` or a stub.
_WHITELIST_POLICIES: dict[str, dict[str, Any]] = {
    "public names and an address": {
        "mode": SandboxNetworkMode.PUBLIC_WHITELIST,
        "public_whitelist": ["github.com", "pypi.org", "93.184.216.34"],
    },
    "local urls and addresses": {
        "mode": SandboxNetworkMode.LOCAL_WHITELIST,
        "local_whitelist": [
            "http://localhost:11434",
            "192.0.2.50",
            "http://198.51.100.5:8000",
        ],
    },
    "public ipv6 and ipv4 addresses": {
        "mode": SandboxNetworkMode.PUBLIC_WHITELIST,
        "public_whitelist": ["2606:4700::1", "93.184.216.34"],
    },
    "local ipv6 url and ipv4 address": {
        "mode": SandboxNetworkMode.LOCAL_WHITELIST,
        "local_whitelist": ["http://[fd00::1]:8080", "192.168.1.50"],
    },
    "https url with a port": {
        "mode": SandboxNetworkMode.PUBLIC_WHITELIST,
        "public_whitelist": ["https://1.1.1.1:8443"],
    },
    "address with a port": {
        "mode": SandboxNetworkMode.PUBLIC_WHITELIST,
        "public_whitelist": ["1.1.1.1:8443"],
    },
    "http url": {
        "mode": SandboxNetworkMode.PUBLIC_WHITELIST,
        "public_whitelist": ["http://example.com"],
    },
    "bare name": {
        "mode": SandboxNetworkMode.PUBLIC_WHITELIST,
        "public_whitelist": ["example.com"],
    },
    "bracketed ipv6 with a port": {
        "mode": SandboxNetworkMode.PUBLIC_WHITELIST,
        "public_whitelist": ["[2606:4700::1]:8443"],
    },
    "local url with a port": {
        "mode": SandboxNetworkMode.LOCAL_WHITELIST,
        "local_whitelist": ["http://192.0.2.50:11434"],
    },
    "two names, one with a port": {
        "mode": SandboxNetworkMode.PUBLIC_WHITELIST,
        "public_whitelist": ["example.com:8443", "example.org"],
    },
}


def _egress_without_dns(config: dict[str, Any], **policy: Any) -> list[dict[str, Any]]:
    """The egress rules a configuration's policy holds, the kube-dns rule left out."""
    egress = SandboxNetworkConfig(**config).to_k8s_network_policy(**policy)["spec"]["egress"]
    return [rule for rule in egress if rule != _build_dns_egress_rule()]


def _tcp_rule(cidrs: list[str], port: int) -> dict[str, Any]:
    """The egress rule that opens one TCP port to these address blocks."""
    return {
        "to": [{"ipBlock": {"cidr": cidr}} for cidr in cidrs],
        "ports": [{"protocol": "TCP", "port": port}],
    }


@pytest.fixture
def failed_lookups(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Fail every `socket.getaddrinfo` call, recording its host and flags.

    A test reads the record to show that no DNS query was made: only a call with
    `AI_NUMERICHOST`, which parses a numeric host and never queries, may appear in it.
    """
    calls: list[tuple[str, int]] = []

    def fail(host: Any, *args: Any, **kwargs: Any) -> list[Any]:
        flags = kwargs.get("flags", args[4] if len(args) >= 5 else 0) or 0
        calls.append((str(host), int(flags)))
        raise socket.gaierror(socket.EAI_NONAME, f"lookups fail in this test: {host}")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    return calls


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


def test_sandbox_network_config_public_whitelist_validation_and_policy(public_dns: str) -> None:
    """Verify public whitelist validates domain names, rejects private/metadata IPs, and generates egress policy."""
    cfg = SandboxNetworkConfig(**_WHITELIST_POLICIES["public names and an address"])

    policy = cfg.to_k8s_network_policy(name="app-sandbox", namespace="sandbox")
    # The kube-dns rule, then one rule per entry: each name resolves to the `public_dns` address.
    assert (policy["kind"], policy["spec"]["egress"]) == (
        "NetworkPolicy",
        [
            _build_dns_egress_rule(),
            _tcp_rule([f"{public_dns}/32"], 443),
            _tcp_rule([f"{public_dns}/32"], 443),
            _tcp_rule(["93.184.216.34/32"], 443),
        ],
    )

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


@pytest.mark.usefixtures("failed_lookups")
def test_sandbox_network_config_local_whitelist_validation_and_routing() -> None:
    """Verify local whitelist validates endpoints, rejects cloud metadata, and configures routing.

    The `localhost` entry opens no rule: NetworkPolicy never polices a pod's loopback.
    """
    cfg = SandboxNetworkConfig(**_WHITELIST_POLICIES["local urls and addresses"])

    policy = cfg.to_k8s_network_policy(name="app-sandbox", namespace="sandbox")
    assert (policy["kind"], policy["spec"]["egress"]) == (
        "NetworkPolicy",
        [
            _build_dns_egress_rule(),
            _tcp_rule(["192.0.2.50/32"], 443),
            _tcp_rule(["198.51.100.5/32"], 8000),
        ],
    )

    # Empty local whitelist should raise ValueError
    with pytest.raises(ValueError, match="at least one local URL or IP"):
        SandboxNetworkConfig(mode=SandboxNetworkMode.LOCAL_WHITELIST, local_whitelist=[])

    # Cloud metadata in local whitelist should raise ValueError
    with pytest.raises(ValueError, match=r"Cloud metadata .* is forbidden"):
        SandboxNetworkConfig(
            mode=SandboxNetworkMode.LOCAL_WHITELIST,
            local_whitelist=["169.254.169.254"],
        )


def test_sandbox_local_whitelist_accepts_private_suffix_and_rejects_public_dns_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """local_whitelist accepts node1.example.internal at build time and refuses a public DNS answer on policy generation (#887)."""
    import socket

    cfg = SandboxNetworkConfig(
        mode="local_whitelist",
        local_whitelist=["node1.example.internal"],
    )
    assert cfg.local_whitelist == ["node1.example.internal"]

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )
    with pytest.raises(ValueError, match=r"non-private address"):
        cfg.to_k8s_network_policy()


@pytest.mark.parametrize(
    "entry", ["host.docker.internal", "HOST.DOCKER.INTERNAL.", "http://Host.Docker.Internal:8080"]
)
def test_the_host_gateway_name_is_refused_in_the_local_whitelist_without_a_lookup(
    entry: str, failed_lookups: list[tuple[str, int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`host.docker.internal` names the container runtime's gateway on the workstation, which a
    cluster pod cannot reach, so the entry is refused and the user asked for an IP or CIDR.

    It is refused before the private-host check, even one that would admit the name, so it
    never reaches a resolver. Case and a trailing dot do not matter, as in DNS. The refusal is a
    `SandboxValidationError`, which Pydantic reports as the validation error's cause (#1174).
    """
    monkeypatch.setattr(
        "devops_cli.sandbox.models.is_loopback_or_private_host", lambda *_args, **_kwargs: True
    )
    with pytest.raises(
        PydanticValidationError, match="IP address or CIDR the cluster reaches the host on"
    ) as refusal:
        SandboxNetworkConfig(mode=SandboxNetworkMode.LOCAL_WHITELIST, local_whitelist=[entry])
    causes = [error["ctx"]["error"] for error in refusal.value.errors()]
    assert (failed_lookups, [type(cause) for cause in causes]) == ([], [SandboxValidationError])


@pytest.mark.parametrize(
    "entry", ["http://localhost:11434", "127.0.0.1", "[::1]:8080", "127.0.0.0/8", "::1/128"]
)
def test_a_loopback_entry_opens_no_egress_rule(
    entry: str, failed_lookups: list[tuple[str, int]]
) -> None:
    """NetworkPolicy never polices a pod's loopback, so a loopback entry adds no rule, and
    nothing is looked up to build the policy (#1174)."""
    policy = SandboxNetworkConfig(
        mode=SandboxNetworkMode.LOCAL_WHITELIST, local_whitelist=[entry]
    ).to_k8s_network_policy()
    assert (
        policy["spec"]["egress"],
        [host for host, flags in failed_lookups if not flags & socket.AI_NUMERICHOST],
    ) == ([_build_dns_egress_rule()], [])


@pytest.mark.usefixtures("failed_lookups")
def test_a_loopback_host_or_network_resolves_to_no_address() -> None:
    """`localhost`, a loopback address and a loopback network leave nothing to allow (#1174)."""
    hosts = ("localhost", "LOCALHOST.", "127.0.0.1", "::1", "127.0.0.0/8", "::1/128")
    assert [_resolve_local_host(host, 443) for host in hosts] == [[] for _host in hosts]


def test_an_entry_that_resolves_to_no_address_adds_no_rule() -> None:
    """A rule with an empty `to` allows every destination on its port, so none is built (#1174)."""
    assert _build_whitelist_egress(["example.com"], lambda _host, _port: []) == [
        _build_dns_egress_rule()
    ]


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


@pytest.mark.usefixtures("public_dns")
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
            ",".join(_WHITELIST_POLICIES["public names and an address"]["public_whitelist"]),
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
            ",".join(_WHITELIST_POLICIES["local urls and addresses"]["local_whitelist"]),
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


@pytest.mark.usefixtures("public_dns")
def test_docker_runner_whitelist_fail_closed_without_proxy(
    tmp_path: Path, docker_engine: Any
) -> None:
    """Verify WorkloadSandboxRunner fails closed if whitelist modes lack an egress proxy."""
    from unittest.mock import MagicMock

    from devops_cli.exceptions.docker import DockerSandboxError

    with docker_engine(MagicMock()):
        cfg_pub = WorkloadSandboxConfig(
            workspace_dir=tmp_path,
            command=["echo", "test"],
            network_mode="public_whitelist",
            public_whitelist=["github.com"],
        )
        runner_pub = WorkloadSandboxRunner(cfg_pub)
        with pytest.raises(DockerSandboxError, match="cannot enforce egress whitelist filtering"):
            runner_pub.run()

        cfg_loc = WorkloadSandboxConfig(
            workspace_dir=tmp_path,
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
    tmp_path: Path, docker_engine: Any
) -> None:
    """Verify WorkloadSandboxEngine fails closed if deploy config whitelist lacks egress proxy."""
    from unittest.mock import MagicMock

    from devops_cli.exceptions.sandbox import SandboxValidationError
    from devops_cli.sandbox.engine import WorkloadSandboxEngine

    with docker_engine(MagicMock()):
        engine = WorkloadSandboxEngine()
        deploy_cfg = SandboxDeployConfig(
            workspace_dir=tmp_path,
            network_mode="public_whitelist",
            public_whitelist=["github.com"],
        )
        with pytest.raises(
            SandboxValidationError, match="cannot enforce egress whitelist boundaries"
        ):
            engine._build_create_kwargs(deploy_cfg, tmp_path, [])


def test_a_whitelist_entry_parses_into_its_host_and_port() -> None:
    """An entry's stated port is kept; without one, https and a bare entry get 443 and http 80.

    The host is what the resolvers take: an address, a CIDR, an unbracketed IPv6 address or a
    URL's host. A bare IPv6 address takes no port suffix.
    """
    assert (
        _parse_whitelist_entry("http://localhost:11434"),
        _parse_whitelist_entry("http://[2001:db8::1]:8080"),
        _parse_whitelist_entry("[2001:db8::1]:8080"),
        _parse_whitelist_entry("[2001:db8::1]"),
        _parse_whitelist_entry("2606:4700::1"),
        _parse_whitelist_entry("fd00:ec2::254"),
        _parse_whitelist_entry("2606:4700::/48"),
        _parse_whitelist_entry("192.168.1.1:8080"),
        _parse_whitelist_entry("example.com:8080"),
        _parse_whitelist_entry("example.com"),
        _parse_whitelist_entry("https://example.com/path"),
        _parse_whitelist_entry("http://example.com"),
        _parse_whitelist_entry("ftp://example.com:2121"),
    ) == (
        ("localhost", 11434),
        ("2001:db8::1", 8080),
        ("2001:db8::1", 8080),
        ("2001:db8::1", 443),
        ("2606:4700::1", 443),
        ("fd00:ec2::254", 443),
        ("2606:4700::/48", 443),
        ("192.168.1.1", 8080),
        ("example.com", 8080),
        ("example.com", 443),
        ("example.com", 443),
        ("example.com", 80),
        ("example.com", 2121),
    )


@pytest.mark.parametrize(
    "entry",
    [
        "",
        "https://",
        "example.com/path",
        "140.82.112.0/20:8443",
        "ftp://example.com",
        "example.com:0",
        "example.com:70000",
        "example.com:https",
        "[2606:4700::1",
    ],
)
def test_a_whitelist_entry_that_cannot_name_one_port_is_refused(entry: str) -> None:
    """An entry is refused, by name, rather than read as some other host or port.

    Without a scheme, a path is how a CIDR with a port (`140.82.112.0/20:8443`) would be misread
    as one address on 443. Another scheme has no default port, and a port must be 1-65535.
    """
    with pytest.raises(ValueError, match=re.escape(f"'{entry}'")):
        _parse_whitelist_entry(entry)


def test_resolve_public_host_ipv6_emits_full_prefix() -> None:
    """Verify _resolve_public_host emits /128 for IPv6 and /32 for IPv4 instead of truncating prefixes."""
    assert (
        _resolve_public_host("2606:4700::1", 443),
        _resolve_public_host("2606:4700::/48", 443),
        _resolve_public_host("93.184.216.34", 443),
    ) == (
        ["2606:4700::1/128"],
        ["2606:4700::/48"],
        ["93.184.216.34/32"],
    )

    # DNS resolution with A and AAAA records
    mock_addrs = [
        (2, 1, 6, "", ("93.184.216.34", 0)),
        (10, 1, 6, "", ("2606:4700::1", 0, 0, 0)),
    ]
    with patch("socket.getaddrinfo", return_value=mock_addrs):
        resolved = _resolve_public_host("example.com", 443)
        assert resolved == ["2606:4700::1/128", "93.184.216.34/32"]

    # Non-public IPv6 must be rejected
    with pytest.raises(ValueError, match="non-public network"):
        _resolve_public_host("fd00::1", 443)
    with pytest.raises(ValueError, match="non-public network"):
        _resolve_public_host("::1", 443)


def test_resolve_local_host_ipv6_emits_full_prefix() -> None:
    """Verify _resolve_local_host emits /128 for private IPv6 and /32 for IPv4."""
    assert (
        _resolve_local_host("fd00::1", 443),
        _resolve_local_host("fd00::/8", 443),
        _resolve_local_host("192.168.1.50", 443),
    ) == (
        ["fd00::1/128"],
        ["fd00::/8"],
        ["192.168.1.50/32"],
    )

    # Link-local IPv6 and metadata forbidden
    with pytest.raises(ValueError, match="forbidden"):
        _resolve_local_host("fe80::1", 443)
    with pytest.raises(ValueError, match="forbidden"):
        _resolve_local_host("169.254.169.254", 443)

    # Public IPv6 forbidden in local whitelist
    with pytest.raises(ValueError, match="must be a private or loopback"):
        _resolve_local_host("2606:4700::1", 443)


def test_sandbox_network_config_ipv6_whitelists() -> None:
    """Verify NetworkPolicy generates correct IPv6 /128 ipBlock CIDRs for public and local modes."""
    public_cfg = SandboxNetworkConfig(**_WHITELIST_POLICIES["public ipv6 and ipv4 addresses"])
    public_policy = public_cfg.to_k8s_network_policy(name="app-sandbox", namespace="sandbox")
    public_blocks = [
        t["ipBlock"]["cidr"]
        for rule in public_policy["spec"]["egress"]
        for t in rule.get("to", [])
        if "ipBlock" in t
    ]
    assert (
        "2606:4700::1/128" in public_blocks,
        "93.184.216.34/32" in public_blocks,
        "2606:4700::1/32" not in public_blocks,
    ) == (True, True, True)

    local_cfg = SandboxNetworkConfig(**_WHITELIST_POLICIES["local ipv6 url and ipv4 address"])
    local_policy = local_cfg.to_k8s_network_policy(name="app-sandbox", namespace="sandbox")
    local_blocks = [
        t["ipBlock"]["cidr"]
        for rule in local_policy["spec"]["egress"]
        for t in rule.get("to", [])
        if "ipBlock" in t
    ]
    assert (
        "fd00::1/128" in local_blocks,
        "192.168.1.50/32" in local_blocks,
        "fd00::1/32" not in local_blocks,
    ) == (True, True, True)


# =============================================================================
# One lookup for each whitelist name, checked by the egress policy (#2431)
# =============================================================================

_LOCAL_NAME = "node1.example.internal"
_LOCAL_ANSWER = "192.0.2.10"
_METADATA_NAME = "metadata.google.internal"
_METADATA_ADDRESS = "169.254.169.254"


@pytest.mark.parametrize(
    ("config", "script"),
    [
        (
            {
                "mode": SandboxNetworkMode.PUBLIC_WHITELIST,
                "public_whitelist": ["example.com", "example.org:8443"],
            },
            {"example.com": [[PUBLIC_ADDRESS]], "example.org": [[PUBLIC_ADDRESS]]},
        ),
        (
            {"mode": SandboxNetworkMode.LOCAL_WHITELIST, "local_whitelist": [_LOCAL_NAME]},
            {_LOCAL_NAME: [[_LOCAL_ANSWER]]},
        ),
    ],
    ids=["public", "local"],
)
def test_the_whitelist_policy_looks_up_each_name_once(
    monkeypatch: pytest.MonkeyPatch, config: dict[str, Any], script: dict[str, list[list[str]]]
) -> None:
    """The whitelist validators look up no name, and the policy looks up each name one time."""
    resolver = scripted_resolver(monkeypatch, script)

    SandboxNetworkConfig(**config).to_k8s_network_policy()

    assert resolver.lookups == dict.fromkeys(script, 1)


# Each row: the whitelist, its one host, what the host answers, the lookups made, and the type of
# the refusal's cause: SSRFBlockedError when the egress policy refuses, None when the builder does.
_BUILDER_REFUSALS: dict[str, tuple[str, str, str, int, type[BaseException] | None]] = {
    "public, a cloud metadata name": (
        "public_whitelist",
        _METADATA_NAME,
        _METADATA_ADDRESS,
        0,
        SSRFBlockedError,
    ),
    "public, a cloud metadata answer": (
        "public_whitelist",
        "example.com",
        _METADATA_ADDRESS,
        1,
        SSRFBlockedError,
    ),
    "public, a private answer": (
        "public_whitelist",
        "example.com",
        _LOCAL_ANSWER,
        1,
        SSRFBlockedError,
    ),
    "public, a loopback answer": (
        "public_whitelist",
        "example.com",
        "127.0.0.1",
        1,
        SSRFBlockedError,
    ),
    "public, a scoped ipv6 answer": (
        "public_whitelist",
        "example.com",
        "2606:4700::1%2",
        1,
        SSRFBlockedError,
    ),
    "local, a cloud metadata name": ("local_whitelist", _METADATA_NAME, _METADATA_ADDRESS, 0, None),
    "local, a cloud metadata answer": (
        "local_whitelist",
        _LOCAL_NAME,
        _METADATA_ADDRESS,
        1,
        SSRFBlockedError,
    ),
    "local, a scoped ipv6 answer": (
        "local_whitelist",
        _LOCAL_NAME,
        "fe80::1%2",
        1,
        SSRFBlockedError,
    ),
    "local, a link-local answer": ("local_whitelist", _LOCAL_NAME, "169.254.1.2", 1, None),
    "local, a public answer": ("local_whitelist", _LOCAL_NAME, PUBLIC_ADDRESS, 1, None),
}


@pytest.mark.parametrize("case", list(_BUILDER_REFUSALS))
def test_the_whitelist_policy_refuses_an_answer_outside_its_level(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Each builder refuses a cloud metadata name, a cloud metadata answer and an answer outside
    its level, and the local builder also refuses a public answer.

    `model_construct` skips the whitelist validators, so the refusal comes from the builder. The
    public builder checks at the public egress level. The local builder checks at the private
    level, then admits only a private or loopback address. The refusal names the host, and also
    the answer when the builder refuses an answer.
    """
    field, host, answer, lookups, cause = _BUILDER_REFUSALS[case]
    resolver = scripted_resolver(monkeypatch, {host: [[answer]]})
    config = SandboxNetworkConfig.model_construct(mode=SandboxNetworkMode(field), **{field: [host]})

    with pytest.raises(SandboxValidationError) as refusal:
        config.to_k8s_network_policy()

    assert (
        refusal.value.exit_code,
        refusal.value.error_code,
        f"'{host}'" in str(refusal.value),
        answer in str(refusal.value),
        type(refusal.value.__cause__) if refusal.value.__cause__ else None,
        resolver.lookups,
    ) == (
        CONST_EXIT_FAILURE,
        "SANDBOX_VALIDATION_ERROR",
        True,
        lookups == 1,
        cause,
        {host: lookups},
    )


@pytest.mark.parametrize(
    ("mode", "field", "host"),
    [
        (SandboxNetworkMode.PUBLIC_WHITELIST, "public_whitelist", "example.com"),
        (SandboxNetworkMode.LOCAL_WHITELIST, "local_whitelist", _LOCAL_NAME),
    ],
    ids=["public", "local"],
)
def test_a_whitelist_name_that_does_not_resolve_is_refused(
    mode: SandboxNetworkMode, field: str, host: str, failed_lookups: list[tuple[str, int]]
) -> None:
    """A name with no answer opens no rule: the builder refuses it, and names it."""
    config = SandboxNetworkConfig(mode=mode, **{field: [host]})

    with pytest.raises(SandboxValidationError) as refusal:
        config.to_k8s_network_policy()

    assert (
        refusal.value.exit_code,
        refusal.value.error_code,
        f"'{host}'" in str(refusal.value),
        [name for name, flags in failed_lookups if not flags & socket.AI_NUMERICHOST],
    ) == (CONST_EXIT_FAILURE, "SANDBOX_VALIDATION_ERROR", True, [host])


def test_network_policy_exits_1_naming_a_whitelist_name_whose_answer_it_refuses(
    cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A public whitelist name that answers a private address gets no policy, and the error names
    the name and its answer. Only the one lookup of the policy builder gives the answer: the
    whitelist validators look up no name."""
    resolver = scripted_resolver(monkeypatch, {"example.com": [[_LOCAL_ANSWER]]})

    res = cli(
        "sandbox",
        "network-policy",
        "--network-mode",
        "public_whitelist",
        "--public-whitelist",
        "example.com",
    )

    assert (
        res.exit_code,
        "'example.com'" in res.output,
        _LOCAL_ANSWER in res.output,
        "NetworkPolicy" in res.stdout,
        resolver.lookups,
    ) == (CONST_EXIT_FAILURE, True, True, False, {"example.com": 1})


# =============================================================================
# Port scoping and the collector lane (#702)
# =============================================================================


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("https url with a port", [(["1.1.1.1/32"], 8443)]),
        ("address with a port", [(["1.1.1.1/32"], 8443)]),
        ("http url", [(["93.184.215.14/32"], 80)]),
        ("bare name", [(["93.184.215.14/32"], 443)]),
        ("bracketed ipv6 with a port", [(["2606:4700::1/128"], 8443)]),
        ("local url with a port", [(["192.0.2.50/32"], 11434)]),
    ],
)
def test_a_whitelist_entry_opens_only_its_own_port(
    case: str, expected: list[tuple[list[str], int]], public_dns: str
) -> None:
    """An entry that asks for one port gets that port, on TCP, and no other."""
    assert (public_dns, _egress_without_dns(_WHITELIST_POLICIES[case])) == (
        "93.184.215.14",
        [_tcp_rule(cidrs, port) for cidrs, port in expected],
    )


def test_two_entries_never_share_a_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each entry's addresses open only that entry's port, never the other entry's."""
    addresses = {"example.com": "93.184.216.34", "example.org": "1.0.0.1"}

    def resolve(host: str, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        if host not in addresses:
            raise socket.gaierror(socket.EAI_NONAME, f"no stub address for {host}")
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (addresses[host], 0))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    assert _egress_without_dns(_WHITELIST_POLICIES["two names, one with a port"]) == [
        _tcp_rule(["93.184.216.34/32"], 8443),
        _tcp_rule(["1.0.0.1/32"], 443),
    ]


@pytest.mark.usefixtures("public_dns")
@pytest.mark.parametrize(
    "entry", ["ftp://example.com", "example.com:0", "example.com:70000", "140.82.112.0/20:8443"]
)
def test_network_policy_exits_1_naming_an_entry_it_cannot_scope_to_a_port(entry: str) -> None:
    """The command prints no policy for an entry it would otherwise misread."""
    res = runner.invoke(
        sandbox_app,
        ["network-policy", "--network-mode", "public_whitelist", "--public-whitelist", entry],
    )
    assert (res.exit_code, entry in res.output, "NetworkPolicy" in res.stdout) == (1, True, False)


@pytest.mark.usefixtures("public_dns")
@pytest.mark.parametrize("case", sorted(_WHITELIST_POLICIES))
def test_every_whitelist_rule_but_the_dns_rule_names_its_ports(case: str) -> None:
    """No whitelist policy these tests build opens every port to an address."""
    rules = _egress_without_dns(_WHITELIST_POLICIES[case])
    assert (bool(rules), all(rule.get("ports") for rule in rules)) == (True, True)


@pytest.mark.usefixtures("public_dns")
@pytest.mark.parametrize("case", sorted(_WHITELIST_POLICIES))
def test_every_whitelist_rule_names_a_destination(case: str) -> None:
    """No rule has an empty or missing `to`, which would allow every destination (#1174)."""
    policy = SandboxNetworkConfig(**_WHITELIST_POLICIES[case]).to_k8s_network_policy()
    assert [rule for rule in policy["spec"]["egress"] if not rule.get("to")] == []


_COLLECTOR_RULE: dict[str, Any] = {
    "to": [
        {
            "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "otel"}},
            "podSelector": {
                "matchLabels": {
                    "app.kubernetes.io/name": "opentelemetry-collector",
                    "app.kubernetes.io/instance": "otel-collector",
                }
            },
        }
    ],
    "ports": [{"protocol": "TCP", "port": 4317}, {"protocol": "TCP", "port": 4318}],
}
_MODE_POLICIES: dict[str, dict[str, Any]] = {
    "isolated": {"mode": SandboxNetworkMode.ISOLATED},
    "sandbox_namespace": {"mode": SandboxNetworkMode.SANDBOX_NAMESPACE},
    "public_whitelist": _WHITELIST_POLICIES["bare name"],
    "local_whitelist": _WHITELIST_POLICIES["local url with a port"],
    "bridge": {"mode": SandboxNetworkMode.BRIDGE},
}
_COLLECTOR_LANE_MODES = ("sandbox_namespace", "public_whitelist", "local_whitelist")


def _selects_otel(rule: dict[str, Any]) -> bool:
    """Whether an egress rule has a peer in the collector's namespace."""
    return any(
        peer.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name")
        == "otel"
        for peer in rule.get("to", [])
    )


@pytest.mark.usefixtures("public_dns")
@pytest.mark.parametrize("mode", _COLLECTOR_LANE_MODES)
def test_the_collector_lane_is_one_rule_to_the_collector_pods_on_the_otlp_ports(mode: str) -> None:
    """The lane selects the collector by namespace and pod labels together, never Tempo or an IP."""
    egress = _egress_without_dns(_MODE_POLICIES[mode], allow_collector=True)
    assert [rule for rule in egress if _selects_otel(rule)] == [_COLLECTOR_RULE]


@pytest.mark.parametrize("mode", ["isolated", "bridge"])
def test_the_collector_lane_is_refused_in_a_mode_it_does_not_apply_to(mode: str) -> None:
    """Isolated means no egress, and bridge already has all of it; the error names the modes."""
    res = runner.invoke(
        sandbox_app, ["network-policy", "--network-mode", mode, "--allow-collector"]
    )
    named = tuple(lane_mode in res.output for lane_mode in _COLLECTOR_LANE_MODES)
    assert (res.exit_code, named) == (1, (True, True, True))


@pytest.mark.usefixtures("public_dns")
@pytest.mark.parametrize("mode", sorted(_MODE_POLICIES))
def test_without_the_flag_no_rule_selects_the_collector_namespace(mode: str) -> None:
    """The collector lane is opt-in in every mode."""
    egress = SandboxNetworkConfig(**_MODE_POLICIES[mode]).to_k8s_network_policy()["spec"]["egress"]
    assert [rule for rule in egress if _selects_otel(rule)] == []


@pytest.mark.usefixtures("public_dns")
@pytest.mark.parametrize(
    ("mode", "allow_collector"),
    [(mode, False) for mode in sorted(_MODE_POLICIES)]
    + [(mode, True) for mode in _COLLECTOR_LANE_MODES],
)
def test_no_policy_opens_the_cache_port(mode: str, allow_collector: bool) -> None:
    """There is no lane to a Valkey on 6379, with or without the collector lane."""
    policy = SandboxNetworkConfig(**_MODE_POLICIES[mode]).to_k8s_network_policy(
        allow_collector=allow_collector
    )
    ports = {port["port"] for rule in policy["spec"]["egress"] for port in rule.get("ports", [])}
    assert 6379 not in ports


def test_the_mcp_tool_asks_for_the_collector_lane_only_when_told_to() -> None:
    """`sandbox_network_policy(allow_collector=True)` adds the flag to the command it runs."""
    from devops_cli.ai.mcp.server import sandbox_network_policy

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="policy") as run_command:
        sandbox_network_policy(network_mode="sandbox_namespace", allow_collector=True)
        sandbox_network_policy(network_mode="sandbox_namespace")
    base = [
        "uv",
        "run",
        "devops",
        "sandbox",
        "network-policy",
        "--network-mode",
        "sandbox_namespace",
        "--name",
        "app-sandbox",
        "--namespace",
        "sandbox",
    ]
    assert [call.args[0] for call in run_command.call_args_list] == [
        [*base, "--allow-collector"],
        base,
    ]
