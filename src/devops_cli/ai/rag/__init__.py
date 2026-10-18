"""Retrieval-Augmented Generation (RAG) module for devops-cli."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "CodeChunk",
    "EmbeddingsEngine",
    "EmbeddingsError",
    "IndexStats",
    "LibraryVectorStore",
    "OllamaEmbeddingModel",
    "QdrantClient",
    "QdrantClientError",
    "RAGContext",
    "SearchResult",
    "SemanticChunker",
    "SemanticRetriever",
    "WorkspaceIndexer",
    "ensure_knowledge_base_ready",
    "format_rag_investigation_for_prompt",
    "investigate_rag_context",
    "resolve_qdrant_client",
]

_ATTR_MAP: dict[str, tuple[str, str]] = {
    "CodeChunk": ("devops_cli.ai.rag.models", "CodeChunk"),
    "EmbeddingsEngine": ("devops_cli.ai.rag.embeddings", "EmbeddingsEngine"),
    "EmbeddingsError": ("devops_cli.ai.rag.embeddings", "EmbeddingsError"),
    "IndexStats": ("devops_cli.ai.rag.models", "IndexStats"),
    "LibraryVectorStore": ("devops_cli.ai.rag.library_store", "LibraryVectorStore"),
    "OllamaEmbeddingModel": ("devops_cli.ai.rag.embeddings", "OllamaEmbeddingModel"),
    "QdrantClient": ("devops_cli.ai.rag.qdrant", "QdrantClient"),
    "QdrantClientError": ("devops_cli.ai.rag.qdrant", "QdrantClientError"),
    "RAGContext": ("devops_cli.ai.rag.models", "RAGContext"),
    "SearchResult": ("devops_cli.ai.rag.models", "SearchResult"),
    "SemanticChunker": ("devops_cli.ai.rag.chunker", "SemanticChunker"),
    "SemanticRetriever": ("devops_cli.ai.rag.retriever", "SemanticRetriever"),
    "WorkspaceIndexer": ("devops_cli.ai.rag.indexer", "WorkspaceIndexer"),
    "ensure_knowledge_base_ready": ("devops_cli.ai.rag.kb_sync", "ensure_knowledge_base_ready"),
    "format_rag_investigation_for_prompt": (
        "devops_cli.ai.rag.investigator",
        "format_rag_investigation_for_prompt",
    ),
    "investigate_rag_context": (
        "devops_cli.ai.rag.investigator",
        "investigate_rag_context",
    ),
    "resolve_qdrant_client": ("devops_cli.ai.rag.indexer", "resolve_qdrant_client"),
}


def __getattr__(name: str) -> Any:
    if name in _ATTR_MAP:
        mod_name, attr = _ATTR_MAP[name]
        val = getattr(importlib.import_module(mod_name), attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
