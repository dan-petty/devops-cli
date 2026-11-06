"""Tests for IPv6 URL bracketing, k8s:// service proxy boundaries, and probe protocols.

Verifies #1111:
- Service URLs bracket IPv6 addresses across networking, service, collector, and probe.
- Proxy URLs reject dot segments, path escapes, and invalid identifiers with ServiceAddressError.
- Proxy URL target resolution and Qdrant base/prefix split preserve cluster paths and raw prefixes.
- Probe dispatches over HTTPS for HTTPS targets, preserves paths, and brackets IPv6.
"""

from __future__ import annotations

import json
import os
import re
from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx2
import pytest

from devops_cli.k8s.port_forward_daemon import get_daemon_manager
from devops_cli.k8s.service import KubernetesService
from devops_cli.k8s.service_http import get_json, transport_key
from devops_cli.k8s.service_proxy import (
    ServiceAddressError,
    ServiceRef,
    parse_service_url,
    reset_configuration_cache,
    resolve_proxy_connection,
    resolve_proxy_target,
)
from devops_cli.sandbox.models import ProbeProtocol
from devops_cli.sandbox.probe import run_sandbox_probes
from devops_cli.telemetry.collector import collector_endpoint
from tests.support.fakes.http import WebFake
from tests.support.fakes.kubernetes import FakeCluster, node, service
from tests.support.fakes.process import ProcessAnswer, ProcessFake

# =============================================================================
# 1. IPv6 Builders & Bracketing
# =============================================================================


def _reachable_unless_loopback(addr_tuple: tuple[str, int], timeout: float = 1.0) -> Any:
    """A `socket.create_connection` that reaches every host but the loopback names."""
    host, _port = addr_tuple
    if host in ("localhost", "127.0.0.1", "::1"):
        raise OSError("Connection refused")
    return nullcontext()


def _configured_url(key: str) -> str | None:
    """The URL that `configure-urls` saved for a settings key."""
    from devops_cli.config.settings import dotted_get, load_settings, reset_settings_cache

    reset_settings_cache()
    return dotted_get(load_settings(), key)


def _answer_kubectl_service(process_fake: ProcessFake, name: str, svc: dict[str, Any]) -> None:
    """Answer `kubectl get svc <name> -o json` with `svc`, as the fallback of a cluster that the
    native client cannot resolve reads it."""
    process_fake.answer(
        lambda call: call.argv[:4] == ("kubectl", "get", "svc", name),
        ProcessAnswer(stdout=json.dumps(svc)),
    )


