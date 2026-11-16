"""The Loki pattern ingester is on (#5260)."""

from __future__ import annotations

import pytest
import yaml

from tests.support.helm import helm
from tests.support.paths import REPO_ROOT

VALUES = REPO_ROOT / "k8s/logging/loki-values.yaml"
CHART = "loki"
CHART_REPO = "https://grafana-community.github.io/helm-charts"
CHART_VERSION = "21.2.3"


@pytest.mark.live("helm")
def test_the_loki_config_enables_the_pattern_ingester() -> None:
    """Chart 21.2.3 writes `pattern_ingester.enabled` into the Loki configuration (#5260)."""
    result = helm(
        "template",
        "loki",
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
    (config,) = (
        doc
        for doc in documents
        if doc.get("kind") == "ConfigMap" and "config.yaml" in doc.get("data", {})
    )
    loki = (
        yaml.safe_load(config["data"]["config.yaml"]) if "config.yaml" in config["data"] else None
    )
    assert loki is not None
    assert loki["pattern_ingester"]["enabled"] is True
