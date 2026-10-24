"""Pods on local-path volumes keep off the control-plane node (#1634).

Both StorageClasses of the cluster, `local-path` and `fast-nvme`, use the local-path provisioner.
It binds a volume on the node where the first pod of its claim runs (`WaitForFirstConsumer`), and
the volume then holds each later pod of that claim on the same node. The root disk of the
control-plane node has the least free space, so each pod that mounts a claim requires a node
without the control-plane label: the term `node-role.kubernetes.io/control-plane` `DoesNotExist`
in every term of its required node affinity.

The checks read files only and render no chart. `CHART_CLAIMS` names, for each chart that an
Argo CD Application installs, which values turn on a claim and where the values set the affinity
of the pod that mounts it. A chart that an Application installs and `CHART_CLAIMS` does not name
fails the test, so a new chart states its claims. A pod that must stay on the control-plane node
is in `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS`, with its reason.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS
from tests.support.paths import REPO_ROOT

K8S = REPO_ROOT / "k8s"
APPLICATIONS = K8S / "argocd" / "apps"
CONTROL_PLANE_LABEL = "node-role.kubernetes.io/control-plane"
OFF_CONTROL_PLANE = {"key": CONTROL_PLANE_LABEL, "operator": "DoesNotExist"}
VALUES_PREFIX = "$values/"

# Where each workload kind keeps its pod spec.
POD_SPEC_PATHS: dict[str, tuple[str, ...]] = {
    "Pod": ("spec",),
    "Deployment": ("spec", "template", "spec"),
    "StatefulSet": ("spec", "template", "spec"),
    "DaemonSet": ("spec", "template", "spec"),
    "ReplicaSet": ("spec", "template", "spec"),
    "Job": ("spec", "template", "spec"),
    "CronJob": ("spec", "jobTemplate", "spec", "template", "spec"),
}


def _get(values: Any, path: str, default: Any = None) -> Any:
    """The value at a dotted path, or the default when a key on the path is absent."""
    for key in path.split("."):
        if not isinstance(values, dict) or key not in values:
            return default
        values = values[key]
    return values


@dataclass(frozen=True)
class ClaimSite:
    """One pod of a chart that mounts a claim when its values turn the claim on."""

    pod: str
    claims: Callable[[dict[str, Any]], bool]
    affinity: str


def _on(*switches: tuple[str, Any]) -> Callable[[dict[str, Any]], bool]:
    """A claim that is on when every switch is truthy; each switch has the chart's default."""
    return lambda values: all(_get(values, path, default) for path, default in switches)


def _loki_mode(values: dict[str, Any]) -> bool:
    """Loki's single binary mounts a claim in SingleBinary mode (chart default: SimpleScalable).

    The other modes run write and backend StatefulSets with claims of their own, which this table
    does not name, so the test fails on them until it does.
    """
    mode = _get(values, "deploymentMode", "SimpleScalable")
    if mode != "SingleBinary":
        pytest.fail(f"Loki deploymentMode {mode}: name its claims in CHART_CLAIMS")
    return bool(_get(values, "singleBinary.persistence.enabled", True))


def _alloy_collectors(values: dict[str, Any]) -> tuple[ClaimSite, ...]:
    """Each k8s-monitoring Alloy collector whose controller has claim templates."""
    collectors = _get(values, "collectors", {}) or {}
    return tuple(
        ClaimSite(
            f"collectors.{name}",
            _on((f"collectors.{name}.controller.volumeClaimTemplates", None)),
            f"collectors.{name}.controller.affinity",
        )
        for name in collectors
    )


