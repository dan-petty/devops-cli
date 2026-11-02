"""What `extract_network_references` finds in a file, and the scope and status it gives each
reference."""

from __future__ import annotations

import socket
from typing import Any

import pytest

from devops_cli.security.reference_extractor import extract_network_references

_EXAMPLE_DOC = """
# Example Configuration
Documentation URL: https://example.com/v1/health
Example IP: 192.0.2.1
Benchmarking IP: 198.18.1.10
IPv6 Doc IP: 2001:db8::42
Real Public IP: 93.184.216.34
Real Service: https://api.custom-service.io/v1
Contact: +1-212-555-0142
"""


def test_a_report_tags_documentation_space_as_an_example_and_reserved_space_as_local() -> None:
    """3fff::/20 (RFC 9637) is a documented example; multicast, shared address space and 6to4
    relay anycast are local, and none of them is reported as public (#1174)."""
    refs = extract_network_references(
        "doc 3fff::1 group 224.0.0.1 cgnat 100.64.0.1 relay 192.88.99.1 dns 8.8.8.8",
        "notes.md",
        exclude_examples=False,
    )
    assert {ref.target: (ref.scope, ref.security_status) for ref in refs} == {
        "3fff::1": ("local", "✓ Safe (Documented Example)"),
        "224.0.0.1": ("local", "✓ Safe (Local)"),
        "100.64.0.1": ("local", "✓ Safe (Local)"),
        "192.88.99.1": ("local", "✓ Safe (Local)"),
        "8.8.8.8": ("external", "✓ Safe"),
    }


def test_a_document_gives_its_urls_and_addresses_with_their_scope() -> None:
    """URLs and IP literals are references, each external or local; bare names, example domains
    and file names are not."""
    doc = """
    # Deployment Guide
    Access the cluster at https://api.prod.example-corp.com/v1
    Public ingress IP: 93.184.216.34
    Private internal IP: 192.168.1.100
    Local cluster: http://localhost:8080/v1
    Test host: localhost
    Example doc: example.com
    External endpoint: https://auth.vendor-service.io/oauth/token
    Bare domain reference: prod-infra.custom-cloud.io
    File reference: main.py, coverage.xml, dmypy.json, config.yaml (should all be skipped)
    """
    refs = extract_network_references(doc, "docs/deploy.md")

    assert {r.target: (r.is_local, r.scope) for r in refs} == {
        "https://api.prod.example-corp.com/v1": (False, "external"),
        "93.184.216.34": (False, "external"),
        "https://auth.vendor-service.io/oauth/token": (False, "external"),
        "192.168.1.100": (True, "local"),
        "http://localhost:8080/v1": (True, "local"),
    }
    assert "Local" in next(r for r in refs if r.target == "192.168.1.100").security_status


def test_json_and_yaml_values_give_their_urls_and_addresses() -> None:
    """Values in JSON and YAML configs are read like any text: URLs and addresses count, bare
    host names do not."""
    json_doc = """
    {
        "api_endpoint": "https://api.external-metrics.io/v1",
        "primary_host": "gateway.production-cloud.net",
        "internal_ip": "10.0.0.5",
        "public_ip": "93.184.216.34"
    }
    """
    yaml_doc = """
    services:
      monitoring:
        url: https://telemetry.custom-service.io/traces
        dns: traces.custom-service.io
        server_ip: 8.8.8.8
    """
    json_refs = {r.target: r for r in extract_network_references(json_doc, "config/settings.json")}
    yaml_targets = {r.target for r in extract_network_references(yaml_doc, "docker-compose.yml")}

    assert (
        json_refs["https://api.external-metrics.io/v1"].is_local,
        json_refs["93.184.216.34"].is_local,
        (json_refs["10.0.0.5"].is_local, json_refs["10.0.0.5"].scope),
        "gateway.production-cloud.net" in json_refs,
    ) == (False, False, (True, "local"), False)
    assert yaml_targets == {"https://telemetry.custom-service.io/traces", "8.8.8.8"}


def test_local_urls_and_private_addresses_are_local_and_local_names_are_not_references() -> None:
    """A local URL, a private address and loopback are local references; a cluster, corporate or
    LAN name with no scheme, and an example domain, are not references."""
    doc = """
    # Local & Internal Services
    Localhost API: http://localhost:8080/v1
    Cluster DNS: tempo.otel.svc.cluster.local
    Internal node: node1.corp.internal
    Home LAN: server.lan
    Private IP: 192.168.1.1
    Loopback: 127.0.0.1
    Reserved domain: example.com
    """
    refs = extract_network_references(doc, "docs/internal.md")

    assert {r.target: r.is_local for r in refs} == {
        "http://localhost:8080/v1": True,
        "192.168.1.1": True,
        "127.0.0.1": True,
    }


