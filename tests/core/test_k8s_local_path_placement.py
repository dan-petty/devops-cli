"""Pods on local-path volumes keep off the control-plane node (#1634).

Both StorageClasses of the cluster, `local-path` and `fast-nvme`, use the local-path provisioner.
It binds a volume on the node where the first pod of its claim runs (`WaitForFirstConsumer`), and
the volume then holds each later pod of that claim on the same node. The control-plane node keeps
its volumes under its NVMe base directory `/mnt/nvme-storage/k8s`, which the ConfigMap
`local-path-config` sets, and a pod may run on that node when its volume path is under that
directory. This check reads files only, so it cannot know the directory that the provisioner picks
for a new volume. Each pod that mounts a claim therefore requires a node without the control-plane
label: the term `node-role.kubernetes.io/control-plane` `DoesNotExist` in every term of its
required node affinity.

The checks read files only and render no chart. `CHART_CLAIMS` names, for each chart that an
Argo CD Application installs, which values turn on a claim and where the values set the affinity
of the pod that mounts it. A chart, or a chart version, that an Application pins and `CHART_CLAIMS`
does not name fails the test, so a new chart states its claims and a chart bump reads them again.
A CloudNativePG Cluster whose storage class is absent or is `local-path` or `fast-nvme` is a pod on
a claim, and the check reads its affinity from `spec.affinity`; a Cluster of another class fails the
check. A pod that must stay on the control-plane node is in `_CONTROL_PLANE_CLAIM_EXEMPTIONS`, with
its reason and the item that moves its volume and removes the entry.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import pytest

from tests.support.k8s_tree import chart_values, manifests, pinned_charts, pod_spec, value_at

CONTROL_PLANE_LABEL = "node-role.kubernetes.io/control-plane"
OFF_CONTROL_PLANE = {"key": CONTROL_PLANE_LABEL, "operator": "DoesNotExist"}
# The API group of the CloudNativePG operator, which runs the PostgreSQL databases.
CNPG_GROUP = "postgresql.cnpg.io"
# The storage classes that the local-path provisioner binds. A Cluster that names no class gets the
# default class, `local-path`.
LOCAL_PATH_STORAGE_CLASSES = frozenset({"local-path", "fast-nvme"})
# The reference to an item of the repository, as an exemption states it.
ISSUE_REFERENCE = re.compile(r"#\d+")


@dataclass(frozen=True)
class Exemption:
    """A pod on a local-path claim that may run on the control-plane node.

    `removed_by` names the item that moves the volume and then adds the affinity. An entry with no
    such item fails the check.
    """

    reason: str
    removed_by: str


# The pods on a local-path claim that may run on the control-plane node, each with its reason and
# the item that removes its entry. A key is `<values file>:<pod>` for a chart pod or
# `<manifest>:<kind>/<name>` for a manifest pod.
_CONTROL_PLANE_CLAIM_EXEMPTIONS: dict[str, Exemption] = {
    # #3803 moves the volume of this Cluster to a worker node and then adds the affinity.
    "k8s/mattermost/database.yaml:Cluster/mattermost-db": Exemption(
        reason=(
            "The claim of the database is on the control-plane node, and the pod stays Pending with "
            "the affinity."
        ),
        removed_by="#3803 moves the volume to a worker node and then adds the affinity.",
    ),
    # #1635 added this Cluster and no open item moves its volume, so #3782 splits the move into the
    # follow-up item that this entry names.
    "k8s/llm/gateway-db.yaml:Cluster/llm-gateway-db": Exemption(
        reason=(
            "The claim of the gateway database is on the control-plane node, and the pod stays "
            "Pending with the affinity."
        ),
        removed_by=(
            "The follow-up item `fix(k8s): move the gateway database off the control-plane node`, "
            "split from #3782, moves the volume and then adds the affinity."
        ),
    ),
}


@dataclass(frozen=True)
class ClaimSite:
    """One pod of a chart that mounts a claim when its values turn the claim on."""

    pod: str
    claims: Callable[[dict[str, Any]], bool]
    affinity: str


def _on(*switches: tuple[str, Any]) -> Callable[[dict[str, Any]], bool]:
    """A claim that is on when every switch is truthy; each switch has the chart's default."""
    return lambda values: all(value_at(values, path, default) for path, default in switches)


