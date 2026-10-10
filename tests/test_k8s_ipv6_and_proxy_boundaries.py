"""Tests for IPv6 URL bracketing, k8s:// service proxy boundaries, and probe protocols.

Verifies #1111:
- Service URLs bracket IPv6 addresses across networking, service, collector, and probe.
- Proxy URLs reject dot segments, path escapes, and invalid identifiers with ServiceAddressError.
- Proxy URL target resolution and Qdrant base/prefix split preserve cluster paths and raw prefixes.
- Probe dispatches over HTTPS for HTTPS targets, preserves paths, and brackets IPv6.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s import app as k8s_app
from devops_cli.commands.k8s.networking import (
    _configure_infra_stack_urls,
    _dry_run_preview,
    _extract_service_ingress_or_nodeport,
    _resolve_accessible_url,
    _resolve_k8s_node_port_url,
    _search_ingress_hosts,
    port_forward,
)
from devops_cli.config.settings import Settings
from devops_cli.k8s.service import KubernetesService
from devops_cli.k8s.service_http import _transport_key, get_json
from devops_cli.k8s.service_proxy import (
    ServiceAddressError,
    ServiceRef,
    parse_service_url,
    resolve_proxy_connection,
    resolve_proxy_target,
)
from devops_cli.sandbox.models import ProbeProtocol
from devops_cli.sandbox.probe import _dispatch_probes_for_port, _parse_target_endpoint
from devops_cli.telemetry.collector import collector_endpoint

runner = CliRunner()


# =============================================================================
# 1. IPv6 Builders & Bracketing Table Test
# =============================================================================


def test_ipv6_builders_and_bracketing() -> None:
    """Verify IPv6 addresses produce bracketed URLs across all discovery and probe sites."""
    # 1. networking.py node address via _resolve_k8s_node_port_url
    node_res = MagicMock(
        returncode=0,
        stdout=json.dumps(
            {
                "items": [
                    {
                        "status": {
                            "conditions": [{"type": "Ready", "status": "True"}],
                            "addresses": [{"type": "InternalIP", "address": "2001:db8::1"}],
                        }
                    }
                ]
            }
        ),
    )
    with patch("devops_cli.commands.k8s.networking.runtime.run_subprocess", return_value=node_res):
        node_url = _resolve_k8s_node_port_url([], 30080)

    # 2. networking.py LoadBalancer ingress via _extract_service_ingress_or_nodeport
    lb_svc_data = {
        "spec": {"ports": [{"port": 9090}]},
        "status": {"loadBalancer": {"ingress": [{"ip": "2001:db8::1"}]}},
    }
    lb_url = _extract_service_ingress_or_nodeport(lb_svc_data, [])

    # 3. k8s/service.py list_nodes node address and LoadBalancer ingress
    mgr = KubernetesService()
    mgr._core_v1 = MagicMock()
    mock_node = MagicMock()
    mock_node.status.addresses = [MagicMock(type="InternalIP", address="2001:db8::1")]
    mgr.list_nodes = MagicMock(return_value=[mock_node])  # type: ignore[method-assign]
    mgr.load_config = MagicMock(return_value=True)  # type: ignore[method-assign]

    mock_svc = MagicMock()
    mock_svc.status.load_balancer.ingress = [MagicMock(ip="2001:db8::1", hostname=None)]
    mock_svc.spec.ports = [MagicMock(port=9090, node_port=30080)]
    mgr._core_v1.read_namespaced_service.return_value = mock_svc
    k8s_lb_url = mgr.resolve_service_endpoint("prom", "monitoring")

    mock_svc_nodeport = MagicMock()
    mock_svc_nodeport.status.load_balancer.ingress = []
    mock_svc_nodeport.spec.ports = [MagicMock(port=9090, node_port=30080)]
    mgr._core_v1.read_namespaced_service.return_value = mock_svc_nodeport
    k8s_np_url = mgr.resolve_service_endpoint("prom", "monitoring")

    # 4. telemetry/collector.py endpoint
    with patch(
        "devops_cli.telemetry.collector.node_port_address", return_value=("2001:db8::1", 30080)
    ):
        collector_url = collector_endpoint(None, "otel", "collector")

    # 5. Ingress host builder in networking.py
    ingress_url = _search_ingress_hosts(
        [("monitoring:grafana", ["2001:db8::1"])], "grafana", preferred_domain=None
    )

    assert (
        node_url,
        lb_url,
        k8s_lb_url,
        k8s_np_url,
        collector_url,
        ingress_url,
    ) == (
        "http://[2001:db8::1]:30080",
        "http://[2001:db8::1]:9090",
        "http://[2001:db8::1]:9090",
        "http://[2001:db8::1]:30080",
        "http://[2001:db8::1]:30080",
        "https://[2001:db8::1]",
    )


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


def test_jaeger_to_otel_endpoint_conversion() -> None:
    """Verify Jaeger URL with userinfo and query string yields clean otel.endpoint."""
    settings = Settings()
    configured: dict[str, str] = {}
    jaeger_raw = "http://user:pass@[2001:db8::2]:16686/?x=1"

    with (
        patch(
            "devops_cli.commands.k8s.networking._detect_service_url",
            side_effect=lambda svc, ns, context=None: jaeger_raw if svc == "jaeger" else None,
        ),
        patch(
            "devops_cli.commands.k8s.networking._resolve_accessible_url",
            side_effect=lambda raw, **kw: raw,
        ),
    ):
        _configure_infra_stack_urls(None, settings, configured)

    assert (
        configured.get("jaeger.url"),
        configured.get("otel.endpoint"),
    ) == (
        jaeger_raw,
        "http://[2001:db8::2]:4318",
    )


def test_dry_run_preview_matches_service_ref_describe() -> None:
    """Verify proxy-mode dry-run preview exactly matches ServiceRef.describe()."""
    preview = _dry_run_preview(["infra", "llm"], "proxy")
    for _key, addr in preview.items():
        ref = parse_service_url(addr)
        assert ref.describe() == addr


# =============================================================================
# 2. Port-forward message formatting & error safety
# =============================================================================


def test_port_forward_message_formatting() -> None:
    """Verify port-forward messages handle IPv6 and lists without raising."""
    cases = [
        ("::1", "http://[::1]:8080"),
        ("0.0.0.0", "http://0.0.0.0:8080"),  # nosec B104  # formats the bind-all address
        ("localhost,::1", "localhost,::1:8080"),
    ]
    for addr, expected_target in cases:
        mock_proc = MagicMock(pid=12345)
        saved: list[Any] = []
        mock_mgr = MagicMock()
        mock_mgr.load_forwards.return_value = []
        mock_mgr.locked.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        mock_mgr.save_forwards.side_effect = saved.extend

        with (
            patch(
                "devops_cli.commands.k8s.networking.runtime._cluster_reachable", return_value=True
            ),
            patch("time.sleep"),
            patch("subprocess.Popen", return_value=mock_proc),
            patch("devops_cli.k8s.port_forward_daemon.process_start_ticks", return_value=100),
            patch("devops_cli.k8s.port_forward_daemon.get_daemon_manager", return_value=mock_mgr),
            patch("devops_cli.commands.k8s.networking.print_success") as mock_print,
        ):
            port_forward(stack="infra", argocd_port=8080, address=addr)
            all_printed = " ".join(call[0][0] for call in mock_print.call_args_list)
            assert (expected_target in all_printed, len(saved) > 0) == (True, True)


# =============================================================================
# 3. configure-urls on IPv6 Cluster & Fallback
# =============================================================================


def test_configure_urls_on_ipv6_cluster_and_fallbacks() -> None:
    """Verify configure-urls handles IPv6 NodePort and LoadBalancer fallbacks."""
    # 1. Reachable IPv6 node
    with patch("socket.create_connection") as mock_conn:

        def mock_connect(addr_tuple: tuple[str, int], timeout: float = 1.0) -> Any:
            host, _port = addr_tuple
            if host in ("localhost", "127.0.0.1", "::1"):
                raise OSError("Connection refused")
            return MagicMock()

        mock_conn.side_effect = mock_connect

        assert (
            _resolve_accessible_url("http://[2001:db8::1]:30080", preferred_localhost_ports=[8080]),
            _resolve_accessible_url("http://[2001:db8::1]:9090", preferred_localhost_ports=[9090]),
        ) == (
            "http://[2001:db8::1]:30080",
            "http://[2001:db8::1]:9090",
        )

    # 2. Unreachable IPv6 node falls back to loopback
    with patch("socket.create_connection", side_effect=OSError("Refused")):
        assert (
            _resolve_accessible_url("http://[2001:db8::1]:30080", preferred_localhost_ports=[8080]),
            _resolve_accessible_url("http://2001:db8::1:30080", preferred_localhost_ports=[8080]),
            _resolve_accessible_url("http://[2001:db8::1]:80", preferred_localhost_ports=[80]),
        ) == (
            "http://localhost:30080",
            "http://localhost:30080",
            "http://localhost:80",
        )


# =============================================================================
# 4. Proxy URL Resolution, Paths, and Boundaries
# =============================================================================


def test_proxy_target_resolution_and_path_prefix() -> None:
    """Verify resolve_proxy_target and resolve_proxy_connection preserve API server paths."""
    mock_config = MagicMock()
    mock_config.host = "https://example.com/k8s/clusters/c-1"
    mock_config.api_key = {}
    mock_config.api_key_prefix = {}
    mock_config.ssl_ca_cert = None
    mock_config.cert_file = None
    mock_config.key_file = None
    mock_config.verify_ssl = False

    ref = ServiceRef(
        namespace="monitoring",
        service="prometheus",
        port="9090",
        path="api/v1/query",
        query="query=up",
    )

    with patch("devops_cli.k8s.service_proxy._kube_configuration", return_value=mock_config):
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
        with pytest.raises(ServiceAddressError):
            ServiceRef(namespace="monitoring", service="prometheus", port="9090", path=bad_path)

        valid_ref = ServiceRef(namespace="monitoring", service="prometheus", port="9090")
        with pytest.raises(ServiceAddressError):
            valid_ref.proxy_path(bad_path)

        with pytest.raises(ServiceAddressError):
            get_json("k8s://monitoring/prometheus:9090", path=bad_path)

        with pytest.raises(ServiceAddressError):
            get_json("https://example.com", path=bad_path)

    # Invalid identifiers
    for bad_id, label in (
        ("..", "namespace"),
        ("..", "service"),
        ("9090?", "port"),
        ("9090/../../secrets/foo?", "port"),
    ):
        with pytest.raises(ServiceAddressError):
            ServiceRef(
                namespace=bad_id if label == "namespace" else "monitoring",
                service=bad_id if label == "service" else "prometheus",
                port=bad_id if label == "port" else "9090",
            )


def test_service_url_cli_command_refuses_invalid_identifier_with_exit_1() -> None:
    """devops k8s service-url .. -n .. prints the error and exits 1 with no traceback."""
    res = runner.invoke(k8s_app, ["service-url", "..", "-n", ".."])
    assert res.exit_code == 1
    assert res.exception is not None
    assert isinstance(res.exception, SystemExit)


def test_transport_key_unification() -> None:
    """_transport_key gives identical key across casing, default ports, and userinfo."""
    urls = (
        "https://example.com/a",
        "https://EXAMPLE.com:443/b",
        "https://user:password@example.com/c",
    )
    keys = {_transport_key(u) for u in urls}
    assert len(keys) == 1
    assert "example.com" in next(iter(keys))


# =============================================================================
# 5. Probe Target, Paths, and Protocols
# =============================================================================


def test_probe_https_scheme_and_paths() -> None:
    """Verify HTTPS targets are probed over HTTPS and probe paths preserve relative semantics."""
    collected: list[Any] = []
    with (
        patch("devops_cli.sandbox.probe.probe_tcp") as mock_tcp,
        patch("devops_cli.sandbox.probe.probe_http") as mock_http,
        patch("devops_cli.sandbox.probe.probe_openapi", return_value=[]) as mock_openapi,
    ):
        origin_https = _parse_target_endpoint("https://example.com:8443")
        _dispatch_probes_for_port(
            origin=origin_https,
            protocols=[ProbeProtocol.TCP, ProbeProtocol.HTTP, ProbeProtocol.OPENAPI],
            http_paths=[
                "health",
                "/health",
                "api?x=1",
                "foo:bar",
                "//other.example.com/x",
                "http://other.example.com/x",
            ],
            expected_statuses=None,
            regex=None,
            timeout=5.0,
            latency_budget_ms=None,
            collector=collected,
        )

        mock_tcp.assert_called_once_with("example.com", 8443, timeout=5.0)
        mock_openapi.assert_called_once_with("https://example.com:8443", timeout=5.0)

        http_calls = [call[0][0] for call in mock_http.call_args_list]
        assert (
            http_calls[0],
            http_calls[1],
            http_calls[2],
            http_calls[3],
            http_calls[4],
        ) == (
            "https://example.com:8443/health",
            "https://example.com:8443/health",
            "https://example.com:8443/api?x=1",
            "https://example.com:8443/foo:bar",
            "https://example.com:8443/other.example.com/x",
        )
        assert http_calls[5].startswith("https://example.com:8443/")


def test_probe_ipv6_target_url_construction() -> None:
    """Verify IPv6 probe targets build bracketed URLs."""
    collected: list[Any] = []
    with (
        patch("devops_cli.sandbox.probe.probe_tcp"),
        patch("devops_cli.sandbox.probe.probe_http") as mock_http,
        patch("devops_cli.sandbox.probe.probe_openapi", return_value=[]) as mock_openapi,
    ):
        origin_v6 = _parse_target_endpoint("[2001:db8::1]:8080")
        _dispatch_probes_for_port(
            origin=origin_v6,
            protocols=[ProbeProtocol.HTTP, ProbeProtocol.OPENAPI],
            http_paths=["health"],
            expected_statuses=None,
            regex=None,
            timeout=5.0,
            latency_budget_ms=None,
            collector=collected,
        )

        assert (
            mock_http.call_args[0][0],
            mock_openapi.call_args[0][0],
        ) == (
            "http://[2001:db8::1]:8080/health",
            "http://[2001:db8::1]:8080",
        )
