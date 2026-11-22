"""The SearXNG service (#3924): its row of the cluster Secret table.

The form of the manifests under `k8s/devops/searxng/` is the work of the `k8s` row of `devops ci`
and of kube-linter, and `devops k8s searxng-check` checks the live service: its engines, its JSON
reply and the engines that stay off. No test asserts a value of the manifests (#6060).
"""

from __future__ import annotations

from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS


def test_the_secret_row_feeds_the_variable_and_restarts_the_deployment() -> None:
    """The value lives in the keyring alone (no Settings option reads it), and a first push
    generates 64 hex characters."""
    (row,) = [secret for secret in CLUSTER_SECRETS if secret.ref == "devops/searxng"]
    (entry,) = row.entries
    generator = entry.generator
    assert generator is not None

    assert (
        entry.key,
        entry.source.label,
        (generator.encoding, generator.nbytes),
        [str(workload) for workload in row.restarts],
        row.stack,
    ) == (
        "SEARXNG_SECRET",
        "keyring searxng_secret_key",
        ("hex", 32),
        ["deployment/searxng"],
        "devops",
    )


def test_the_metrics_secret_row() -> None:
    """The OpenMetrics scrape reads a basic-auth Secret: user `searxng`, password from the
    keyring entry `searxng_metrics_password`, and a push restarts the pod that reads it."""
    (row,) = [secret for secret in CLUSTER_SECRETS if secret.ref == "devops/searxng-metrics-auth"]
    username, password = row.entries

    assert (
        row.stack,
        row.secret_type,
        (username.key, username.source.label),
        (password.key, password.source.label),
        [str(workload) for workload in row.restarts],
    ) == (
        "devops",
        "kubernetes.io/basic-auth",
        ("username", "literal"),
        ("password", "keyring searxng_metrics_password"),
        ["deployment/searxng"],
    )
