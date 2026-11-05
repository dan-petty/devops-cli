"""The Ollama service that deploy-stack creates (#2164)."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.commands.k8s.networking import (
    _collect_port_forward_services,
    _configure_llm_stack_urls,
)
from devops_cli.commands.k8s.stack_lifecycle import (
    _HELM_RELEASES_BY_STACK,
    _MANIFESTS_BY_STACK,
)
from devops_cli.config.defaults import DEFAULT_OLLAMA_PORT
from devops_cli.config.settings import Settings
from devops_cli.k8s.service import KubernetesService
from tests.gate.k8s_render import applied_documents


def check_llm_stack_forwards_ollama_through_a_service_deploy_stack_creates() -> None:
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
        for doc in applied_documents(path)
        if doc.get("kind") == "Service"
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
