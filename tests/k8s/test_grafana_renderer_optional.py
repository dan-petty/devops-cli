"""Grafana starts when the renderer token is missing (#5200)."""

from __future__ import annotations

import pytest
import yaml

from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS
from tests.support.paths import REPO_ROOT

VALUES = REPO_ROOT / "k8s/monitoring/grafana-values.yaml"
CHART = "grafana"
CHART_REPO = "https://grafana-community.github.io/helm-charts"
CHART_VERSION = "14.4.1"


@pytest.mark.live("helm")
def test_the_grafana_container_reads_the_renderer_token_as_optional() -> None:
    """The chart writes a required secretKeyRef; the values repeat it as optional after it
    (#5200)."""
    from tests.support.helm import helm

    result = helm(
        "template",
        "grafana",
        CHART,
        "--repo",
        CHART_REPO,
        "--version",
        CHART_VERSION,
        "-f",
        VALUES,
    )
    assert result.returncode == 0, result.stderr

    documents = [doc for doc in yaml.safe_load_all(result.stdout) if doc]
    (deployment,) = (
        doc
        for doc in documents
        if doc.get("kind") == "Deployment" and doc["metadata"]["name"] == "grafana"
    )
    container = next(
        item
        for item in deployment["spec"]["template"]["spec"]["containers"]
        if item["name"] == "grafana"
    )
    entries = [
        entry for entry in container["env"] if entry["name"] == "GF_RENDERING_RENDERER_TOKEN"
    ]

    assert len(entries) == 2
    assert entries[-1]["valueFrom"]["secretKeyRef"]["optional"] is True
    assert "optional" not in entries[0]["valueFrom"]["secretKeyRef"]


def test_the_optional_feature_secret_is_in_the_cluster_secret_table() -> None:
    """The list names a Secret of the cluster Secret table (#5200)."""
    from devops_cli.k8s.cluster_secrets import OPTIONAL_FEATURE_SECRETS

    refs = {secret.ref for secret in CLUSTER_SECRETS}

    assert set(OPTIONAL_FEATURE_SECRETS) <= refs