def _loki_mode(values: dict[str, Any]) -> bool:
    """Loki's single binary mounts a claim in Monolithic mode, the mode of the
    grafana-community chart.

    The other modes run write and backend StatefulSets with claims of their own, which this table
    does not name, so the test fails on them until it does.
    """
    mode = value_at(values, "deploymentMode", "Monolithic")
    if mode != "Monolithic":
        pytest.fail(f"Loki deploymentMode {mode}: name its claims in CHART_CLAIMS")
    return bool(value_at(values, "singleBinary.persistence.enabled", True))


def test_loki_mode_rejects_the_old_name() -> None:
    """The deprecated SingleBinary name is not the mode the values use."""
    with pytest.raises(pytest.fail.Exception, match="Loki deploymentMode SingleBinary"):
        _loki_mode({"deploymentMode": "SingleBinary"})


def test_loki_mode_accepts_the_current_name() -> None:
    """Monolithic with persistence on mounts a claim."""
    assert _loki_mode({"deploymentMode": "Monolithic"}) is True


def _alloy_collectors(values: dict[str, Any]) -> tuple[ClaimSite, ...]:
    """Each k8s-monitoring Alloy collector whose controller has claim templates."""
    collectors = value_at(values, "collectors", {}) or {}
    return tuple(
        ClaimSite(
            f"collectors.{name}",
            _on((f"collectors.{name}.controller.volumeClaimTemplates", None)),
            f"collectors.{name}.controller.affinity",
        )
        for name in collectors
    )


# The claims of each chart an Application installs, read from the chart's own values.yaml. The key
# is the chart and the version that the entry was read from: a chart release can move the value that
# sets a claim, so a chart bump fails until a person reads the entry again. A callable entry reads
# the sites from the values.
CHART_CLAIMS: dict[
    tuple[str, str],
    tuple[ClaimSite, ...] | Callable[[dict[str, Any]], tuple[ClaimSite, ...]],
] = {
    ("argo-cd", "10.18.0"): (),
    ("argo-workflows", "2.0.18"): (),
    ("argocd-image-updater", "1.4.2"): (),
    ("cert-manager", "v1.21.3"): (),
    ("cloudnative-pg", "0.29.1"): (),
    ("dcgm-exporter", "4.8.4"): (),
    # Chart 12.7.0 turns persistence on by default; 13.x turns it off.
    ("gitea", "12.7.0"): (ClaimSite("gitea", _on(("persistence.enabled", True)), "affinity"),),
    ("opentelemetry-collector", "0.178.3"): (),
    ("plugin-barman-cloud", "0.9.0"): (),
    ("prometheus-operator-crds", "33.0.2"): (),
    ("grafana", "14.4.1"): (ClaimSite("grafana", _on(("persistence.enabled", False)), "affinity"),),
    ("k8s-monitoring", "4.6.1"): _alloy_collectors,
    ("loki", "21.2.3"): (ClaimSite("singleBinary", _loki_mode, "singleBinary.affinity"),),
    ("mattermost-operator", "1.0.5"): (),
    ("open-webui", "18.3.0"): (
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
    ("prometheus", "29.47.2"): (
        ClaimSite("server", _on(("server.persistentVolume.enabled", True)), "server.affinity"),
        ClaimSite(
            "alertmanager",
            _on(("alertmanager.enabled", True), ("alertmanager.persistence.enabled", True)),
            "alertmanager.affinity",
        ),
    ),
    ("pyroscope", "2.4.3"): (
        ClaimSite("pyroscope", _on(("pyroscope.persistence.enabled", False)), "pyroscope.affinity"),
    ),
    # The chart's StatefulSet always has the claim template `qdrant-storage`.
    ("qdrant", "1.20.2"): (ClaimSite("qdrant", lambda values: True, "affinity"),),
    ("tempo", "3.2.1"): (ClaimSite("tempo", _on(("persistence.enabled", False)), "affinity"),),
    ("traefik", "42.3.2"): (ClaimSite("traefik", _on(("persistence.enabled", False)), "affinity"),),
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
        "k8s/devops/roadmap-service/cronjob-planner-run.yaml:CronJob/devops-cli-planner-run",
        "k8s/devops/roadmap-service/deployment.yaml:Deployment/roadmap-service",
        "k8s/devops/renovate/cronjob.yaml:CronJob/renovate",
        "k8s/llm/gateway-db.yaml:Cluster/llm-gateway-db",
        "k8s/llm/valkey-runs.yaml:Deployment/valkey-runs",
        "k8s/mattermost/database.yaml:Cluster/mattermost-db",
    }
)


