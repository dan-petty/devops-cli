"""Test suite for addressing cluster services through the Kubernetes API server."""

from __future__ import annotations

import ssl
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.k8s.service_http import describe_endpoint, get_json
from devops_cli.k8s.service_proxy import (
    ServiceAddressError,
    is_service_url,
    kube_configuration,
    parse_service_url,
    resolve_proxy_target,
    ssl_context,
)
from tests.support.fakes.kubernetes import FakeCluster

PROM = "k8s://monitoring/prometheus:9090"


# =============================================================================
# URL Parsing
# =============================================================================


def test_a_service_url_parses_into_its_parts() -> None:
    """The address names a Service, not a host, which is what makes it portable."""
    ref = parse_service_url("k8s://monitoring/prometheus:9090/api/v1/query")
    assert (ref.namespace, ref.service, ref.port, ref.path, ref.tls) == (
        "monitoring",
        "prometheus",
        "9090",
        "api/v1/query",
        False,
    )


def test_a_query_string_survives_parsing() -> None:
    """urlparse splits the query off the path.

    A Prometheus or Loki endpoint is almost entirely query string, so dropping it turns
    every request into a bare /proxy call that the API server rejects with 400.
    """
    ref = parse_service_url("k8s://monitoring/prometheus:9090/api/v1/query?query=up&time=5")
    assert (ref.path, ref.query) == ("api/v1/query", "query=up&time=5")


def test_a_query_string_reaches_the_proxy_path() -> None:
    """Parsing it is not enough; it has to be rebuilt into the request."""
    ref = parse_service_url("k8s://monitoring/prometheus:9090/api/v1/query?query=up")
    assert ref.proxy_path().endswith("/proxy/api/v1/query?query=up")


def test_a_named_port_is_accepted() -> None:
    """Services commonly expose ports by name rather than number."""
    assert parse_service_url("k8s://otel/tempo:prom-metrics").port == "prom-metrics"


def test_a_tls_backend_uses_the_https_proxy_prefix() -> None:
    """The prefix tells the API server how to reach the backend, not how to reach itself."""
    ref = parse_service_url("k8s+https://argocd/argocd-server:443")
    assert (ref.tls, ref.target) == (True, "https:argocd-server:443")


def test_a_plain_backend_has_no_scheme_prefix() -> None:
    """An unnecessary prefix would make the API server speak TLS to a plaintext port."""
    assert parse_service_url(PROM).target == "prometheus:9090"


def test_a_reference_without_a_path_proxies_to_the_service_root() -> None:
    """Some endpoints are served at the root."""
    assert parse_service_url(PROM).proxy_path() == (
        "/api/v1/namespaces/monitoring/services/prometheus:9090/proxy"
    )


def test_an_explicit_path_overrides_the_reference_path() -> None:
    """Callers append request paths to a configured base address."""
    ref = parse_service_url("k8s://monitoring/prometheus:9090/unused")
    assert ref.proxy_path("api/v1/status").endswith("/proxy/api/v1/status")


def test_an_override_path_may_carry_its_own_query() -> None:
    """A caller building a query should not have to split it first."""
    assert (
        parse_service_url(PROM)
        .proxy_path("api/v1/query?query=up")
        .endswith("/proxy/api/v1/query?query=up")
    )


@pytest.mark.parametrize(
    ("description", "url"),
    [
        ("missing port", "k8s://monitoring/prometheus"),
        ("empty port", "k8s://monitoring/prometheus:"),
        ("missing service", "k8s://monitoring"),
        ("missing service with slash", "k8s://monitoring/"),
        ("missing namespace", "k8s:///prometheus:9090"),
    ],
)
def test_a_malformed_service_url_is_rejected(description: str, url: str) -> None:
    """Treating a malformed k8s:// URL as an ordinary one produces a DNS failure naming a
    host the operator never configured, which is far harder to act on than an error."""
    with pytest.raises(ServiceAddressError) as raised:
        parse_service_url(url)
    assert raised.value.error_code == "K8S_ERROR"


def test_the_port_is_required_rather_than_guessed() -> None:
    """A Service may expose several ports; picking one would silently target the wrong."""
    with pytest.raises(ServiceAddressError, match="port"):
        parse_service_url("k8s://monitoring/prometheus")


def test_an_ordinary_url_is_not_a_service_url() -> None:
    """Direct addressing keeps working for endpoints outside the cluster."""
    assert (is_service_url("https://example.com"), is_service_url(PROM)) == (False, True)


def test_an_empty_url_is_not_a_service_url() -> None:
    """Absence of configuration is not a malformed address."""
    assert is_service_url("") is False


def test_parsing_a_non_service_url_is_an_error() -> None:
    """The caller checked is_service_url first, so reaching here is a programming error."""
    with pytest.raises(ServiceAddressError) as raised:
        parse_service_url("https://example.com")
    assert raised.value.error_code == "K8S_ERROR"


