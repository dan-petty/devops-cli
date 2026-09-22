"""Test suite for scoping Kubernetes manifest validation to actual manifests."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.security.kubeconform import (
    _is_manifest_document,
    _validate_single_k8s_file_fallback,
)


def write(tmp_path: Path, name: str, body: str) -> Path:
    """Write a YAML file into the scan root."""
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


# =============================================================================
# What Counts As A Manifest
# =============================================================================


def test_a_document_declaring_apiversion_is_a_manifest() -> None:
    """`apiVersion` is the Kubernetes-specific marker."""
    assert _is_manifest_document({"apiVersion": "v1", "kind": "ConfigMap"}) is True


def test_a_helm_values_file_declaring_kind_is_not_a_manifest() -> None:
    """Charts legitimately expose `kind` as a values key.

    fluent-bit uses it to choose between a DaemonSet and a Deployment, so keying on `kind`
    reports correct values files as broken manifests.
    """
    assert _is_manifest_document({"replicaCount": 1, "kind": "DaemonSet"}) is False


def test_a_plain_configuration_document_is_not_a_manifest() -> None:
    """Most YAML in a repository is not a Kubernetes resource."""
    assert _is_manifest_document({"replicaCount": 1, "image": {"tag": "1.0"}}) is False


def test_a_non_mapping_document_is_not_a_manifest() -> None:
    """A YAML list or scalar cannot be a resource."""
    assert (_is_manifest_document([1, 2]), _is_manifest_document(None)) == (False, False)


# =============================================================================
# Validation
# =============================================================================


def test_a_valid_manifest_produces_no_finding(tmp_path: Path) -> None:
    """The ordinary case."""
    path = write(tmp_path, "cm.yaml", "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: x\n")
    assert _validate_single_k8s_file_fallback(path, tmp_path) is None


def test_a_manifest_missing_kind_is_reported(tmp_path: Path) -> None:
    """Validation must still catch a genuinely malformed manifest."""
    path = write(tmp_path, "broken.yaml", "apiVersion: apps/v1\nmetadata:\n  name: x\n")
    finding = _validate_single_k8s_file_fallback(path, tmp_path)
    assert finding is not None
    assert finding.title == "Invalid Kubernetes manifest schema"


def test_a_helm_values_file_produces_no_finding(tmp_path: Path) -> None:
    """Nine such files were reported as broken manifests, all of them correct.

    Treating the absence of apiVersion and kind as a defect inverted the test: that absence
    is precisely how a non-manifest is recognised, and a validator that flags correct files
    teaches people to ignore it.
    """
    path = write(tmp_path, "values.yaml", "replicaCount: 1\nimage:\n  tag: '1.0'\n")
    assert _validate_single_k8s_file_fallback(path, tmp_path) is None


def test_a_values_file_with_a_kind_key_produces_no_finding(tmp_path: Path) -> None:
    """The case that survived the first fix and forced the discriminator to change."""
    path = write(tmp_path, "fluent-bit-values.yaml", "replicaCount: 1\nkind: DaemonSet\n")
    assert _validate_single_k8s_file_fallback(path, tmp_path) is None


def test_unparseable_yaml_is_reported(tmp_path: Path) -> None:
    """A file that cannot be parsed cannot be validated, and that is worth saying."""
    path = write(tmp_path, "bad.yaml", "a: [unclosed\n")
    finding = _validate_single_k8s_file_fallback(path, tmp_path)
    assert finding is not None
    assert finding.title == "Unparseable YAML document"


def test_a_multi_document_file_validates_every_manifest(tmp_path: Path) -> None:
    """Manifests are commonly concatenated with `---`."""
    path = write(
        tmp_path,
        "multi.yaml",
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: a\n"
        "---\napiVersion: apps/v1\nmetadata:\n  name: b\n",
    )
    finding = _validate_single_k8s_file_fallback(path, tmp_path)
    assert finding is not None


def test_manifests_mixed_with_non_manifests_are_still_validated(tmp_path: Path) -> None:
    """A values document alongside a manifest must not mask the manifest."""
    path = write(
        tmp_path,
        "mixed.yaml",
        "replicaCount: 1\n---\napiVersion: apps/v1\nmetadata:\n  name: b\n",
    )
    assert _validate_single_k8s_file_fallback(path, tmp_path) is not None


def test_an_empty_file_produces_no_finding(tmp_path: Path) -> None:
    """An empty document is not a broken manifest."""
    assert _validate_single_k8s_file_fallback(write(tmp_path, "empty.yaml", ""), tmp_path) is None


@pytest.mark.parametrize(
    "name",
    [
        "values.yaml",
        "values-qdrant.yaml",
        "loki-values.yaml",
        "fluent-bit-values.yaml",
    ],
)
def test_the_repository_helm_values_files_are_clean(name: str) -> None:
    """The nine files this previously flagged are all correct and still present."""
    matches = list(Path("k8s").rglob(name))
    for path in matches:
        assert _validate_single_k8s_file_fallback(path, Path("k8s")) is None, name
