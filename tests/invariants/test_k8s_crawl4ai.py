"""The Crawl4AI manifests under `k8s/devops/crawl4ai/`: what the committed files must hold (#3884)."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

import pytest
import yaml

from devops_cli.commands.k8s.stack_lifecycle import MANIFESTS_BY_STACK
from devops_cli.k8s.image_pins import names_latest
from tests.support.k8s_tree import K8S, manifests, pod_spec
from tests.support.paths import REPO_ROOT

CRAWL4AI_DIR = K8S / "devops" / "crawl4ai"
IMAGE_PATTERN = re.compile(r"^unclecode/crawl4ai:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}$")
# The upstream tmpfs paths of its compose file, which a read-only root needs as volumes.
_POD_ROOT = PurePosixPath("/")  # the root of the pod, not a path of this host
WRITABLE_PATHS = (
    str(_POD_ROOT / "tmp"),
    "/var/lib/redis",
    "/var/lib/crawl4ai/outputs",
    "/home/appuser/.crawl4ai",
    "/home/appuser/.cache/url_seeder",
    "/home/appuser/.gunicorn",
)
SHM_PATH = str(_POD_ROOT / "dev" / "shm")
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


def test_the_image_names_a_release_tag_and_its_digest() -> None:
    """A digest alone hides the release from a reader, and a tag alone can move. The pin names
    both, and Renovate bumps both together."""
    image = _container()["image"]

    assert (bool(IMAGE_PATTERN.match(image)), names_latest(image)) == (True, False)


def test_the_deployment_runs_one_pod_that_a_rollout_replaces_before_it_starts_another() -> None:
    """A second pod during a rollout would double the memory of Chromium."""
    spec = _object("Deployment", "crawl4ai")["spec"]

    assert (spec["replicas"], spec["strategy"]) == (1, {"type": "Recreate"})


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


def test_the_writable_paths_are_empty_directories_and_dev_shm_is_memory() -> None:
    """The root file system is read-only, so the six paths that the upstream compose file mounts as
    tmpfs are volumes, and Chromium gets 1 Gi of shared memory at `/dev/shm`."""
    pod = _pod()
    mounts = {mount["mountPath"]: mount["name"] for mount in _container()["volumeMounts"]}
    volumes = {volume["name"]: volume["emptyDir"] for volume in pod["volumes"]}

    assert (
        sorted(mounts),
        {volumes[mounts[path]].get("medium") for path in WRITABLE_PATHS},
        volumes[mounts[SHM_PATH]],
    ) == (
        sorted([*WRITABLE_PATHS, SHM_PATH]),
        {None},
        {"medium": "Memory", "sizeLimit": "1Gi"},
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


def test_the_probes_read_health_and_the_startup_probe_waits_for_chromium() -> None:
    """`/health` is the only route that needs no token. The start window is at least three
    minutes, because supervisord starts Redis, the app and the browser pool, and the first pull of
    a 2.3 GB image is not part of it."""
    container = _container()
    startup = container["startupProbe"]

    assert (
        container["readinessProbe"]["httpGet"],
        startup["httpGet"],
        startup["periodSeconds"] * startup["failureThreshold"] >= 180,
        "livenessProbe" in container,
    ) == (
        {"path": "/health", "port": 11235},
        {"path": "/health", "port": 11235},
        True,
        False,
    )


def test_the_container_has_requests_and_limits() -> None:
    """The first limits follow the upstream compose file (4 Gi of memory) and are measured later."""
    resources = _container()["resources"]

    assert resources == {
        "requests": {"cpu": "500m", "memory": "1Gi", "ephemeral-storage": "512Mi"},
        "limits": {"cpu": "2", "memory": "4Gi", "ephemeral-storage": "2Gi"},
    }


def test_the_service_is_a_cluster_ip_on_11235_for_the_pod() -> None:
    spec = _object("Service", "crawl4ai")["spec"]

    assert (
        spec["type"],
        spec["selector"],
        [(p["port"], p["targetPort"]) for p in spec["ports"]],
    ) == (
        "ClusterIP",
        {"app.kubernetes.io/name": "crawl4ai"},
        [(11235, 11235)],
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
        path.name for path in MANIFESTS_BY_STACK["devops"] if path.parent.name == "crawl4ai"
    )

    assert (sorted(inner["resources"]), "crawl4ai" in outer["resources"], stack) == (
        files,
        True,
        files,
    )


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        ("Deployment", "crawl4ai"),
        ("Service", "crawl4ai"),
        ("NetworkPolicy", "crawl4ai-perimeter"),
        ("NetworkPolicy", "roadmap-service-to-crawl4ai"),
    ],
)
def test_each_object_is_in_namespace_devops_and_part_of_the_stack(kind: str, name: str) -> None:
    metadata = _object(kind, name)["metadata"]

    assert (metadata["namespace"], metadata["labels"]["app.kubernetes.io/part-of"]) == (
        "devops",
        "devops-cli-stack",
    )
