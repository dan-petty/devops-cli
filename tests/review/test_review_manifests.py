"""Tests for Kubernetes manifest object extraction and key formatting (#1352)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.review.manifests import (
    collect_manifest_objects,
    manifest_object_key,
    read_manifest_objects,
)


def test_manifest_object_key_formats_with_and_without_namespace() -> None:
    """The key builder formats as Kind/namespace/name when namespace is present, and Kind/name when absent."""
    assert manifest_object_key("Deployment", "api", "prod") == "Deployment/prod/api"
    assert manifest_object_key("Deployment", "web") == "Deployment/web"
    assert manifest_object_key("Deployment", "web", "") == "Deployment/web"
    assert manifest_object_key("Deployment", "web", None) == "Deployment/web"
    assert (
        manifest_object_key("  Service  ", "  frontend  ", "  default  ")
        == "Service/default/frontend"
    )
    assert manifest_object_key("ConfigMap", "settings", "   ") == "ConfigMap/settings"


def test_read_manifest_objects_single_and_multi_document() -> None:
    """read_manifest_objects parses single and multi-document YAML manifests."""
    yaml_content = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  namespace: prod
---
apiVersion: v1
kind: Service
metadata:
  name: web-svc
"""
    objects = read_manifest_objects(yaml_content)
    assert objects == {"Deployment/prod/web", "Service/web-svc"}


def test_read_manifest_objects_unwraps_list_items() -> None:
    """read_manifest_objects unwraps List documents and extracts nested items."""
    yaml_content = """
apiVersion: v1
kind: List
items:
  - apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: worker
      namespace: processing
  - apiVersion: v1
    kind: ConfigMap
    metadata:
      name: worker-config
"""
    objects = read_manifest_objects(yaml_content)
    assert objects == {"Deployment/processing/worker", "ConfigMap/worker-config"}


def test_read_manifest_objects_handles_malformed_and_non_k8s_docs() -> None:
    """read_manifest_objects safely ignores non-dict documents, malformed YAML, and missing metadata."""
    assert read_manifest_objects("") == set()
    assert read_manifest_objects("not yaml: [unclosed") == set()
    assert read_manifest_objects("just a string") == set()
    assert read_manifest_objects("---\n- a list item\n- another") == set()
    assert read_manifest_objects("kind: Deployment\nfoo: bar") == set()


def test_collect_manifest_objects_from_paths_and_content_getter(tmp_path: Path) -> None:
    """collect_manifest_objects collects objects across multiple paths with or without a getter."""
    m1 = tmp_path / "deploy.yaml"
    m1.write_text(
        """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
""",
        encoding="utf-8",
    )
    m2 = tmp_path / "service.yaml"
    m2.write_text(
        """
apiVersion: v1
kind: Service
metadata:
  name: api-svc
  namespace: default
""",
        encoding="utf-8",
    )

    objects = collect_manifest_objects([m1, m2])
    assert objects == {"Deployment/api", "Service/default/api-svc"}

    # Using custom content getter
    def _getter(p: str) -> str | None:
        return m1.read_text(encoding="utf-8") if "deploy" in p else None

    getter_objects = collect_manifest_objects(
        ["deploy.yaml", "missing.yaml"], content_getter=_getter
    )
    assert getter_objects == {"Deployment/api"}
