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
is in `_CONTROL_PLANE_CLAIM_EXEMPTIONS`, with its reason.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from tests.support.k8s_tree import chart_values, manifests, pinned_charts, pod_spec, value_at

CONTROL_PLANE_LABEL = "node-role.kubernetes.io/control-plane"
OFF_CONTROL_PLANE = {"key": CONTROL_PLANE_LABEL, "operator": "DoesNotExist"}

# The pods on a local-path claim that may run on the control-plane node, each with its reason. A key
# is `<values file>:<pod>` for a chart pod or `<manifest>:<kind>/<name>` for a manifest pod.
_CONTROL_PLANE_CLAIM_EXEMPTIONS: dict[str, str] = {
    "k8s/logging/loki-values.yaml:singleBinary": (
        "Volume storage-loki-0 is still on the control-plane node; with the affinity, the pod "
        "cannot start until the volume moves (k8s/README.md, Local-Path Volume Placement)."
    ),
    "k8s/monitoring/grafana-values.yaml:grafana": (
        "Volume grafana is still on the control-plane node; with the affinity, the pod cannot "
        "start until the volume moves (k8s/README.md, Local-Path Volume Placement)."
    ),
    "k8s/monitoring/prometheus-values.yaml:server": (
        "Volume prometheus-server is still on the control-plane node; with the affinity, the pod "
        "cannot start until the volume moves (k8s/README.md, Local-Path Volume Placement)."
    ),
}


def test_the_claim_table_names_each_chart_at_the_version_that_an_application_pins() -> None:
    """The CHART_CLAIMS table must name every chart an Application pins, at that version."""
    assert sorted(pinned_charts() ^ CHART_CLAIMS.keys(), key=str) == []


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
    """Loki's single binary mounts a claim in Monolithic mode, the default of the
    grafana-community chart, which also takes SingleBinary as the old name of that mode.

    The other modes run write and backend StatefulSets with claims of their own, which this table
    does not name, so the test fails on them until it does.
    """
    mode = value_at(values, "deploymentMode", "Monolithic")
    if mode not in ("Monolithic", "SingleBinary"):
        pytest.fail(f"Loki deploymentMode {mode}: name its claims in CHART_CLAIMS")
    return bool(value_at(values, "singleBinary.persistence.enabled", True))


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


# The claims of each chart an Application installs, read from the chart's own values.yaml at the
# version the Application pins. A callable entry reads the sites from the values.
# This is a tuple[str, str] key dict where the first element is chart name and second is version
CHART_CLAIMS: dict[
    tuple[str, str], tuple[ClaimSite, ...] | Callable[[dict[str, Any]], tuple[ClaimSite, ...]]
] = {
    # Initialize with empty entries to match pinned charts structure - will be populated by tests
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
    terms = value_at(
        affinity, "nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms"
    )
    return bool(terms) and all(
        OFF_CONTROL_PLANE in (term.get("matchExpressions") or []) for term in terms
    )


def _chart_sites(chart: str, values: dict[str, Any]) -> tuple[ClaimSite, ...]:
    """The claim sites of a chart for these values.

    This function finds the correct versioned entry in CHART_CLAIMS by chart name only,
    since we're looking up based on the chart being processed.
    """
    # Find the first entry that matches this chart (ignoring version)
    matching_entry = None
    for (entry_chart, _), entry_value in CHART_CLAIMS.items():
        if entry_chart == chart:
            matching_entry = entry_value
            break

    if matching_entry is None:
        pytest.fail(f"Chart {chart} not found in CHART_CLAIMS table")

    return matching_entry(values) if callable(matching_entry) else matching_entry


def _chart_pods() -> dict[str, Any]:
    """Each chart pod that mounts a claim, keyed `<values file>:<pod>`, with its affinity."""
    return {
        f"{relative}:{site.pod}": value_at(values, site.affinity)
        for chart, relative, values in chart_values()
        for site in _chart_sites(chart, values)
        if site.claims(values)
    }


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


def test_every_chart_an_application_installs_states_its_claims() -> None:
    """A chart with no entry in CHART_CLAIMS could mount a claim that no check sees."""
    assert sorted({chart for chart, _, _ in chart_values()} - CHART_CLAIMS.keys()) == []


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
    """
    pods = _chart_pods() | _manifest_pods()
    assert (
        sorted(
            exempt
            for exempt in _CONTROL_PLANE_CLAIM_EXEMPTIONS
            if exempt not in pods or keeps_off_the_control_plane(pods[exempt])
        )
        == []
    )