# The claims of each chart an Application installs, read from the chart's own values.yaml at the
# version the Application pins. A callable entry reads the sites from the values.
CHART_CLAIMS: dict[
    str, tuple[ClaimSite, ...] | Callable[[dict[str, Any]], tuple[ClaimSite, ...]]
] = {
    "argo-cd": (),
    "argo-workflows": (),
    "argocd-image-updater": (),
    "dcgm-exporter": (),
    # Chart 12.7.0 turns persistence on by default; 13.x turns it off.
    "gitea": (ClaimSite("gitea", _on(("persistence.enabled", True)), "affinity"),),
    "opentelemetry-collector": (),
    "prometheus-operator-crds": (),
    "grafana": (ClaimSite("grafana", _on(("persistence.enabled", False)), "affinity"),),
    "k8s-monitoring": _alloy_collectors,
    "loki": (ClaimSite("singleBinary", _loki_mode, "singleBinary.affinity"),),
    "open-webui": (
        ClaimSite("open-webui", _on(("persistence.enabled", True)), "affinity"),
        ClaimSite(
            "pipelines",
            _on(("pipelines.enabled", True), ("pipelines.persistence.enabled", True)),
            "pipelines.affinity",
        ),
        ClaimSite(
            "ollama",
            _on(("ollama.enabled", True), ("ollama.persistentVolume.enabled", False)),
            "ollama.affinity",
        ),
    ),
    "prometheus": (
        ClaimSite("server", _on(("server.persistentVolume.enabled", True)), "server.affinity"),
        ClaimSite(
            "alertmanager",
            _on(("alertmanager.enabled", True), ("alertmanager.persistence.enabled", True)),
            "alertmanager.affinity",
        ),
    ),
    "pyroscope": (
        ClaimSite("pyroscope", _on(("pyroscope.persistence.enabled", False)), "pyroscope.affinity"),
    ),
    # The chart's StatefulSet always has the claim template `qdrant-storage`.
    "qdrant": (ClaimSite("qdrant", lambda values: True, "affinity"),),
    "tempo": (ClaimSite("tempo", _on(("persistence.enabled", False)), "affinity"),),
    "traefik": (ClaimSite("traefik", _on(("persistence.enabled", False)), "affinity"),),
}

# Pods that the tree must hold, so that a wrong path in the table cannot pass by finding nothing.
EXPECTED_CHART_PODS = frozenset(
    {
        "k8s/gitea/values.yaml:gitea",
        "k8s/llm/values-open-webui.yaml:open-webui",
        "k8s/llm/values-qdrant.yaml:qdrant",
        "k8s/logging/loki-values.yaml:singleBinary",
        "k8s/monitoring/grafana-values.yaml:grafana",
        "k8s/monitoring/prometheus-values.yaml:alertmanager",
        "k8s/monitoring/prometheus-values.yaml:server",
        "k8s/monitoring/pyroscope-values.yaml:pyroscope",
        "k8s/otel/tempo-values.yaml:tempo",
    }
)
EXPECTED_MANIFEST_PODS = frozenset(
    {
        "k8s/devops/roadmap-service/deployment.yaml:Deployment/roadmap-service",
        "k8s/llm/valkey-runs.yaml:Deployment/valkey-runs",
    }
)


def keeps_off_the_control_plane(affinity: Any) -> bool:
    """Every term of the required node affinity holds the control-plane `DoesNotExist` term.

    The terms of `nodeSelectorTerms` are ORed, so one term without it admits the node.
    """
    terms = _get(
        affinity, "nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms"
    )
    return bool(terms) and all(
        OFF_CONTROL_PLANE in (term.get("matchExpressions") or []) for term in terms
    )


@cache
def _documents(path: Path) -> tuple[dict[str, Any], ...]:
    """The mappings a YAML file holds, read once."""
    return tuple(
        document
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(document, dict)
    )