def test_a_reference_round_trips_through_its_configuration_form() -> None:
    """What is displayed must be what can be pasted back into config.yaml."""
    original = "k8s+https://argocd/argocd-server:443/api/v1/session?a=1"
    assert parse_service_url(parse_service_url(original).describe()).describe() == original


# =============================================================================
# Credential Resolution
# =============================================================================


def _configuration(**overrides: Any) -> Any:
    """Build a Kubernetes client configuration stub."""
    from kubernetes.client import Configuration

    configuration = Configuration()
    configuration.host = overrides.get("host", "https://cluster.example.com:6443")
    configuration.ssl_ca_cert = overrides.get("ssl_ca_cert", None)
    configuration.verify_ssl = overrides.get("verify_ssl", True)
    configuration.cert_file = overrides.get("cert_file", None)
    configuration.key_file = overrides.get("key_file", None)
    configuration.api_key = overrides.get("api_key", {})
    configuration.api_key_prefix = overrides.get("api_key_prefix", {})
    configuration.refresh_api_key_hook = overrides.get("refresh_api_key_hook", None)
    return configuration


def test_the_proxy_url_is_built_from_the_api_server_host(cluster: FakeCluster) -> None:
    """The whole point is that the API server is reachable wherever the kubeconfig is."""
    target = resolve_proxy_target(parse_service_url(PROM), "api/v1/status")
    assert target.url == (
        "https://cluster.example.com:6443"
        "/api/v1/namespaces/monitoring/services/prometheus:9090/proxy/api/v1/status"
    )


def test_a_trailing_slash_on_the_host_does_not_double_up(cluster: FakeCluster) -> None:
    """A doubled slash changes the path the API server matches."""
    cluster.configuration.host = "https://cluster.example.com:6443/"
    target = resolve_proxy_target(parse_service_url(PROM))
    assert "//api/v1/namespaces" not in target.url


def test_a_bearer_token_becomes_an_authorization_header(cluster: FakeCluster) -> None:
    """Token-authenticated clusters are the common case in CI."""
    cluster.configuration.api_key = {"authorization": "abc123"}
    cluster.configuration.api_key_prefix = {"authorization": "Bearer"}
    target = resolve_proxy_target(parse_service_url(PROM))
    assert target.headers["authorization"] == "Bearer abc123"


def test_a_bearer_token_stored_under_bearer_token_key_becomes_authorization_header(
    cluster: FakeCluster,
) -> None:
    """kubernetes 36+ stores bearer tokens under BearerToken, which must map to authorization."""
    cluster.configuration.api_key = {"BearerToken": "cluster-token-xyz"}
    cluster.configuration.api_key_prefix = {"BearerToken": "Bearer"}
    target = resolve_proxy_target(parse_service_url(PROM))
    assert ("BearerToken" not in target.headers, target.headers.get("authorization")) == (
        True,
        "Bearer cluster-token-xyz",
    )


def test_refresh_api_key_hook_rotates_token_on_each_request(cluster: FakeCluster) -> None:
    """Dynamic tokens (in-cluster, OIDC, exec) rotate through refresh_api_key_hook."""
    counter = 0

    def rotate(config: Any) -> None:
        nonlocal counter
        counter += 1
        config.api_key["BearerToken"] = f"rotated-token-{counter}"
        config.api_key_prefix["BearerToken"] = "Bearer"

    cluster.configuration.refresh_api_key_hook = rotate
    target1 = resolve_proxy_target(parse_service_url(PROM))
    target2 = resolve_proxy_target(parse_service_url(PROM))

    assert (
        target1.headers.get("authorization"),
        target2.headers.get("authorization"),
        "BearerToken" in target1.headers,
    ) == ("Bearer rotated-token-1", "Bearer rotated-token-2", False)


def test_an_empty_credential_is_not_sent_as_a_header(cluster: FakeCluster) -> None:
    """An empty Authorization header is worse than none: it fails less clearly."""
    cluster.configuration.api_key = {"authorization": ""}
    assert resolve_proxy_target(parse_service_url(PROM)).headers == {}


def test_client_certificates_are_loaded_into_the_ssl_context(cluster: FakeCluster) -> None:
    """A CA and a client certificate cannot both be passed to httpx as plain values, so
    they have to be combined into one context."""
    target = resolve_proxy_target(parse_service_url(PROM))
    assert isinstance(target.ssl_context, ssl.SSLContext)
    assert target.ssl_context.verify_mode == ssl.CERT_REQUIRED


def test_an_insecure_kubeconfig_disables_verification(cluster: FakeCluster) -> None:
    """Only reachable when the kubeconfig itself sets insecure-skip-tls-verify."""
    cluster.configuration.verify_ssl = False
    context = resolve_proxy_target(parse_service_url(PROM)).ssl_context
    assert (context.check_hostname, context.verify_mode) == (False, ssl.CERT_NONE)


def test_a_configuration_without_a_host_is_an_error(cluster: FakeCluster) -> None:
    """Building a URL against an empty host would request a relative path."""
    cluster.configuration.host = ""
    with pytest.raises(ServiceAddressError, match="API server host"):
        resolve_proxy_target(parse_service_url(PROM))


