"""Test suite for cluster-native endpoint addressing across discovery and configuration."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app as k8s_app
from devops_cli.k8s.service_proxy import discover_service
from tests.support.fakes.kubernetes import FakeCluster, api_exception, service

runner = CliRunner()


def _listing(cluster: FakeCluster, *services: Any) -> None:
    """Make the fake cluster list the given services in the `monitoring` and `otel` namespaces."""
    cluster.core.answers["list_namespaced_service"] = list(services)


# =============================================================================
# Service Discovery
# =============================================================================


def test_a_chart_renamed_service_is_still_found(cluster: FakeCluster) -> None:
    """Charts rarely install a service under the bare name an operator thinks in.

    Prometheus server ships as `prometheus-server`, so an exact-name lookup
    for `prometheus` finds nothing and the endpoint silently falls back to a hand-written localhost URL.
    """
    _listing(cluster, service("prometheus-server", "monitoring", ports=[(9090, "http")]))
    ref = discover_service("monitoring", ("prometheus-server", "prometheus"), ("9090",))
    assert (ref is not None, ref.describe() if ref else None) == (
        True,
        "k8s://monitoring/prometheus-server:9090",
    )


def test_the_most_specific_pattern_wins(cluster: FakeCluster) -> None:
    """Callers order patterns most-specific first, and that order must be honoured.

    A loose `prometheus` would otherwise match the node exporter or the operator.
    """
    _listing(
        cluster,
        service("prometheus-node-exporter", "monitoring", ports=[(9100, None)]),
        service("prometheus-server", "monitoring", ports=[(9090, "http")]),
    )
    ref = discover_service("monitoring", ("prometheus-server", "prometheus"), ("9090",))
    assert (ref is not None, ref.service if ref else None) == (True, "prometheus-server")


def test_a_hinted_port_is_preferred_over_the_first(cluster: FakeCluster) -> None:
    """A Service commonly exposes several; Prometheus publishes a reloader port too."""
    _listing(
        cluster, service("prometheus", "monitoring", ports=[(8080, "reloader"), (9090, "web")])
    )
    ref = discover_service("monitoring", ("prometheus",), ("9090", "web"))
    assert (ref.port if ref else None) == "9090"


def test_a_port_is_matched_by_name_as_well_as_number(cluster: FakeCluster) -> None:
    """Port numbers vary between installations; names are more stable."""
    _listing(cluster, service("tempo", "otel", ports=[(4317, None), (3200, "prom-metrics")]))
    ref = discover_service("otel", ("tempo",), ("prom-metrics",))
    assert (ref.port if ref else None) == "3200"


def test_the_first_port_is_used_when_no_hint_matches(cluster: FakeCluster) -> None:
    """A best guess beats refusing to address the service at all."""
    _listing(cluster, service("grafana", "monitoring", ports=[(3000, None)]))
    ref = discover_service("monitoring", ("grafana",), ("80", "http"))
    assert (ref.port if ref else None) == "3000"


def test_a_service_with_no_ports_is_skipped(cluster: FakeCluster) -> None:
    """An address without a port cannot be proxied."""
    _listing(cluster, service("headless", "monitoring", ports=[]))
    assert discover_service("monitoring", ("headless",)) is None


def test_no_matching_service_returns_nothing(cluster: FakeCluster) -> None:
    """A stack component that is not installed is not an error."""
    _listing(cluster, service("grafana", "monitoring", ports=[(80, None)]))
    assert discover_service("monitoring", ("prometheus",)) is None


def test_an_unreachable_cluster_returns_nothing(cluster: FakeCluster) -> None:
    """Discovery must not raise when the cluster cannot be contacted."""
    cluster.context_names.clear()
    assert discover_service("monitoring", ("prometheus",)) is None


def test_a_failed_listing_returns_nothing(cluster: FakeCluster) -> None:
    """A namespace the credentials cannot read is not a crash."""
    cluster.core.answers["list_namespaced_service"] = api_exception(403, "Forbidden")
    assert discover_service("monitoring", ("prometheus",)) is None


# =============================================================================
# configure-urls Addressing Mode
# =============================================================================


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


# =============================================================================
# Dry-run preview
# =============================================================================


def test_the_preview_follows_the_requested_addressing_mode() -> None:
    """A fixed block of NodePort URLs was previewed whatever `--addressing` asked for.

    Running `--addressing proxy --dry-run` described the NodePort result, which is not what
    the command would have written.
    """
    from devops_cli.commands.k8s.networking import _dry_run_preview

    proxy = _dry_run_preview(["llm"], "proxy")
    nodeport = _dry_run_preview(["llm"], "nodeport")
    assert proxy != nodeport


def test_the_proxy_preview_renders_cluster_native_addresses() -> None:
    """Proxy addressing writes `k8s://` addresses, so the preview must show those."""
    from devops_cli.commands.k8s.networking import _dry_run_preview

    preview = _dry_run_preview(["llm"], "proxy")
    assert preview["qdrant.url"].startswith("k8s://llm/qdrant:")


def test_the_preview_carries_no_host_address() -> None:
    """A minikube node IP was hardcoded here with assigned port numbers.

    It described some other cluster on every run, and it was the only concrete private
    address left in `src`.
    """
    import re

    from devops_cli.commands.k8s.networking import _dry_run_preview

    rendered = " ".join(
        value
        for mode in ("proxy", "nodeport")
        for value in _dry_run_preview(["infra", "llm"], mode).values()
    )
    assert re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", rendered) is None


def test_the_nodeport_preview_names_the_shape_of_what_it_cannot_know() -> None:
    """A node address and an assigned port are only resolved by asking the cluster."""
    from devops_cli.commands.k8s.networking import _dry_run_preview

    preview = _dry_run_preview(["infra"], "nodeport")
    assert preview["grafana.url"] == "http://<node>:<port>"


def test_the_valkey_preview_keeps_its_scheme() -> None:
    """Valkey is addressed as `valkey://`, not http; a preview that said otherwise would mislead."""
    from devops_cli.commands.k8s.networking import _dry_run_preview

    assert _dry_run_preview(["llm"], "nodeport")["valkey.url"].startswith("valkey://")


def test_a_stack_that_was_not_selected_is_absent_from_the_preview() -> None:
    """The preview describes what this invocation would write, not the full catalogue."""
    from devops_cli.commands.k8s.networking import _dry_run_preview

    assert "qdrant.url" not in _dry_run_preview(["infra"], "proxy")


def test_the_fqdn_preview_renders_domain_addresses() -> None:
    """FQDN addressing renders domain-based HTTPS URLs for services."""
    from devops_cli.commands.k8s.networking import _dry_run_preview

    preview = _dry_run_preview(["infra", "llm"], "fqdn")
    assert (
        preview["argocd.url"],
        preview["grafana.url"],
        preview["prometheus.url"],
        preview["open_webui.url"],
        preview["qdrant.url"],
        preview["ai.gateway_url"],
    ) == (
        "https://argocd.example.com",
        "https://grafana.example.com",
        "https://prometheus.example.com",
        "https://chat.example.com",
        "https://qdrant.example.com",
        "https://ai.example.com/v1",
    )
