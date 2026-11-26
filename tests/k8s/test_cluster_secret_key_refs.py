"""Tests for secretKeyRef validation against the cluster secrets generator table (#6064)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.k8s import cluster_secrets as _cs

# The Secret table reads the environment tree.
pytestmark = pytest.mark.usefixtures("environment_repo")

check_secret_key_refs: Any = getattr(_cs, "check_secret_key_refs", None)
_check_secret_ref: Any = getattr(_cs, "_check_secret_ref", None)
CLUSTER_SECRETS: Any = getattr(_cs, "CLUSTER_SECRETS", ())
ClusterSecret: Any = getattr(_cs, "ClusterSecret", None)
load_cluster_secrets_table: Any = getattr(
    _cs, "load_cluster_secrets_table", lambda: CLUSTER_SECRETS
)


def test_unknown_credential_key_fails_the_check(tmp_path: Path) -> None:
    """The check SHALL report a failure when a secretKeyRef names a key that the generator table of
    devops k8s push-secrets has no row for (#6064)."""
    assert check_secret_key_refs is not None, "check_secret_key_refs is not implemented"
    assert ClusterSecret is not None, "ClusterSecret is not implemented"

    manifest = tmp_path / "llm" / "values-qdrant.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        """
apiKey:
  secretKeyRef:
    name: qdrant-api-key
    key: read-only-api-key
""",
        encoding="utf-8",
    )

    table_without_read_only = tuple(
        ClusterSecret(
            namespace=s.namespace,
            name=s.name,
            stack=s.stack,
            entries=tuple(e for e in s.entries if e.key != "read-only-api-key"),
            restarts=s.restarts,
            labels=s.labels,
            change_note=s.change_note,
            secret_type=s.secret_type,
        )
        if s.ref == "llm/qdrant-api-key"
        else s
        for s in load_cluster_secrets_table()
    )

    findings = check_secret_key_refs(tmp_path, table=table_without_read_only)

    assert len(findings) == 1
    (finding,) = findings
    assert str(manifest) in finding
    assert "llm/qdrant-api-key" in finding
    assert "read-only-api-key" in finding


def test_known_credential_key_passes_the_check(tmp_path: Path) -> None:
    """The check SHALL pass when each secretKeyRef to a Secret of the generator table names a key
    of that Secret's row (#6064)."""
    assert check_secret_key_refs is not None, "check_secret_key_refs is not implemented"

    manifest = tmp_path / "llm" / "values-qdrant.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        """
---
# empty doc
---
apiKey:
  secretKeyRef:
    name: qdrant-api-key
    key: read-only-api-key
""",
        encoding="utf-8",
    )

    findings = check_secret_key_refs(manifest, table=CLUSTER_SECRETS)
    assert findings == []


def test_check_secret_ref_matches_unique_name_without_namespace(tmp_path: Path) -> None:
    """_check_secret_ref matches a unique secret name when doc_ns is empty (#6064)."""
    assert _check_secret_ref is not None, "_check_secret_ref is not implemented"
    table_list = tuple(load_cluster_secrets_table())
    table_by_ref = {s.ref: s for s in table_list}
    table_by_name: dict[str, list[Any]] = {}
    for s in table_list:
        table_by_name.setdefault(s.name, []).append(s)

    file_path = tmp_path / "values.yaml"
    result = _check_secret_ref(
        "llm-gateway-secrets",
        "master-key",
        "",
        table_by_ref,
        table_by_name,
        file_path,
    )
    assert result is None


def test_secret_outside_the_table_is_skipped(tmp_path: Path) -> None:
    """The check MUST skip a secretKeyRef whose Secret name is not a row of the generator table (#6064)."""
    assert check_secret_key_refs is not None, "check_secret_key_refs is not implemented"

    manifest = tmp_path / "llm" / "gateway" / "deployment.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm
  namespace: llm
spec:
  template:
    spec:
      containers:
        - name: litellm
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: llm-gateway-db-app
                  key: uri
""",
        encoding="utf-8",
    )

    findings = check_secret_key_refs(manifest, table=CLUSTER_SECRETS)
    assert findings == []