@pytest.mark.parametrize(
    ("file_name", "content", "target"),
    [
        pytest.param(
            "main.go",
            'package main\nconst ApiUrl = "https://api.datadoghq.com/api/v1/query"\n',
            "https://api.datadoghq.com/api/v1/query",
            id="go",
        ),
        pytest.param(
            "lib.rs",
            'pub const ENDPOINT: &str = "https://api.auth0.com/oauth/token";\n',
            "https://api.auth0.com/oauth/token",
            id="rust",
        ),
        pytest.param(
            "Dockerfile",
            "FROM alpine:3.19\nRUN curl -fsSL https://app.datadoghq.com/agent -o agent.sh\n",
            "https://app.datadoghq.com/agent",
            id="dockerfile",
        ),
    ],
)
def test_a_url_in_go_rust_or_a_dockerfile_is_a_reference(
    file_name: str, content: str, target: str
) -> None:
    """Source files of other languages give their URL literals."""
    refs = extract_network_references(content, file_name, include_local=True)

    assert target in {r.target for r in refs}


def test_a_shell_style_assignment_gives_its_public_url_and_address() -> None:
    """Assignments of URLs and addresses in a script give their public targets."""
    content = """
    # Network targets
    export PROMETHEUS_ENDPOINT="http://prometheus.internal:9090/metrics"
    export GRAFANA_HOST="https://grafana.prod.corp.com"
    export PUBLIC_API="https://api.external-service.net/v1"
    CONNECT_IP = "93.184.216.34"
    LOCAL_IP = "127.0.0.1"
    """
    targets = [r.target for r in extract_network_references(content, "deploy.py")]

    assert (
        len(targets) >= 2,
        any("https://api.external-service.net/v1" in t for t in targets),
        any("93.184.216.34" in t for t in targets),
    ) == (True, True, True)


def test_a_single_label_url_is_a_local_reference() -> None:
    """A URL whose host has no dot, such as a node name, is local."""
    refs = extract_network_references("url = 'http://node1:11434'", "test.py", include_local=True)

    assert [(r.target, r.is_local, r.scope) for r in refs] == [
        ("http://node1:11434", True, "local")
    ]


def test_a_comma_separated_list_of_urls_gives_each_url() -> None:
    """Each URL of a comma-separated list is its own reference, and the joined text is not."""
    refs = extract_network_references(
        'SERVERS = "http://node1:11434,http://node2:11434"', "test_urls.py"
    )

    assert {r.target for r in refs} >= {"http://node1:11434", "http://node2:11434"}
    assert "http://node1:11434,http://node2:11434" not in {r.target for r in refs}


def test_urls_and_addresses_in_dict_keys_and_call_arguments_are_references() -> None:
    """A URL or an address is a reference also as a dict key or a call argument; a bare name and
    a metric name are not."""
    code = """
    routes = {
        "https://api.example.internal/v1": "service_a",
        "8.8.8.8": "dns_server",
        "bare.domain.internal": "ignored",
    }
    record_metric("cli.command.total", 1.0)
    logfire.metric_counter("agent.tokens.total").add(10)
    counter("https://telemetry.custom-vendor.net/ingest")
    ping("1.1.1.1")
    """
    targets = {r.target for r in extract_network_references(code, "service.py", include_local=True)}

    assert (
        "https://api.example.internal/v1" in targets,
        "8.8.8.8" in targets,
        "1.1.1.1" in targets,
        "https://telemetry.custom-vendor.net/ingest" in targets,
        "bare.domain.internal" in targets,
        "cli.command.total" in targets,
        "agent.tokens.total" in targets,
    ) == (True, True, True, True, False, False, False)


def test_a_url_of_any_network_scheme_is_a_reference_and_a_file_url_is_not() -> None:
    """Redis, PostgreSQL, WebSocket and gRPC URLs are references; a `file:` URL is not."""
    content = """
    REDIS_URL = "redis://user:pass@redis.example.internal:6379/0"
    PG_URL = "postgresql://pg.example.internal:5432/db"
    WS_URL = "wss://stream.vendor.com/live"
    GRPC_URL = "grpc://grpc.vendor.com:443"
    FILE_URL = "file:///tmp/something"
    JDBC_URL = "jdbc:postgresql://db.vendor.com/test"
    """
    targets = {
        r.target for r in extract_network_references(content, "settings.py", include_local=True)
    }

    assert (
        "redis://user:pass@redis.example.internal:6379/0" in targets,
        "postgresql://pg.example.internal:5432/db" in targets,
        "wss://stream.vendor.com/live" in targets,
        "grpc://grpc.vendor.com:443" in targets,
        "file:///tmp/something" in targets,
    ) == (True, True, True, True, False)


