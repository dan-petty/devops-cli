"""Grafana starts when the renderer token is missing (#5200)."""

from __future__ import annotations

from devops_cli.k8s.cluster_secrets import OPTIONAL_FEATURE_SECRETS, load_cluster_secrets_table
from tests.support.paths import FIXTURES


def test_the_optional_feature_secret_is_in_the_cluster_secret_table() -> None:
    """The list names a Secret of the cluster Secret table (#5200)."""
    refs = {secret.ref for secret in load_cluster_secrets_table(k8s_dir=FIXTURES)}

    assert set(OPTIONAL_FEATURE_SECRETS) <= refs
