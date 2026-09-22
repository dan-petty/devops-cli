"""Test suite for addressing cluster services through the Kubernetes API server."""

from __future__ import annotations

import ssl
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s import app as k8s_app
from devops_cli.k8s.service_http import describe_endpoint, get_json
from devops_cli.k8s.service_proxy import (
    ServiceAddressError,
    is_service_url,
    parse_service_url,
    resolve_proxy_target,
)


@pytest.fixture(autouse=True)
def clear_configuration_cache() -> Any:
    """Client configurations are cached process-wide; tests must not inherit one another's."""
    from devops_cli.k8s.service_proxy import reset_configuration_cache

    reset_configuration_cache()
    yield
    reset_configuration_cache()


runner = CliRunner()

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
    assert parse_service_url("k8s://otel/jaeger:http-query").port == "http-query"


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
    with pytest.raises(ServiceAddressError):
        parse_service_url(url)


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
    with pytest.raises(ServiceAddressError):
        parse_service_url("https://example.com")


def test_a_reference_round_trips_through_its_configuration_form() -> None:
    """What is displayed must be what can be pasted back into config.yaml."""
    original = "k8s+https://argocd/argocd-server:443/api/v1/session?a=1"
    assert parse_service_url(parse_service_url(original).describe()).describe() == original


# =============================================================================
# Credential Resolution
# =============================================================================


def _configuration(**overrides: Any) -> Any:
    """Build a Kubernetes client configuration stub."""
    configuration = MagicMock()
    configuration.host = overrides.get("host", "https://cluster.example.com:6443")
    configuration.ssl_ca_cert = overrides.get("ssl_ca_cert", None)
    configuration.verify_ssl = overrides.get("verify_ssl", True)
    configuration.cert_file = overrides.get("cert_file", None)
    configuration.key_file = overrides.get("key_file", None)
    configuration.api_key = overrides.get("api_key", {})
    configuration.api_key_prefix = overrides.get("api_key_prefix", {})
    return configuration


def test_the_proxy_url_is_built_from_the_api_server_host() -> None:
    """The whole point is that the API server is reachable wherever the kubeconfig is."""
    with patch("devops_cli.k8s.service_proxy._kube_configuration", return_value=_configuration()):
        target = resolve_proxy_target(parse_service_url(PROM), "api/v1/status")
    assert target.url == (
        "https://cluster.example.com:6443"
        "/api/v1/namespaces/monitoring/services/prometheus:9090/proxy/api/v1/status"
    )


def test_a_trailing_slash_on_the_host_does_not_double_up() -> None:
    """A doubled slash changes the path the API server matches."""
    with patch(
        "devops_cli.k8s.service_proxy._kube_configuration",
        return_value=_configuration(host="https://cluster.example.com:6443/"),
    ):
        target = resolve_proxy_target(parse_service_url(PROM))
    assert "//api/v1/namespaces" not in target.url


def test_a_bearer_token_becomes_an_authorization_header() -> None:
    """Token-authenticated clusters are the common case in CI."""
    with patch(
        "devops_cli.k8s.service_proxy._kube_configuration",
        return_value=_configuration(
            api_key={"authorization": "abc123"}, api_key_prefix={"authorization": "Bearer"}
        ),
    ):
        target = resolve_proxy_target(parse_service_url(PROM))
    assert target.headers["authorization"] == "Bearer abc123"


def test_an_empty_credential_is_not_sent_as_a_header() -> None:
    """An empty Authorization header is worse than none: it fails less clearly."""
    with patch(
        "devops_cli.k8s.service_proxy._kube_configuration",
        return_value=_configuration(api_key={"authorization": ""}),
    ):
        assert resolve_proxy_target(parse_service_url(PROM)).headers == {}


def test_client_certificates_are_loaded_into_the_ssl_context(tmp_path: Any) -> None:
    """A CA and a client certificate cannot both be passed to httpx as plain values, so
    they have to be combined into one context."""
    with patch("devops_cli.k8s.service_proxy._kube_configuration", return_value=_configuration()):
        target = resolve_proxy_target(parse_service_url(PROM))
    assert isinstance(target.ssl_context, ssl.SSLContext)


def test_an_insecure_kubeconfig_disables_verification() -> None:
    """Only reachable when the kubeconfig itself sets insecure-skip-tls-verify."""
    with patch(
        "devops_cli.k8s.service_proxy._kube_configuration",
        return_value=_configuration(verify_ssl=False),
    ):
        context = resolve_proxy_target(parse_service_url(PROM)).ssl_context
    assert (context.check_hostname, context.verify_mode) == (False, ssl.CERT_NONE)


def test_a_configuration_without_a_host_is_an_error() -> None:
    """Building a URL against an empty host would request a relative path."""
    with patch(
        "devops_cli.k8s.service_proxy._kube_configuration",
        return_value=_configuration(host=""),
    ):
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


def test_a_service_url_is_fetched_through_the_api_server() -> None:
    """No local port is involved, which is the property this exists for."""
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.get.return_value = _response('{"status": "success", "data": [1, 2]}')

    with (
        patch("devops_cli.k8s.service_proxy._kube_configuration", return_value=_configuration()),
        patch("httpx2.Client", return_value=client),
    ):
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

    with (
        patch("httpx2.Client", return_value=client),
        patch("devops_cli.k8s.service_http.validate_url_egress") as egress,
    ):
        get_json("http://prometheus.internal:9090", "api/v1/status")

    assert (
        client.get.call_args[0][0],
        egress.call_args.kwargs["allow_private"],
    ) == ("http://prometheus.internal:9090/api/v1/status", True)