def keeps_off_the_control_plane(affinity: Any) -> bool:
    """Every term of the required node affinity holds the control-plane `DoesNotExist` term.

    The terms of `nodeSelectorTerms` are ORed, so one term without it admits the node.
    """
    terms = value_at(
        affinity, "nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms"
    )
    return bool(terms) and all(
        OFF_CONTROL_PLANE in (term.get("matchExpressions") or []) for term in terms
    )


def _chart_sites(chart: str, values: dict[str, Any]) -> tuple[ClaimSite, ...]:
    """The claim sites of a chart for these values."""
    (sites,) = (sites for (name, _), sites in CHART_CLAIMS.items() if name == chart)
    return sites(values) if callable(sites) else sites


def _chart_pods() -> dict[str, Any]:
    """Each chart pod that mounts a claim, keyed `<values file>:<pod>`, with its affinity."""
    return {
        f"{relative}:{site.pod}": value_at(values, site.affinity)
        for chart, relative, values in chart_values()
        for site in _chart_sites(chart, values)
        if site.claims(values)
    }


def _cluster_pod(relative: str, document: dict[str, Any]) -> tuple[str, Any] | None:
    """The key and the affinity of a CloudNativePG Cluster that stores its data on a local-path
    claim, or None for another document.

    The operator makes a claim from `spec.storage` and mounts it in the database pods, and it
    applies `spec.affinity` to those pods, so a Cluster is a pod on a claim like a workload. The
    key has the form `<file>:<kind>/<name>`, the form of a workload key. A Cluster whose storage
    class is neither absent nor one of `LOCAL_PATH_STORAGE_CLASSES` fails the check, because no
    check here covers the provisioner of another class.
    """
    if not str(document.get("apiVersion", "")).startswith(f"{CNPG_GROUP}/"):
        return None
    spec = document.get("spec") or {}
    storage = spec.get("storage")
    if not storage:
        return None
    key = f"{relative}:{document['kind']}/{document['metadata']['name']}"
    storage_class = storage.get("storageClass")
    if storage_class is not None and storage_class not in LOCAL_PATH_STORAGE_CLASSES:
        pytest.fail(
            f"{key} names the storage class {storage_class}: the check covers "
            f"{sorted(LOCAL_PATH_STORAGE_CLASSES)}, so move its claim to one of them"
        )
    return key, spec.get("affinity")


def _manifest_pods() -> dict[str, Any]:
    """Each manifest pod that mounts a claim, keyed `<file>:<kind>/<name>`, with its affinity."""
    documents = list(manifests())
    claims = {
        (document["metadata"].get("namespace"), document["metadata"]["name"])
        for _, document in documents
        if document["kind"] == "PersistentVolumeClaim"
    }
    pods: dict[str, Any] = {}
    for relative, document in documents:
        cluster = _cluster_pod(relative, document)
        if cluster is not None:
            key, affinity = cluster
            pods[key] = affinity
            continue
        pod = pod_spec(document)
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


def _cluster(affinity: Any, storage_class: str | None = "local-path") -> dict[str, Any]:
    """A CloudNativePG Cluster document that stores its data on a claim, with this affinity and
    storage class; no class when None."""
    storage: dict[str, Any] = {"size": "1Gi"}
    if storage_class is not None:
        storage["storageClass"] = storage_class
    return {
        "apiVersion": "postgresql.cnpg.io/v1",
        "kind": "Cluster",
        "metadata": {"name": "example-db", "namespace": "example"},
        "spec": {
            "instances": 1,
            "storage": storage,
            "affinity": affinity,
        },
    }


