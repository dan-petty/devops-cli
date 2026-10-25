"""Kubernetes manifest object extraction and key formatting (#1352).

Provides canonical key generation and YAML document parsing for review admission.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def manifest_object_key(kind: str, name: str, namespace: str | None = None) -> str:
    """Build the canonical Kubernetes object key.

    Returns Kind/namespace/name when namespace is present, and Kind/name when absent.
    """
    clean_kind = kind.strip()
    clean_name = name.strip()
    clean_ns = namespace.strip() if namespace else ""
    if clean_ns:
        return f"{clean_kind}/{clean_ns}/{clean_name}"
    return f"{clean_kind}/{clean_name}"


def _extract_doc_objects(doc: Any, objects: set[str]) -> None:
    """Extract Kubernetes object keys from one parsed YAML document into objects."""
    if not isinstance(doc, dict):
        return

    kind = doc.get("kind")
    if (kind == "List" or (isinstance(kind, str) and kind.endswith("List"))) and "items" in doc:
        items = doc.get("items")
        if isinstance(items, list):
            for item in items:
                _extract_doc_objects(item, objects)
        return

    if not kind or not isinstance(kind, str):
        return
    metadata = doc.get("metadata")
    if not isinstance(metadata, dict):
        return
    name = metadata.get("name")
    if not name:
        return
    namespace = metadata.get("namespace")
    clean_ns = str(namespace).strip() if namespace else ""
    objects.add(
        manifest_object_key(
            kind=kind.strip(),
            name=str(name).strip(),
            namespace=clean_ns or None,
        )
    )


def read_manifest_objects(content: str) -> set[str]:
    """Parse YAML content and return all Kubernetes object keys."""
    if not content or not content.strip():
        return set()

    import yaml

    objects: set[str] = set()
    try:
        docs = yaml.safe_load_all(content)
        for doc in docs:
            _extract_doc_objects(doc, objects)
    except yaml.YAMLError as exc:
        logger.debug("Failed to parse YAML manifest stream: %s", exc)
    return objects


def collect_manifest_objects(
    manifest_paths: Iterable[Path | str],
    *,
    content_getter: Callable[[str], str | None] | None = None,
) -> set[str]:
    """Collect Kubernetes object keys across the given manifest file paths."""
    objects: set[str] = set()
    for path in manifest_paths:
        path_str = str(path)
        content: str | None = None
        if content_getter is not None:
            content = content_getter(path_str)
        else:
            p = Path(path)
            if p.is_file():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    logger.debug("Failed to read manifest file %s: %s", path_str, exc)
        if content:
            objects |= read_manifest_objects(content)
    return objects