def test_a_download_from_a_package_registry_is_skipped_by_host() -> None:
    """A package download from a registry host is skipped; the same file from another host is a
    reference."""
    pypi_url = "https://files.pythonhosted.org/packages/package.whl"
    crates_url = "https://crates.io/api/v1/crates/tokio/download"
    vendor_url = "https://downloads.vendor.com/package.whl"
    content = f'URLS = ["{pypi_url}", "{crates_url}", "{vendor_url}"]'

    targets = {r.target for r in extract_network_references(content, "download.py")}

    assert (pypi_url in targets, crates_url in targets, vendor_url in targets) == (
        False,
        False,
        True,
    )


def test_a_source_file_keeps_service_urls_and_arbitrary_downloads_but_not_registry_files() -> None:
    """Registry package files are skipped; a service endpoint and a download from another host
    stay."""
    src_content = """
    pypi_wheel = "https://files.pythonhosted.org/packages/4c/76/pkg-1.0.0.whl"
    npm_tarball = "https://registry.npmjs.org/lib/-/lib-2.0.0.tgz"
    service_api = "https://api.external-monitoring-service.net/v2/events"
    arbitrary_download = "https://evil-host.xyz/payload.tar.gz"
    """
    targets = {r.target for r in extract_network_references(src_content, "src/worker.py")}

    assert (
        "https://api.external-monitoring-service.net/v2/events" in targets,
        "https://evil-host.xyz/payload.tar.gz" in targets,
        "https://files.pythonhosted.org/packages/4c/76/pkg-1.0.0.whl" in targets,
        "https://registry.npmjs.org/lib/-/lib-2.0.0.tgz" in targets,
    ) == (True, True, False, False)


def test_a_lockfile_gives_no_reference() -> None:
    """The URLs of a lockfile are dependency sources, which the dependency checks cover."""
    lock_doc = """
    [[package]]
    name = "foo"
    version = "1.0.0"
    source = { url = "https://files.pythonhosted.org/packages/12/34/foo-1.0.0-py3-none-any.whl" }
    """
    assert extract_network_references(lock_doc, "uv.lock") == []


def test_example_targets_are_kept_and_tagged_when_examples_are_not_excluded() -> None:
    """With `exclude_examples=False`, an example domain and a documentation address are
    references that say they are documented examples; a real address is not an example."""
    refs = {
        r.target: r
        for r in extract_network_references(_EXAMPLE_DOC, "sample.md", exclude_examples=False)
    }

    assert (
        refs["https://example.com/v1/health"].is_example,
        "✓ Safe (Documented Example)" in refs["https://example.com/v1/health"].security_status,
        refs["192.0.2.1"].is_example,
        "✓ Safe (Documented Example)" in refs["192.0.2.1"].security_status,
        refs["93.184.216.34"].is_example,
        "https://api.custom-service.io/v1" in refs,
    ) == (True, True, True, True, False, True)


def test_example_targets_are_omitted_when_examples_are_excluded() -> None:
    """With `exclude_examples=True`, example domains and documentation and benchmarking addresses
    are not references; real targets stay."""
    targets = {
        r.target
        for r in extract_network_references(_EXAMPLE_DOC, "sample.md", exclude_examples=True)
    }

    assert (
        "https://example.com/v1/health" in targets,
        "192.0.2.1" in targets,
        "198.18.1.10" in targets,
        "2001:db8::42" in targets,
        "93.184.216.34" in targets,
        "https://api.custom-service.io/v1" in targets,
    ) == (False, False, False, False, True, True)


def test_reference_extraction_makes_no_dns_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Extraction reads the text only: it never resolves a name. Only a call with
    `AI_NUMERICHOST`, which makes no DNS query, reaches the resolver (#2152)."""
    real_getaddrinfo = socket.getaddrinfo

    def exploding_getaddrinfo(host: object, *args: Any, **kwargs: Any) -> Any:
        if not kwargs.get("flags", 0) & socket.AI_NUMERICHOST:
            raise AssertionError("DNS lookup attempted during reference extraction!")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", exploding_getaddrinfo)
    content = """
    export HOST="api.datadoghq.com"
    export URL="https://api.custom-service.io/v1"
    export IP="1.1.1.1"
    """
    targets = {r.target for r in extract_network_references(content, "test.sh")}

    assert (
        "https://api.custom-service.io/v1" in targets,
        "1.1.1.1" in targets,
        "api.datadoghq.com" in targets,
    ) == (True, True, False)