# =============================================================================
# Fetching
# =============================================================================


def _response(payload: str = '{"status": "success"}') -> Any:
    """Build an httpx response stub."""
    response = MagicMock()
    response.text = payload
    response.raise_for_status = MagicMock()
    return response


def test_a_service_url_is_fetched_through_the_api_server(cluster: FakeCluster) -> None:
    """No local port is involved, which is the property this exists for."""
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.get.return_value = _response('{"status": "success", "data": [1, 2]}')

    with patch("httpx2.Client", return_value=client):
        payload = get_json(PROM, "api/v1/label/__name__/values")

    requested = client.get.call_args[0][0]
    assert (payload["status"], "/proxy/api/v1/label/__name__/values" in requested) == (
        "success",
        True,
    )


def test_an_ordinary_url_is_fetched_directly() -> None:
    """Direct addressing is unchanged for endpoints that are not cluster services."""
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.get.return_value = _response()

    with patch("httpx2.Client", return_value=client):
        get_json("http://prometheus.internal:9090", "api/v1/status")

    assert client.get.call_args[0][0] == "http://prometheus.internal:9090/api/v1/status"


def test_a_failing_request_raises_rather_than_returning_empty(cluster: FakeCluster) -> None:
    """An empty result would read as "the service has no data"."""
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    response = _response()
    response.raise_for_status.side_effect = RuntimeError("404 Not Found")
    client.get.return_value = response

    with patch("httpx2.Client", return_value=client):
        with pytest.raises(RuntimeError, match="404"):
            get_json(PROM)


def test_an_endpoint_is_described_in_its_configuration_form() -> None:
    """Displays should show the portable address, not the resolved API server URL."""
    assert describe_endpoint(PROM) == PROM


def test_describing_an_ordinary_url_returns_it_unchanged() -> None:
    """Non-service endpoints display as written."""
    assert describe_endpoint("https://example.com") == "https://example.com"


def test_describing_a_malformed_service_url_returns_it_unchanged() -> None:
    """A display helper must not raise on bad configuration."""
    assert describe_endpoint("k8s://broken") == "k8s://broken"


# =============================================================================
# CLI
# =============================================================================


def test_the_command_prints_the_portable_address(
    cluster: FakeCluster, cli: Callable[..., Any]
) -> None:
    """The address is what goes into config.yaml and works on any cluster."""
    result = cli("k8s", "service-url", "prometheus", "-n", "monitoring", "-p", "9090", "--json")
    assert (result.exit_code, PROM in result.stdout) == (0, True)


def test_the_command_still_prints_the_address_when_no_cluster_is_reachable(
    cluster: FakeCluster, cli: Callable[..., Any]
) -> None:
    """The address is valid configuration even when nothing can be contacted right now."""
    cluster.configuration = None
    result = cli("k8s", "service-url", "prometheus", "-n", "monitoring", "-p", "9090", "--json")
    assert (result.exit_code, PROM in result.stdout) == (0, True)


def test_the_command_reports_a_failed_fetch(
    cluster: FakeCluster, refusing_port: int, cli: Callable[..., Any]
) -> None:
    """A silent failure would read as an empty response."""
    cluster.configuration.host = f"http://127.0.0.1:{refusing_port}"
    result = cli(
        "k8s",
        "service-url",
        "prometheus",
        "-n",
        "monitoring",
        "-p",
        "9090",
        "--fetch",
    )
    assert result.exit_code == 1


# =============================================================================
# Kubeconfig Bootstrap
# =============================================================================


def test_credentials_are_loaded_for_the_resolved_context(
    cluster: FakeCluster, config: Callable[..., Path]
) -> None:
    """Addressing must follow the configured context like every other cluster call."""
    cluster.context_names.append("homelab-k3s")
    config(k8s={"context": "homelab-k3s"})
    kube_configuration()
    assert "homelab-k3s" in cluster.connects


def test_no_usable_configuration_names_the_context_that_failed(cluster: FakeCluster) -> None:
    """ "No usable configuration" names the context that failed."""
    cluster.configuration = None
    with pytest.raises(ServiceAddressError, match=cluster.current or "fake"):
        kube_configuration()


def test_client_certificates_are_loaded_when_both_files_are_present(tmp_path: Path) -> None:
    """k3s admin kubeconfigs authenticate with a client certificate, not a token."""
    cert_file, key_file = str(tmp_path / "client.crt"), str(tmp_path / "client.key")
    configuration = _configuration(cert_file=cert_file, key_file=key_file)
    with patch("ssl.SSLContext.load_cert_chain") as load_chain:
        ssl_context(configuration)
    load_chain.assert_called_once_with(cert_file, key_file)


def test_a_certificate_without_its_key_is_not_loaded(tmp_path: Path) -> None:
    """Half a credential is not a credential, and loading it raises."""
    with patch("ssl.SSLContext.load_cert_chain") as load_chain:
        ssl_context(_configuration(cert_file=str(tmp_path / "client.crt")))
    load_chain.assert_not_called()
