"""The Crawl4AI manifests under `k8s/devops/crawl4ai/`: what the committed files must hold (#3884)."""

from __future__ import annotations

from typing import Any

import yaml

from devops_cli.commands.k8s.stack_lifecycle import PRODUCT_MANIFESTS_BY_STACK
from tests.support.k8s_tree import K8S, manifests, pod_spec
from tests.support.paths import REPO_ROOT

CRAWL4AI_DIR = K8S / "devops" / "crawl4ai"
# A switch that lets the service reach an internal address, run a hook or run script from a caller.
FORBIDDEN_ENV = (
    "CRAWL4AI_ALLOW_INTERNAL_URLS",
    "CRAWL4AI_HOOKS_ENABLED",
    "CRAWL4AI_EXECUTE_JS_ENABLED",
)
ROUTE_KINDS = ("Ingress", "IngressRoute", "IngressRouteTCP", "HTTPRoute", "Middleware")


def _object(kind: str, name: str) -> dict[str, Any]:
    (found,) = (
        document
        for _, document in manifests()
        if document["kind"] == kind and document["metadata"]["name"] == name
    )
    return found


def _container() -> dict[str, Any]:
    (container,) = pod_spec(_object("Deployment", "crawl4ai"))["containers"]  # type: ignore[index]
    return container


def _pod() -> dict[str, Any]:
    spec = pod_spec(_object("Deployment", "crawl4ai"))
    assert spec is not None
    return spec


def test_the_pod_meets_pod_security_restricted() -> None:
    """Namespace devops enforces `restricted`, so the pod sets each control that level needs. The
    user is the numeric ID of `appuser` in the image (999), because a named user cannot be checked
    against `runAsNonRoot`. The pod mounts no service account token and no host path."""
    pod = _pod()
    container = _container()
    volume_kinds = {next(iter(set(volume) - {"name"})) for volume in pod["volumes"]}

    assert (
        pod["securityContext"]["runAsNonRoot"],
        pod["securityContext"]["runAsUser"],
        pod["securityContext"]["seccompProfile"],
        pod["automountServiceAccountToken"],
        container["securityContext"],
        volume_kinds,
        pod.get("hostNetwork", False) or pod.get("hostPID", False) or pod.get("hostIPC", False),
    ) == (
        True,
        999,
        {"type": "RuntimeDefault"},
        False,
        {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        },
        {"emptyDir"},
        False,
    )


def test_the_environment_holds_the_token_and_the_bind_and_no_switch_or_key() -> None:
    """The token comes from Secret `crawl4ai`. The bind is an IPv4 address, so a Service reaches the
    pod whatever the node's IPv6 setting. No switch lets a caller reach an internal address, run a
    hook or run script, and the pod holds no key of a model provider (#3884)."""
    container = _container()
    env = {item["name"]: item for item in container["env"]}

    assert (
        env,
        container.get("envFrom"),
        sorted(set(FORBIDDEN_ENV) & set(env)),
    ) == (
        {
            "CRAWL4AI_API_TOKEN": {
                "name": "CRAWL4AI_API_TOKEN",
                "valueFrom": {"secretKeyRef": {"name": "crawl4ai", "key": "CRAWL4AI_API_TOKEN"}},
            },
            "GUNICORN_BIND": {"name": "GUNICORN_BIND", "value": "0.0.0.0:11235"},
        },
        None,
        [],
    )


def test_no_route_reaches_the_service_from_outside_the_cluster() -> None:
    """The service has no Ingress, no Traefik route and no tunnel entry: a page fetch proxy that
    the public reaches is a risk, and the in-app filter had bypasses in 0.8 and 0.9."""
    routed = [
        (relative, document["kind"])
        for relative, document in manifests()
        if document["kind"] in ROUTE_KINDS and "crawl4ai" in yaml.safe_dump(document)
    ]
    tunnel = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in (K8S / "cloudflared").rglob("*.y*ml")
        if "crawl4ai" in path.read_text(encoding="utf-8")
    ]

    assert (routed, tunnel) == ([], [])


def test_every_file_of_the_service_is_in_both_kustomizations_and_the_deploy_stack() -> None:
    """Argo CD syncs the files that the kustomizations list, and `devops k8s deploy-stack` applies
    the files of `MANIFESTS_BY_STACK`. A file in one list and not in the other is applied by one
    path and not by the other."""
    files = sorted(
        path.name for path in CRAWL4AI_DIR.glob("*.yaml") if path.name != "kustomization.yaml"
    )
    inner = yaml.safe_load((CRAWL4AI_DIR / "kustomization.yaml").read_text(encoding="utf-8"))
    outer = yaml.safe_load((K8S / "devops" / "kustomization.yaml").read_text(encoding="utf-8"))
    stack = sorted(
        path.name for path in PRODUCT_MANIFESTS_BY_STACK["devops"] if path.parent.name == "crawl4ai"
    )

    assert (sorted(inner["resources"]), "crawl4ai" in outer["resources"], stack) == (
        files,
        True,
        files,
    )
