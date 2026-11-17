"""Grafana starts when the renderer token is missing (#5200)."""

from __future__ import annotations

from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS


def test_the_optional_feature_secret_is_in_the_cluster_secret_table() -> None:
    """The list names a Secret of the cluster Secret table (#5200)."""
    from devops_cli.k8s.cluster_secrets import OPTIONAL_FEATURE_SECRETS

    refs = {secret.ref for secret in CLUSTER_SECRETS}

    assert set(OPTIONAL_FEATURE_SECRETS) <= refs
