"""Unit and integration tests for Kubernetes stack networking and URL configuration safety."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import yaml

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.commands.k8s.networking import (
    _build_port_forward_details,
    _collect_port_forward_services,
    _configure_llm_stack_urls,
    _is_fqdn_url,
    _resolve_accessible_url,
    _resolve_effective_addressing,
    _select_best_ingress_host,
    _should_update_url,
    _update_ollama_urls,
    port_forward,
)
from devops_cli.commands.k8s.stack_lifecycle import (
    _HELM_RELEASES_BY_STACK,
    _MANIFESTS_BY_STACK,
    deploy_stack,
)
from devops_cli.config.defaults import DEFAULT_OLLAMA_PORT, DEFAULT_OLLAMA_URLS, DEFAULT_QDRANT_URL
from devops_cli.config.settings import Settings
from devops_cli.k8s.service import KubernetesService


def test_should_update_url_edge_cases() -> None:
    """_should_update_url preserves custom remote endpoints while allowing valid updates."""
    test_cases = (
        _should_update_url(None, "http://localhost:8080"),
        _should_update_url("http://example.com:8080", "http://localhost:8080"),
        _should_update_url("http://example.com:8080", "http://127.0.0.1:8080"),
        _should_update_url("http://example.com:8080", "http://example.com:30080"),
        _should_update_url(
            "http://localhost:6333", "http://localhost:6333", default_url=DEFAULT_QDRANT_URL
        ),
        _should_update_url("http://example.com:8080", None),
    )
    expected = (True, False, False, True, True, False)
    assert test_cases == expected


def test_update_ollama_urls_endpoint_preservation() -> None:
    """_update_ollama_urls protects custom remote Ollama endpoints from localhost clobbering."""
    settings_custom = Settings()
    settings_custom.ai.ollama_urls = ["http://example.com:11434"]
    configured_custom: dict[str, str] = {}
    _update_ollama_urls(settings_custom, configured_custom, "http://localhost:11434")

    settings_append = Settings()
    settings_append.ai.ollama_urls = ["http://example.com:11434"]
    configured_append: dict[str, str] = {}
    _update_ollama_urls(settings_append, configured_append, "http://example.com:31434")

    settings_default = Settings()
    settings_default.ai.ollama_urls = list(DEFAULT_OLLAMA_URLS)
    configured_default: dict[str, str] = {}
    _update_ollama_urls(settings_default, configured_default, "http://example.com:31434")

    assert (
        settings_custom.ai.ollama_urls,
        "ai.ollama_urls" in configured_custom,
        settings_append.ai.ollama_urls,
        settings_default.ai.ollama_urls,
    ) == (
        ["http://example.com:11434"],
        False,
        ["http://example.com:11434", "http://example.com:31434"],
        ["http://example.com:31434"],
    )


def test_resolve_accessible_url_prefers_reachable_cluster_endpoint() -> None:
    """_resolve_accessible_url retains reachable cluster URLs over localhost listeners."""
    with patch("devops_cli.commands.k8s.networking._verify_url_reachability", return_value=True):
        resolved_cluster = _resolve_accessible_url(
            "http://example.com:30080", preferred_localhost_ports=[8080]
        )

    def fake_verify(url: str, timeout: float = 1.0) -> bool:
        return "localhost" in url or "127.0.0.1" in url

    with patch(
        "devops_cli.commands.k8s.networking._verify_url_reachability", side_effect=fake_verify
    ):
        resolved_fallback = _resolve_accessible_url(
            "http://example.com:30080", preferred_localhost_ports=[8080]
        )

    assert (resolved_cluster, resolved_fallback) == (
        "http://example.com:30080",
        "http://localhost:8080",
    )


def test_collect_port_forward_services_and_details() -> None:
    """_collect_port_forward_services and _build_port_forward_details generate valid specs."""
    ports = {
        "argocd": 8080,
        "grafana": 8030,
        "prometheus": 8090,
        "jaeger": 16686,
        "pyroscope": 4040,
        "otel": 4318,
        "ollama": 11434,
        "open_webui": 3000,
        "qdrant": 6333,
        "valkey": 6379,
    }
    services_infra = _collect_port_forward_services(["infra"], ports)
    services_llm = _collect_port_forward_services(["llm"], ports)
    details_infra = _build_port_forward_details(["infra"], ports)
    details_llm = _build_port_forward_details(["llm"], ports)

    assert (
        len(services_infra),
        len(services_llm),
        details_infra["argocd.url"],
        details_infra["pyroscope.url"],
        details_llm["ollama.url"],
    ) == (
        6,
        4,
        "http://localhost:8080",
        "http://localhost:4040",
        "http://localhost:11434",
    )


def test_llm_stack_forwards_ollama_through_a_service_deploy_stack_creates() -> None:
    """port-forward and configure-urls address only Services the llm stack deploys (#953).

    Both addressed `ollama`, a Service only `k8s/llm/ollama-host-service.yaml` defined and nothing
    applied once the Ollama tiers replaced the single workload, so the Ollama forward failed. They
    now address the default tier's Service, which is ClusterIP: configure-urls detects no
    NodePort or load balancer for it, and sets `ai.ollama_urls` only when the forward answers on
    `localhost:11434`.
    """
    manifests = {
        (doc["metadata"]["namespace"], doc["metadata"]["name"]): doc
        for path in _MANIFESTS_BY_STACK["llm"]
        for doc in yaml.load_all(
            path.read_text(encoding="utf-8"), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader)
        )
        if doc and doc.get("kind") == "Service"
    }
    # A Helm release's Service carries the release name.
    deployed = manifests.keys() | {
        (release["namespace"], release["name"]) for release in _HELM_RELEASES_BY_STACK["llm"]
    }
    forwarded = [
        (namespace, service.removeprefix("svc/"))
        for namespace, service, _, _ in _collect_port_forward_services(
            ["llm"], dict.fromkeys(("ollama", "open_webui", "qdrant", "valkey"), 0)
        )
    ]

    # kubectl answers `get svc` with the Services the llm manifests define, so detection sees
    # each one's real type. The native client finds nothing.
    looked_up: list[tuple[str, str]] = []

    def kubectl(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        service = (
            (cmd[cmd.index("-n") + 1], cmd[3]) if cmd[:3] == ["kubectl", "get", "svc"] else None
        )
        if service:
            looked_up.append(service)
        found = manifests.get(service) if service else None
        return subprocess.CompletedProcess(cmd, 0 if found else 1, json.dumps(found or {}), "")

    def configured_ollama(listening: set[str]) -> str | None:
        configured: dict[str, str] = {}
        with (
            patch.object(runtime, "resolve_effective_context", return_value=None),
            patch.object(runtime, "run_subprocess", side_effect=kubectl),
            patch.object(KubernetesService, "get_instance") as native,
            patch(
                "devops_cli.commands.k8s.networking._verify_url_reachability",
                side_effect=lambda url, timeout=0.0: url in listening,
            ),
        ):
            native.return_value.resolve_service_endpoint.return_value = None
            _configure_llm_stack_urls(None, Settings(), configured)
        return configured.get("ai.ollama_urls")

    forward = f"http://localhost:{DEFAULT_OLLAMA_PORT}"
    assert (
        configured_ollama(set()),
        configured_ollama({forward}),
        sorted(set(looked_up)),
        sorted({*forwarded, *looked_up} - deployed),
    ) == (None, forward, sorted(forwarded), [])


def test_deploy_stack_defaults_do_not_port_forward_or_configure_urls() -> None:
    """deploy_stack does not invoke port-forward or configure-urls unless requested."""
    with (
        patch(
            "devops_cli.commands.k8s.stack_lifecycle.runtime._cluster_reachable", return_value=True
        ),
        patch("devops_cli.commands.k8s.stack_lifecycle.runtime._run_cmd"),
        patch("devops_cli.commands.k8s.stack_lifecycle.net.port_forward") as mock_pf,
        patch("devops_cli.commands.k8s.stack_lifecycle.net.configure_urls") as mock_conf,
        patch("devops_cli.k8s.credentials.sync_k8s_credentials", return_value={}),
        patch("devops_cli.commands.k8s.stack_lifecycle.push_for_stacks"),
        patch("devops_cli.commands.k8s.stack_lifecycle.require_keyring_for_push"),
        patch("devops_cli.commands.k8s.stack_lifecycle.namespace_exists", return_value=False),
    ):
        deploy_stack(stack="infra")
        assert (mock_pf.called, mock_conf.called) == (False, False)

        deploy_stack(stack="infra", port_forward=True)
        assert (mock_pf.called, mock_conf.called) == (True, False)

        mock_pf.reset_mock()
        deploy_stack(stack="infra", configure_urls=True)
        assert (mock_pf.called, mock_conf.called) == (False, True)


def test_port_forward_defaults_do_not_update_config() -> None:
    """port_forward does not invoke configure_urls unless update_config is True."""
    with (
        patch("devops_cli.commands.k8s.networking.runtime._cluster_reachable", return_value=True),
        patch("devops_cli.commands.k8s.networking._launch_port_forwards"),
        patch("time.sleep"),
        patch("devops_cli.commands.k8s.networking.configure_urls") as mock_conf,
    ):
        port_forward(stack="infra")
        assert mock_conf.called is False

        port_forward(stack="infra", update_config=True)
        assert mock_conf.called is True


def test_is_fqdn_url() -> None:
    """_is_fqdn_url correctly identifies valid FQDN endpoints and rejects IPs/loopbacks."""
    results = (
        _is_fqdn_url("https://argocd.example.com"),
        _is_fqdn_url("http://chat.example.com:8080"),
        _is_fqdn_url("http://192.0.2.1:30500"),
        _is_fqdn_url("http://127.0.0.1:8080"),
        _is_fqdn_url("http://localhost:11434"),
        _is_fqdn_url("http://service.default.svc.cluster.local:8080"),
        _is_fqdn_url(""),
        _is_fqdn_url(None),
    )
    expected = (True, True, False, False, False, False, False, False)
    assert results == expected


def test_should_update_url_preserves_fqdn() -> None:
    """_should_update_url forbids downgrading FQDN URLs to NodePort IPs or loopback."""
    results = (
        _should_update_url("https://argocd.example.com", "http://192.0.2.4:30500"),
        _should_update_url("https://argocd.example.com", "http://localhost:8080"),
        _should_update_url("https://argocd.example.com", "https://argocd.example.com"),
        _should_update_url("https://argocd.example.com", "https://new-argocd.example.com"),
    )
    assert results == (False, False, True, True)


def test_select_best_ingress_host() -> None:
    """_select_best_ingress_host prefers host matching the configured domain."""
    hosts = ["argocd.example.com", "argocd.homelab.example.com"]
    chosen_with_domain = _select_best_ingress_host(hosts, preferred_domain="homelab.example.com")
    chosen_default = _select_best_ingress_host(hosts, preferred_domain=None)
    chosen_empty = _select_best_ingress_host([], preferred_domain="example.com")
    assert (chosen_with_domain, chosen_default, chosen_empty) == (
        "argocd.homelab.example.com",
        "argocd.example.com",
        None,
    )


def test_resolve_effective_addressing() -> None:
    """_resolve_effective_addressing determines correct mode from args or settings."""
    settings_empty = Settings()
    settings_empty.k8s.domain = None
    settings_empty.k8s.addressing = "nodeport"

    settings_domain = Settings()
    settings_domain.k8s.domain = "example.com"
    settings_domain.k8s.addressing = "nodeport"

    settings_domain_no_addressing = Settings()
    settings_domain_no_addressing.k8s.domain = "example.com"
    settings_domain_no_addressing.k8s.addressing = None

    settings_explicit_mode = Settings()
    settings_explicit_mode.k8s.domain = None
    settings_explicit_mode.k8s.addressing = "proxy"

    results = (
        _resolve_effective_addressing("fqdn", settings_empty),
        _resolve_effective_addressing(None, settings_empty),
        _resolve_effective_addressing(None, settings_domain),
        _resolve_effective_addressing(None, settings_domain_no_addressing),
        _resolve_effective_addressing(None, settings_explicit_mode),
    )
    assert results == ("fqdn", "nodeport", "nodeport", "fqdn", "proxy")


def test_preview_fqdn_addresses() -> None:
    """_preview_fqdn_addresses returns domain-based endpoints for infra and llm stacks."""
    from devops_cli.commands.k8s.networking import _preview_fqdn_addresses

    preview_infra = _preview_fqdn_addresses(["infra"])
    preview_llm = _preview_fqdn_addresses(["llm"])
    assert (
        preview_infra.get("argocd.url"),
        preview_llm.get("ai.gateway_url"),
    ) == (
        "https://argocd.example.com",
        "https://ai.example.com/v1",
    )


def test_configure_fqdn_urls() -> None:
    """_configure_fqdn_urls maps discovered ingress hosts to service configurations."""
    from devops_cli.commands.k8s.networking import _configure_fqdn_urls

    mock_ingress = {
        "argocd-server": ["argocd.example.com"],
        "open-webui": ["chat.example.com"],
        "llm-gateway": ["ai.example.com"],
    }
    settings = Settings()
    settings.ai.gateway_enabled = False
    settings.ai.tasks.analysis.provider = "copilot"
    settings.ai.tasks.analysis.api_base_url = "https://example.com/custom"
    settings.ai.tasks.chat.provider = "gateway"
    settings.ai.tasks.chat.api_base_url = None
    configured: dict[str, str] = {}

    with patch(
        "devops_cli.commands.k8s.networking._discover_ingress_hosts",
        return_value=mock_ingress,
    ):
        _configure_fqdn_urls(None, settings, configured, ["infra", "llm"])

    assert (
        configured.get("argocd.url"),
        configured.get("open_webui.url"),
        configured.get("ai.gateway_url"),
        settings.ai.gateway_enabled,
        settings.ai.tasks.analysis.api_base_url,
        settings.ai.tasks.chat.api_base_url,
    ) == (
        "https://argocd.example.com",
        "https://chat.example.com",
        "https://ai.example.com/v1",
        False,
        "https://example.com/custom",
        "https://ai.example.com/v1",
    )
