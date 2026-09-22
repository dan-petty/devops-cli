"""Test suite for cluster-native endpoint addressing across discovery and configuration."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app as k8s_app
from devops_cli.k8s.service_proxy import discover_service

runner = CliRunner()


def _port(number: int, name: str = "") -> Any:
    """Build a Service port stub."""
    port = MagicMock()
    port.port = number
    port.name = name
    return port


def _service(name: str, ports: list[Any]) -> Any:
    """Build a Service stub."""
    service = MagicMock()
    service.metadata.name = name
    service.spec.ports = ports
    return service


def _listing(*services: Any) -> Any:
    """Patch KubernetesService so it lists the given services."""
    api = MagicMock()
    api.load_config.return_value = True
    api._core_v1.list_namespaced_service.return_value = MagicMock(items=list(services))
    return patch("devops_cli.k8s.service.KubernetesService.get_instance", return_value=api)


# =============================================================================
# Service Discovery
# =============================================================================


def test_a_chart_renamed_service_is_still_found() -> None:
    """Charts rarely install a service under the bare name an operator thinks in.

    Prometheus ships as `kube-prometheus-kube-prome-prometheus`, so an exact-name lookup
    finds nothing and the endpoint silently falls back to a hand-written localhost URL.
    """
    with _listing(_service("kube-prometheus-kube-prome-prometheus", [_port(9090, "web")])):
        ref = discover_service("monitoring", ("prome-prometheus", "prometheus"), ("9090",))
    assert ref is not None
    assert ref.describe() == "k8s://monitoring/kube-prometheus-kube-prome-prometheus:9090"


def test_the_most_specific_pattern_wins() -> None:
    """Callers order patterns most-specific first, and that order must be honoured.

    A loose `prometheus` would otherwise match the node exporter or the operator.
    """
    with _listing(
        _service("kube-prometheus-prometheus-node-exporter", [_port(9100)]),
        _service("kube-prometheus-kube-prome-prometheus", [_port(9090, "web")]),
    ):
        ref = discover_service("monitoring", ("prome-prometheus", "prometheus"), ("9090",))
    assert ref is not None
    assert ref.service == "kube-prometheus-kube-prome-prometheus"


def test_a_hinted_port_is_preferred_over_the_first() -> None:
    """A Service commonly exposes several; Prometheus publishes a reloader port too."""
    with _listing(_service("prometheus", [_port(8080, "reloader"), _port(9090, "web")])):
        ref = discover_service("monitoring", ("prometheus",), ("9090", "web"))
    assert ref is not None
    assert ref.port == "9090"


def test_a_port_is_matched_by_name_as_well_as_number() -> None:
    """Port numbers vary between installations; names are more stable."""
    with _listing(_service("jaeger", [_port(14268), _port(16686, "http-query")])):
        ref = discover_service("otel", ("jaeger",), ("http-query",))
    assert ref is not None
    assert ref.port == "16686"


def test_the_first_port_is_used_when_no_hint_matches() -> None:
    """A best guess beats refusing to address the service at all."""
    with _listing(_service("grafana", [_port(3000)])):
        ref = discover_service("monitoring", ("grafana",), ("80", "http"))
    assert ref is not None
    assert ref.port == "3000"


def test_a_service_with_no_ports_is_skipped() -> None:
    """An address without a port cannot be proxied."""
    with _listing(_service("headless", [])):
        assert discover_service("monitoring", ("headless",)) is None


def test_no_matching_service_returns_nothing() -> None:
    """A stack component that is not installed is not an error."""
    with _listing(_service("grafana", [_port(80)])):
        assert discover_service("monitoring", ("prometheus",)) is None


def test_an_unreachable_cluster_returns_nothing() -> None:
    """Discovery must not raise when the cluster cannot be contacted."""
    api = MagicMock()
    api.load_config.return_value = False
    with patch("devops_cli.k8s.service.KubernetesService.get_instance", return_value=api):
        assert discover_service("monitoring", ("prometheus",)) is None


def test_a_failed_listing_returns_nothing() -> None:
    """A namespace the credentials cannot read is not a crash."""
    api = MagicMock()
    api.load_config.return_value = True
    api._core_v1.list_namespaced_service.side_effect = RuntimeError("forbidden")
    with patch("devops_cli.k8s.service.KubernetesService.get_instance", return_value=api):
        assert discover_service("monitoring", ("prometheus",)) is None


# =============================================================================
# configure-urls Addressing Mode
# =============================================================================


def test_proxy_mode_records_portable_addresses() -> None:
    """The recorded address carries no host, so it resolves on any cluster."""
    from devops_cli.commands.k8s.networking import _configure_proxy_urls
    from devops_cli.k8s.service_proxy import ServiceRef

    configured: dict[str, str] = {}
    settings = MagicMock()
    with (
        patch(
            "devops_cli.k8s.service_proxy.discover_service",
            return_value=ServiceRef(namespace="monitoring", service="prometheus", port="9090"),
        ),
        patch("devops_cli.config.settings.dotted_set"),
    ):
        _configure_proxy_urls(None, settings, configured, ["infra"])

    assert configured["prometheus.url"] == "k8s://monitoring/prometheus:9090"


def test_proxy_mode_skips_components_that_are_not_installed() -> None:
    """A partial stack configures what exists rather than failing outright."""
    from devops_cli.commands.k8s.networking import _configure_proxy_urls

    configured: dict[str, str] = {}
    with (
        patch("devops_cli.k8s.service_proxy.discover_service", return_value=None),
        patch("devops_cli.config.settings.dotted_set"),
    ):
        _configure_proxy_urls(None, MagicMock(), configured, ["infra", "llm"])

    assert configured == {}


def test_an_unknown_addressing_mode_is_rejected() -> None:
    """A typo must not silently fall back to the cluster-specific default."""
    result = runner.invoke(k8s_app, ["configure-urls", "--addressing", "bogus"])
    # The error is written to stderr, which `output` includes and `stdout` does not.
    assert (result.exit_code, "nodeport, proxy" in result.output) == (2, True)


# =============================================================================
# Telemetry Through Cluster-Native Addressing
# =============================================================================


def test_the_telemetry_provider_accepts_a_service_address() -> None:
    """The dashboard reads Prometheus without a port-forward.

    The provider does not branch on the address form; get_json resolves either, which is
    what lets a configuration move to cluster-native addressing without code changes.
    """
    from devops_cli.ui import data_providers

    address = "k8s://monitoring/prometheus:9090"
    payload = {"data": ["http_requests_total", "up", "go_goroutines", "latency_bucket"]}
    with (
        patch.object(data_providers, "_prometheus_base_url", return_value=address),
        patch("devops_cli.k8s.service_http.get_json", return_value=payload) as fetch,
    ):
        summary = data_providers.fetch_telemetry_status()

    assert (fetch.call_args[0][0], summary.source, summary.counter_count) == (
        address,
        address,
        1,
    )


def test_a_failing_service_address_falls_back_and_names_the_endpoint() -> None:
    """An unreachable cluster service must not look like an absence of metrics."""
    from devops_cli.ui import data_providers

    address = "k8s://monitoring/prometheus:9090"
    with (
        patch.object(data_providers, "_prometheus_base_url", return_value=address),
        patch("devops_cli.k8s.service_http.get_json", side_effect=RuntimeError("403 Forbidden")),
    ):
        summary = data_providers.fetch_telemetry_status()

    assert (address in summary.error_message, summary.source) == (True, "in-process")