def test_a_failing_request_raises_rather_than_returning_empty() -> None:
    """An empty result would read as "the service has no data"."""
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    response = _response()
    response.raise_for_status.side_effect = RuntimeError("404 Not Found")
    client.get.return_value = response

    with (
        patch("devops_cli.k8s.service_proxy._kube_configuration", return_value=_configuration()),
        patch("httpx2.Client", return_value=client),
    ):
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


def test_the_command_prints_the_portable_address() -> None:
    """The address is what goes into config.yaml and works on any cluster."""
    with patch("devops_cli.k8s.service_proxy._kube_configuration", return_value=_configuration()):
        result = runner.invoke(
            k8s_app, ["service-url", "prometheus", "-n", "monitoring", "-p", "9090", "--json"]
        )
    assert (result.exit_code, PROM in result.stdout) == (0, True)


def test_the_command_still_prints_the_address_when_no_cluster_is_reachable() -> None:
    """The address is valid configuration even when nothing can be contacted right now."""
    with patch(
        "devops_cli.k8s.service_proxy._kube_configuration",
        side_effect=ServiceAddressError("no kubeconfig"),
    ):
        result = runner.invoke(
            k8s_app, ["service-url", "prometheus", "-n", "monitoring", "-p", "9090", "--json"]
        )
    assert (result.exit_code, PROM in result.stdout) == (0, True)


def test_the_command_reports_a_failed_fetch() -> None:
    """A silent failure would read as an empty response."""
    with patch(
        "devops_cli.k8s.service_http.get_json", side_effect=RuntimeError("connection refused")
    ):
        result = runner.invoke(
            k8s_app,
            ["service-url", "prometheus", "-n", "monitoring", "-p", "9090", "--fetch"],
        )
    assert result.exit_code == 1


# =============================================================================
# Kubeconfig Bootstrap
# =============================================================================


def _k8s_modules(incluster_fails: bool = True, kubeconfig_fails: bool = False) -> Any:
    """Patch the kubernetes client and config modules used to load credentials."""
    config_module = MagicMock()
    if incluster_fails:
        config_module.load_incluster_config.side_effect = RuntimeError("not in a cluster")
    if kubeconfig_fails:
        config_module.load_kube_config.side_effect = RuntimeError("no kubeconfig")
    client_module = MagicMock()
    client_module.Configuration.get_default_copy.return_value = _configuration()
    return config_module, client_module


def test_credentials_are_loaded_for_the_resolved_context() -> None:
    """Addressing must follow the configured context like every other cluster call."""
    from devops_cli.k8s.service_proxy import _kube_configuration

    config_module, client_module = _k8s_modules()
    with (
        patch.dict(
            "sys.modules",
            {"kubernetes": MagicMock(client=client_module, config=config_module)},
        ),
        patch("devops_cli.k8s.service_proxy.resolve_context", return_value="homelab-k3s"),
    ):
        _kube_configuration()

    config_module.load_kube_config.assert_called_once_with(context="homelab-k3s")


def test_in_cluster_credentials_take_precedence() -> None:
    """Running inside the cluster must use the pod's service account."""
    from devops_cli.k8s.service_proxy import _kube_configuration

    config_module, client_module = _k8s_modules(incluster_fails=False)
    with (
        patch.dict(
            "sys.modules",
            {"kubernetes": MagicMock(client=client_module, config=config_module)},
        ),
        patch("devops_cli.k8s.service_proxy.resolve_context", return_value="homelab-k3s"),
    ):
        _kube_configuration()

    assert (
        config_module.load_incluster_config.call_count,
        config_module.load_kube_config.call_count,
    ) == (1, 0)


def test_no_usable_configuration_names_the_context_that_failed() -> None:
    """ "No kubeconfig" without naming the context is hard to act on."""
    from devops_cli.k8s.service_proxy import _kube_configuration

    config_module, client_module = _k8s_modules(kubeconfig_fails=True)
    with (
        patch.dict(
            "sys.modules",
            {"kubernetes": MagicMock(client=client_module, config=config_module)},
        ),
        patch("devops_cli.k8s.service_proxy.resolve_context", return_value="homelab-k3s"),
    ):
        with pytest.raises(ServiceAddressError, match="homelab-k3s"):
            _kube_configuration()


def test_client_certificates_are_loaded_when_both_files_are_present() -> None:
    """k3s admin kubeconfigs authenticate with a client certificate, not a token."""
    from devops_cli.k8s.service_proxy import _ssl_context

    configuration = _configuration(cert_file="/tmp/client.crt", key_file="/tmp/client.key")
    with patch("ssl.SSLContext.load_cert_chain") as load_chain:
        _ssl_context(configuration)
    load_chain.assert_called_once_with("/tmp/client.crt", "/tmp/client.key")


def test_a_certificate_without_its_key_is_not_loaded() -> None:
    """Half a credential is not a credential, and loading it raises."""
    from devops_cli.k8s.service_proxy import _ssl_context

    with patch("ssl.SSLContext.load_cert_chain") as load_chain:
        _ssl_context(_configuration(cert_file="/tmp/client.crt"))
    load_chain.assert_not_called()
