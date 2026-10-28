"""Test suite for scoping Kubernetes manifest validation to actual manifests."""

from __future__ import annotations

from devops_cli.security.kubeconform import _is_manifest_document

# =============================================================================
# What Counts As A Manifest
# =============================================================================


def test_a_document_declaring_apiversion_is_a_manifest() -> None:
    """`apiVersion` is the Kubernetes-specific marker."""
    assert _is_manifest_document({"apiVersion": "v1", "kind": "ConfigMap"}) is True


def test_a_helm_values_file_declaring_kind_is_not_a_manifest() -> None:
    """Charts legitimately expose `kind` as a values key."""
    assert _is_manifest_document({"replicaCount": 1, "kind": "DaemonSet"}) is False


def test_a_plain_configuration_document_is_not_a_manifest() -> None:
    """Most YAML in a repository is not a Kubernetes resource."""
    assert _is_manifest_document({"replicaCount": 1, "image": {"tag": "1.0"}}) is False


def test_a_non_mapping_document_is_not_a_manifest() -> None:
    """A YAML list or scalar cannot be a resource."""
    assert (_is_manifest_document([1, 2]), _is_manifest_document(None)) == (False, False)
