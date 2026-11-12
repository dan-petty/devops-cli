"""The Secret of the Qdrant API key reaches the RAG ingest WorkflowTemplate only (#4180, #5132)."""

from __future__ import annotations

from typing import Any

from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"


QDRANT_SECRET = "qdrant-api-key"


def _secret_names(node: Any) -> set[str]:
    """The name of each Secret that a `secretRef`, a `secretKeyRef` or a `secret` volume of the
    object names, at any depth."""
    names: set[str] = set()
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, field in (
                ("secretRef", "name"),
                ("secretKeyRef", "name"),
                ("secret", "secretName"),
            ):
                if isinstance(current.get(key), dict):
                    names.add(current[key].get(field, ""))
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return names


def check_the_qdrant_secret_reaches_the_ingest_workflow_template_only() -> None:
    """Of the objects that `kubectl apply -k k8s/devops` applies, only WorkflowTemplate rag-ingest
    names the Secret of the Qdrant API key."""
    holders = [
        f"{doc.get('kind', '')}/{doc.get('metadata', {}).get('name', '')}"
        for doc in applied_documents(DEVOPS_DIR)
        if QDRANT_SECRET in _secret_names(doc)
    ]
    assert holders == ["WorkflowTemplate/rag-ingest"], (
        f"Secret {QDRANT_SECRET} is named by {holders}; only WorkflowTemplate/rag-ingest may name it"
    )
