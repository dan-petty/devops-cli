"""Services in the namespaces of Helm charts (#2164)."""

from __future__ import annotations

from devops_cli.commands.k8s.stack_lifecycle import (
    HELM_RELEASES_BY_STACK,
    MANIFESTS_BY_STACK,
)
from tests.gate.k8s_render import applied_objects, kustomized_objects, manifest_objects
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"


# Services declared in plain manifests that sit in a namespace where a Helm release installs.
# Each entry maps (namespace, name) to (manifest_path, owner).
EXEMPT_PLAIN_SERVICES: dict[tuple[str, str], tuple[str, str]] = {
    ("llm", "valkey"): ("k8s/llm/valkey.yaml", "llm stack valkey manifest"),
    ("llm", "valkey-runs"): ("k8s/llm/valkey-runs.yaml", "llm stack valkey-runs manifest"),
    ("llm", "valkey-devops"): ("k8s/llm/valkey-devops.yaml", "llm stack valkey-devops manifest"),
    ("llm", "llm-gateway"): ("k8s/llm/gateway/service.yaml", "llm stack gateway manifest"),
    ("llm", "portkey"): ("k8s/llm/portkey/service.yaml", "llm stack portkey manifest"),
    **{
        ("llm", f"ollama-{name}"): ("k8s/llm/profiles/services.yaml", "llm stack ollama profile")
        for name in (
            "16gib",
            "24gib",
            "32gib",
            "48gib",
            "64gib",
            "72gib",
            "96gib",
            "128gib",
            "fast",
            "standard",
            "slow",
            "48gib-fast",
            "24gib-embed-gpu0",
            "24gib-embed-gpu1",
            "64gib-standard",
            "16gib-fast",
            "24gib-slow",
        )
    },
}


def check_no_plain_service_sits_in_a_helm_namespace_without_owned_exemption() -> None:
    """No Service in the kustomize base, or in any plain manifest that deploy-stack applies,
    sits in a namespace that a release in HELM_RELEASES_BY_STACK installs into, unless an
    exemption names its owner (#1104). The test renders no chart and keeps no hand-written
    list of chart Service names.
    """
    helm_namespaces = {
        r["namespace"] for releases in HELM_RELEASES_BY_STACK.values() for r in releases
    }
    base_services = kustomized_objects(K8S_DIR, "Service")
    manifest_services = {
        svc
        for manifests in MANIFESTS_BY_STACK.values()
        for m in manifests
        for svc in applied_objects(REPO_ROOT / m, "Service")
    }
    colliding = {svc for svc in (base_services | manifest_services) if svc[0] in helm_namespaces}
    exempted = set(EXEMPT_PLAIN_SERVICES)

    assert (
        sorted(colliding - exempted),
        sorted(exempted - colliding),
        sorted(
            svc
            for svc, (path, _owner) in EXEMPT_PLAIN_SERVICES.items()
            if svc not in manifest_objects(REPO_ROOT / path, "Service")
        ),
    ) == ([], [], [])
