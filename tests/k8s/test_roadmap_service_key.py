"""The roadmap Service uses its own gateway key, not the master key (#3685).

The push writes the key to Secret `roadmap-service-llm-key`, an optional row of the cluster Secret
table.
"""

from __future__ import annotations

from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS


def test_the_key_has_an_optional_cluster_secret_row() -> None:
    row = next(
        secret for secret in CLUSTER_SECRETS if secret.ref == "devops/roadmap-service-llm-key"
    )
    (entry,) = row.entries

    assert (entry.key, entry.required) == ("api-key", False)