def test_kubectl_fallback_brackets_a_ipv6_load_balancer_address(
    cli: Any, cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """A LoadBalancer ingress with an IPv6 address becomes a bracketed `grafana.url`."""
    _answer_kubectl_service(
        process_fake,
        "grafana",
        {
            "spec": {"ports": [{"port": 9090}]},
            "status": {"loadBalancer": {"ingress": [{"ip": "2001:db8::1"}]}},
        },
    )

    with patch("socket.create_connection", side_effect=_reachable_unless_loopback):
        result = cli(["k8s", "configure-urls", "--stack", "infra"])

    assert (result.exit_code, _configured_url("grafana.url")) == (0, "http://[2001:db8::1]:9090")


def test_kubectl_fallback_brackets_a_ipv6_node_address(
    cli: Any, cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """A NodePort service on a node with an IPv6 address becomes a bracketed `grafana.url`."""
    _answer_kubectl_service(
        process_fake,
        "grafana",
        {"spec": {"ports": [{"port": 9090, "nodePort": 30080}]}, "status": {}},
    )
    nodes = {
        "items": [
            {
                "status": {
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "addresses": [{"type": "InternalIP", "address": "2001:db8::1"}],
                }
            }
        ]
    }
    process_fake.answer(
        lambda call: call.argv[:3] == ("kubectl", "get", "nodes"),
        ProcessAnswer(stdout=json.dumps(nodes)),
    )

    with patch("socket.create_connection", side_effect=_reachable_unless_loopback):
        result = cli(["k8s", "configure-urls", "--stack", "infra"])

    assert (result.exit_code, _configured_url("grafana.url")) == (0, "http://[2001:db8::1]:30080")


def test_native_service_endpoint_brackets_ipv6() -> None:
    """KubernetesService brackets a LoadBalancer address and a node address in an endpoint."""
    mgr = KubernetesService(FakeCluster(contexts=("ipv6",), current="ipv6"))
    fake_core = mgr.core_api("ipv6")
    fake_core.answers["list_node"] = [node("node-a", addresses={"InternalIP": "2001:db8::1"})]
    fake_core.answers["list_namespaced_service"] = [
        service("prom", "monitoring", port=9090, node_port=30080, load_balancer="2001:db8::1")
    ]
    k8s_lb_url = mgr.resolve_service_endpoint("prom", "monitoring", context="ipv6")

    fake_core.answers["list_namespaced_service"] = [
        service("prom", "monitoring", port=9090, node_port=30080)
    ]
    k8s_np_url = mgr.resolve_service_endpoint("prom", "monitoring", context="ipv6")

    assert (k8s_lb_url, k8s_np_url) == ("http://[2001:db8::1]:9090", "http://[2001:db8::1]:30080")


def test_collector_endpoint_brackets_an_ipv6_cluster_host(process_fake: ProcessFake) -> None:
    """The collector endpoint takes the IPv6 host of the API server and brackets it."""
    svc = {"spec": {"type": "NodePort", "ports": [{"port": 4318, "nodePort": 30080}]}}
    process_fake.answer(lambda call: "service" in call.argv, ProcessAnswer(stdout=json.dumps(svc)))
    process_fake.answer(
        lambda call: "config" in call.argv, ProcessAnswer(stdout="https://[2001:db8::1]:6443")
    )

    assert collector_endpoint(None, "otel", "collector") == "http://[2001:db8::1]:30080"


def test_fqdn_addressing_brackets_an_ipv6_ingress_host(
    cli: Any, cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """An Ingress whose host is an IPv6 address becomes a bracketed `https` URL."""
    ingress = {
        "items": [
            {
                "metadata": {"namespace": "monitoring"},
                "spec": {
                    "rules": [
                        {
                            "host": "2001:db8::1",
                            "http": {"paths": [{"backend": {"service": {"name": "grafana"}}}]},
                        }
                    ]
                },
            }
        ]
    }
    process_fake.answer(
        lambda call: call.argv[:3] == ("kubectl", "get", "ingress"),
        ProcessAnswer(stdout=json.dumps(ingress)),
    )

    result = cli(["k8s", "configure-urls", "--stack", "infra", "--addressing", "fqdn"])

    assert (result.exit_code, _configured_url("grafana.url")) == (0, "https://[2001:db8::1]")


def test_special_ipv6_and_scoped_address_parsing() -> None:
    """Verify ::ffff:192.0.2.1 and fe80::1%eth0 bracket and round-trip cleanly."""
    for raw in ("::ffff:192.0.2.1", "fe80::1%eth0"):
        url_str = str(httpx2.URL(scheme="http", host=raw, port=8080))
        assert url_str == f"http://[{raw}]:8080"
        parsed_split = urlsplit(url_str)
        parsed_httpx = httpx2.URL(url_str)
        assert (
            parsed_split.hostname,
            parsed_split.port,
            parsed_httpx.host,
            parsed_httpx.port,
        ) == (
            raw,
            8080,
            raw,
            8080,
        )


def test_tempo_to_otel_endpoint_conversion(
    cli: Any, cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """A Tempo service at an IPv6 address yields `tempo.url` and a matching `otel.endpoint`."""
    cluster.core.answers["list_namespaced_service"] = [
        service("tempo", "otel", port=3200, load_balancer="2001:db8::2")
    ]

    with patch("socket.create_connection", side_effect=_reachable_unless_loopback):
        result = cli(["k8s", "configure-urls", "--stack", "infra"])

    assert (
        result.exit_code,
        _configured_url("tempo.url"),
        "http://[2001:db8::2]:4318" in result.output,
    ) == (0, "http://[2001:db8::2]:3200", True)


def test_dry_run_preview_matches_service_ref_describe(cli: Any) -> None:
    """Verify proxy-mode dry-run preview exactly matches ServiceRef.describe()."""
    result = cli(["k8s", "configure-urls", "--stack", "all", "--addressing", "proxy", "--dry-run"])

    addresses = re.findall(r"k8s://[\w.:/-]+", result.output)
    assert (result.exit_code, len(addresses) > 0) == (0, True)
    for addr in addresses:
        assert parse_service_url(addr).describe() == addr


# =============================================================================
# 2. Port-forward message formatting & error safety
# =============================================================================


@pytest.mark.parametrize(
    ("addr", "expected_target"),
    [
        ("::1", "http://[::1]:8080"),
        ("0.0.0.0", "http://0.0.0.0:8080"),  # nosec B104  # formats the bind-all address
        ("localhost,::1", "localhost,::1:8080"),
    ],
)
def test_port_forward_message_formatting(
    addr: str, expected_target: str, cli: Any, cluster: FakeCluster
) -> None:
    """Verify port-forward messages handle IPv6 and lists without raising."""
    with (
        patch("time.sleep"),
        patch("subprocess.Popen", return_value=SimpleNamespace(pid=os.getpid())),
    ):
        result = cli(
            ["k8s", "port-forward", "--stack", "infra", "--argocd-port", "8080", "--address", addr]
        )

    assert (result.exit_code, expected_target in result.output) == (0, True)
    assert len(get_daemon_manager().load_forwards()) > 0


# =============================================================================
# 3. configure-urls on IPv6 Cluster & Fallback
# =============================================================================


def test_configure_urls_keeps_a_reachable_ipv6_node(
    cli: Any, cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """A LoadBalancer at a reachable IPv6 address stays the configured URL."""
    cluster.core.answers["list_namespaced_service"] = [
        service("grafana", "monitoring", port=9090, load_balancer="2001:db8::1")
    ]

    with patch("socket.create_connection", side_effect=_reachable_unless_loopback):
        result = cli(["k8s", "configure-urls", "--stack", "infra"])

    assert (result.exit_code, _configured_url("grafana.url")) == (0, "http://[2001:db8::1]:9090")


def test_configure_urls_falls_back_to_loopback_for_an_unreachable_ipv6_node(
    cli: Any, cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """A NodePort at an unreachable IPv6 address falls back to localhost and the same port."""
    cluster.core.answers["list_node"] = [node("node-a", addresses={"InternalIP": "2001:db8::1"})]
    cluster.core.answers["list_namespaced_service"] = [
        service("grafana", "monitoring", port=9090, node_port=30080)
    ]

    with patch("socket.create_connection", side_effect=OSError("Refused")):
        result = cli(["k8s", "configure-urls", "--stack", "infra"])

    assert (result.exit_code, _configured_url("grafana.url")) == (0, "http://localhost:30080")


# =============================================================================
# 4. Proxy URL Resolution, Paths, and Boundaries
# =============================================================================


def test_proxy_target_resolution_and_path_prefix(cluster: FakeCluster) -> None:
    """Verify resolve_proxy_target and resolve_proxy_connection preserve API server paths."""
    cluster.configuration = SimpleNamespace(
        host="https://example.com/k8s/clusters/c-1",
        api_key={},
        api_key_prefix={},
        ssl_ca_cert=None,
        cert_file=None,
        key_file=None,
        verify_ssl=False,
    )
    reset_configuration_cache()

    ref = ServiceRef(
        namespace="monitoring",
        service="prometheus",
        port="9090",
        path="api/v1/query",
        query="query=up",
    )

    target = resolve_proxy_target(ref)
    conn = resolve_proxy_connection(ref)

    assert (
        target.url,
        conn.base_url,
        conn.prefix,
    ) == (
        "https://example.com/k8s/clusters/c-1/api/v1/namespaces/monitoring/services/prometheus:9090/proxy/api/v1/query?query=up",
        "https://example.com",
        "k8s/clusters/c-1/api/v1/namespaces/monitoring/services/prometheus:9090/proxy",
    )


def test_proxy_path_suffixes_and_encoded_segments() -> None:
    """Verify raw encoded characters (%2F) and valid suffixes are preserved."""
    ref = ServiceRef(
        namespace="argocd",
        service="argocd-server",
        port="443",
        tls=True,
    )
    assert (
        ref.proxy_path("a%2Fb"),
        ref.proxy_path("foo:bar"),
        ref.proxy_path(".hidden"),
        ref.proxy_path("a..b"),
    ) == (
        "/api/v1/namespaces/argocd/services/https:argocd-server:443/proxy/a%2Fb",
        "/api/v1/namespaces/argocd/services/https:argocd-server:443/proxy/foo:bar",
        "/api/v1/namespaces/argocd/services/https:argocd-server:443/proxy/.hidden",
        "/api/v1/namespaces/argocd/services/https:argocd-server:443/proxy/a..b",
    )


def test_proxy_boundaries_refuse_dot_segments_and_escapes() -> None:
    """Verify ServiceRef, proxy_path, and get_json refuse dot segments and invalid identifiers."""
    refused_paths = (
        "../../../secrets/foo",
        "/../grafana:80/api/health",
        "a/../b",
        ".",
        "./x",
        "%2e%2e/x",
        ".%2e/x",
        "%2E/x",
    )
    for bad_path in refused_paths:
        with pytest.raises(ServiceAddressError) as raised:
            ServiceRef(namespace="monitoring", service="prometheus", port="9090", path=bad_path)
        assert raised.value.error_code == "K8S_ERROR"

        valid_ref = ServiceRef(namespace="monitoring", service="prometheus", port="9090")
        with pytest.raises(ServiceAddressError) as raised:
            valid_ref.proxy_path(bad_path)
        assert raised.value.error_code == "K8S_ERROR"

        with pytest.raises(ServiceAddressError) as raised:
            get_json("k8s://monitoring/prometheus:9090", path=bad_path)
        assert raised.value.error_code == "K8S_ERROR"

        with pytest.raises(ServiceAddressError) as raised:
            get_json("https://example.com", path=bad_path)
        assert raised.value.error_code == "K8S_ERROR"

    # Invalid identifiers
    for bad_id, label in (
        ("..", "namespace"),
        ("..", "service"),
        ("9090?", "port"),
        ("9090/../../secrets/foo?", "port"),
    ):
        with pytest.raises(ServiceAddressError) as raised:
            ServiceRef(
                namespace=bad_id if label == "namespace" else "monitoring",
                service=bad_id if label == "service" else "prometheus",
                port=bad_id if label == "port" else "9090",
            )
        assert raised.value.error_code == "K8S_ERROR"


def test_service_url_cli_command_refuses_invalid_identifier_with_exit_1(cli: Any) -> None:
    """devops k8s service-url .. -n .. prints the error and exits 1 with no traceback."""
    res = cli(["k8s", "service-url", "..", "-n", ".."])
    assert res.exit_code == 1
    assert res.exception is not None
    assert isinstance(res.exception, SystemExit)


def test_transport_key_unification() -> None:
    """transport_key gives identical key across casing, default ports, and userinfo."""
    urls = (
        "https://example.com/a",
        "https://EXAMPLE.com:443/b",
        "https://user:password@example.com/c",
    )
    keys = {transport_key(u) for u in urls}
    assert len(keys) == 1
    assert "example.com" in next(iter(keys))


# =============================================================================
# 5. Probe Target, Paths, and Protocols
# =============================================================================


def test_probe_https_scheme_and_paths(web: WebFake) -> None:
    """Verify HTTPS targets are probed over HTTPS and probe paths preserve relative semantics."""
    run_sandbox_probes(
        "https://example.com:8443",
        protocols=[ProbeProtocol.HTTP, ProbeProtocol.OPENAPI],
        http_paths=[
            "health",
            "/health",
            "api?x=1",
            "foo:bar",
            "//other.example.com/x",
            "http://other.example.com/x",
        ],
        timeout=5.0,
    )

    requested = web.requested
    assert requested[:5] == [
        "https://example.com:8443/health",
        "https://example.com:8443/health",
        "https://example.com:8443/api?x=1",
        "https://example.com:8443/foo:bar",
        "https://example.com:8443/other.example.com/x",
    ]
    assert requested[5].startswith("https://example.com:8443/")
    assert requested[-1] == "https://example.com:8443/openapi.json"


def test_probe_ipv6_target_url_construction(web: WebFake) -> None:
    """Verify IPv6 probe targets build bracketed URLs."""
    run_sandbox_probes(
        "[2001:db8::1]:8080",
        protocols=[ProbeProtocol.HTTP, ProbeProtocol.OPENAPI],
        http_paths=["health"],
        timeout=5.0,
    )

    assert web.requested == [
        "http://[2001:db8::1]:8080/health",
        "http://[2001:db8::1]:8080/openapi.json",
    ]