def _chart_values() -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Each chart an Application installs, its values file and the values, in file order."""
    for application_file in sorted(APPLICATIONS.glob("*.yaml")):
        for application in _documents(application_file):
            if application.get("kind") != "Application":
                continue
            spec = application["spec"]
            for source in spec.get("sources") or [spec.get("source")]:
                if not source or "chart" not in source:
                    continue
                for value_file in source.get("helm", {}).get("valueFiles", []):
                    relative = value_file.removeprefix(VALUES_PREFIX)
                    (values,) = _documents(REPO_ROOT / relative)
                    yield source["chart"], relative, values


def _chart_sites(chart: str, values: dict[str, Any]) -> tuple[ClaimSite, ...]:
    """The claim sites of a chart for these values."""
    sites = CHART_CLAIMS[chart]
    return sites(values) if callable(sites) else sites


def _chart_pods() -> dict[str, Any]:
    """Each chart pod that mounts a claim, keyed `<values file>:<pod>`, with its affinity."""
    return {
        f"{relative}:{site.pod}": _get(values, site.affinity)
        for chart, relative, values in _chart_values()
        for site in _chart_sites(chart, values)
        if site.claims(values)
    }


def _value_files() -> frozenset[str]:
    """Every values file an Application names."""
    return frozenset(relative for _, relative, _ in _chart_values())


def _manifests() -> Iterator[tuple[str, dict[str, Any]]]:
    """Each Kubernetes object a manifest under k8s/ declares, with its file."""
    values = _value_files()
    for path in sorted(K8S.rglob("*.y*ml")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative in values:
            continue
        for document in _documents(path):
            if "kind" in document:
                yield relative, document


def _pod_spec(document: dict[str, Any]) -> dict[str, Any] | None:
    """The pod spec of a workload, or None for another kind."""
    path = POD_SPEC_PATHS.get(str(document.get("kind")))
    spec = document
    for key in path or ():
        spec = spec.get(key) or {}
    return spec if path else None


def _manifest_pods() -> dict[str, Any]:
    """Each manifest pod that mounts a claim, keyed `<file>:<kind>/<name>`, with its affinity."""
    documents = list(_manifests())
    claims = {
        (document["metadata"].get("namespace"), document["metadata"]["name"])
        for _, document in documents
        if document["kind"] == "PersistentVolumeClaim"
    }
    pods: dict[str, Any] = {}
    for relative, document in documents:
        pod = _pod_spec(document)
        if pod is None:
            continue
        namespace = document["metadata"].get("namespace")
        mounted = {
            (namespace, volume["persistentVolumeClaim"]["claimName"])
            for volume in pod.get("volumes") or []
            if "persistentVolumeClaim" in volume
        }
        if mounted & claims or document["spec"].get("volumeClaimTemplates"):
            pods[f"{relative}:{document['kind']}/{document['metadata']['name']}"] = pod.get(
                "affinity"
            )
    return pods


@pytest.mark.parametrize(
    ("affinity", "keeps_off"),
    [
        (None, False),
        ({"podAntiAffinity": {}}, False),
        (
            {
                "nodeAffinity": {
                    "requiredDuringSchedulingIgnoredDuringExecution": {
                        "nodeSelectorTerms": [{"matchExpressions": [OFF_CONTROL_PLANE]}]
                    }
                }
            },
            True,
        ),
        (
            {
                "nodeAffinity": {
                    "preferredDuringSchedulingIgnoredDuringExecution": [
                        {"weight": 1, "preference": {"matchExpressions": [OFF_CONTROL_PLANE]}}
                    ]
                }
            },
            False,
        ),
        (
            {
                "nodeAffinity": {
                    "requiredDuringSchedulingIgnoredDuringExecution": {
                        "nodeSelectorTerms": [
                            {"matchExpressions": [OFF_CONTROL_PLANE]},
                            {"matchExpressions": [{"key": "gpu", "operator": "Exists"}]},
                        ]
                    }
                }
            },
            False,
        ),
    ],
    ids=["none", "pod-anti-affinity", "required", "preferred-only", "second-term-admits"],
)
def test_the_placement_check_needs_the_term_in_every_required_term(
    affinity: Any, keeps_off: bool
) -> None:
    """Pin the check on literal affinities: only a required term in every ORed term counts."""
    assert keeps_off_the_control_plane(affinity) is keeps_off


def test_every_chart_an_application_installs_states_its_claims() -> None:
    """A chart with no entry in CHART_CLAIMS could mount a claim that no check sees."""
    assert sorted({chart for chart, _, _ in _chart_values()} - CHART_CLAIMS.keys()) == []


def test_every_chart_pod_on_a_claim_keeps_off_the_control_plane_node() -> None:
    """Each chart pod that mounts a claim requires a node without the control-plane label."""
    pods = _chart_pods()
    assert (
        sorted(EXPECTED_CHART_PODS - pods.keys()),
        sorted(
            pod
            for pod, affinity in pods.items()
            if pod not in CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS
            and not keeps_off_the_control_plane(affinity)
        ),
    ) == ([], [])


def test_every_manifest_pod_on_a_claim_keeps_off_the_control_plane_node() -> None:
    """Each manifest pod that mounts a claim under k8s/ requires a node without the label."""
    pods = _manifest_pods()
    assert (
        sorted(EXPECTED_MANIFEST_PODS - pods.keys()),
        sorted(
            pod
            for pod, affinity in pods.items()
            if pod not in CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS
            and not keeps_off_the_control_plane(affinity)
        ),
    ) == ([], [])


def test_every_exemption_names_a_pod_on_a_claim_that_stays_on_any_node() -> None:
    """An exemption names a pod the checks find, and that pod does not keep off the node yet.

    A stale entry, for a pod that has gone or that has the affinity, would hide a later change.
    """
    pods = _chart_pods() | _manifest_pods()
    assert (
        sorted(
            exempt
            for exempt in CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS
            if exempt not in pods or keeps_off_the_control_plane(pods[exempt])
        )
        == []
    )
