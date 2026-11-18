"""Test helpers for Renovate manifests (#6020)."""

from __future__ import annotations

import yaml

from tests.support.paths import REPO_ROOT

RENOVATE_CONFIGMAP_PATH = REPO_ROOT / "k8s" / "devops" / "renovate" / "configmap.yaml"


def renovate_configmap_data() -> dict[str, str]:
    """Return the data dictionary of ConfigMap renovate-config."""
    document = yaml.safe_load(RENOVATE_CONFIGMAP_PATH.read_text(encoding="utf-8"))
    return document["data"]