@pytest.mark.parametrize(
    ("affinity", "keeps_off"),
    [
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
    ],
    ids=["pod-anti-affinity", "required"],
)
def test_a_cluster_on_a_claim_is_a_pod_that_keeps_off_the_control_plane(
    affinity: Any, keeps_off: bool
) -> None:
    """The operator applies `spec.affinity` of a Cluster to its database pod, so a Cluster that
    stores its data on a claim takes the same check as a workload pod."""
    name, cluster_affinity = _cluster_pod("k8s/llm/database.yaml", _cluster(affinity))
    assert (name, keeps_off_the_control_plane(cluster_affinity)) == (
        "k8s/llm/database.yaml:Cluster/example-db",
        keeps_off,
    )


@pytest.mark.parametrize("storage_class", [None, "local-path", "fast-nvme"])
def test_a_cluster_on_a_local_path_class_is_a_pod_on_a_claim(
    storage_class: str | None,
) -> None:
    """A Cluster on a local-path class, or with no class of its own, keeps its data on a claim."""
    assert _cluster_pod("k8s/llm/database.yaml", _cluster(None, storage_class)) == (
        "k8s/llm/database.yaml:Cluster/example-db",
        None,
    )


def test_a_cluster_of_another_storage_class_fails_the_check() -> None:
    """The check covers the local-path provisioner only, so a Cluster of another class fails, and
    the failure names its key."""
    with pytest.raises(pytest.fail.Exception, match=r"k8s/llm/database\.yaml:Cluster/example-db"):
        _cluster_pod("k8s/llm/database.yaml", _cluster(None, "gp3"))


def test_a_cluster_without_storage_is_no_pod_on_a_claim() -> None:
    """A Cluster with no `spec.storage` keeps no data on a claim, so no check applies."""
    document = _cluster(None)
    del document["spec"]["storage"]
    assert _cluster_pod("k8s/llm/database.yaml", document) is None


def test_the_claim_table_names_each_chart_at_the_version_that_an_application_pins() -> None:
    """A chart release can move the value that sets a claim, as Loki 20.0.2 did (#1632). An entry
    names the version that it was read from, so a bump fails until a person reads it again. A chart
    with no entry could mount a claim that no check sees."""
    assert sorted(pinned_charts() ^ CHART_CLAIMS.keys(), key=str) == []


def test_every_chart_pod_on_a_claim_keeps_off_the_control_plane_node() -> None:
    """Each chart pod that mounts a claim requires a node without the control-plane label."""
    pods = _chart_pods()
    assert (
        sorted(EXPECTED_CHART_PODS - pods.keys()),
        sorted(
            pod
            for pod, affinity in pods.items()
            if pod not in _CONTROL_PLANE_CLAIM_EXEMPTIONS
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
            if pod not in _CONTROL_PLANE_CLAIM_EXEMPTIONS
            and not keeps_off_the_control_plane(affinity)
        ),
    ) == ([], [])


def test_every_exemption_names_a_pod_on_a_claim_that_stays_on_any_node() -> None:
    """An exemption names a pod the checks find, and that pod does not keep off the node yet.

    A stale entry, for a pod that has gone or that has the affinity, would hide a later change.
    Each entry states its reason.
    """
    pods = _chart_pods() | _manifest_pods()
    assert (
        sorted(
            exempt
            for exempt, entry in _CONTROL_PLANE_CLAIM_EXEMPTIONS.items()
            if exempt not in pods or keeps_off_the_control_plane(pods[exempt]) or not entry.reason
        )
        == []
    )


def _exemptions_without_an_item(
    exemptions: Mapping[str, Exemption],
) -> list[str]:
    """The keys of the exemptions that name no item, sorted."""
    return sorted(
        exempt
        for exempt, entry in exemptions.items()
        if not ISSUE_REFERENCE.search(entry.removed_by)
    )


def test_every_exemption_names_the_item_that_removes_it() -> None:
    """Each exemption names the item that moves its volume and then adds the affinity.

    An entry with no item would keep a database volume on the root disk of the node that also runs
    the API server, with no item that removes it.
    """
    assert _exemptions_without_an_item(_CONTROL_PLANE_CLAIM_EXEMPTIONS) == []


def test_an_exemption_with_no_item_fails_the_check() -> None:
    """An entry with no removing item fails the check, and the failure names its claim."""
    exemptions = {"k8s/llm/gateway-db.yaml:Cluster/llm-gateway-db": Exemption("A reason.", "")}
    assert _exemptions_without_an_item(exemptions) == [
        "k8s/llm/gateway-db.yaml:Cluster/llm-gateway-db"
    ]
