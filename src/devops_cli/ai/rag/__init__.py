"""Retrieval-Augmented Generation (RAG) module for devops-cli."""

from __future__ import annotations

from devops_cli.ai.rag.chunker import SemanticChunker
from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError, OllamaEmbeddingModel
from devops_cli.ai.rag.indexer import WorkspaceIndexer, resolve_qdrant_client
from devops_cli.ai.rag.investigator import (
    format_rag_investigation_for_prompt,
    investigate_rag_context,
)
from devops_cli.ai.rag.models import CodeChunk, IndexStats, RAGContext, SearchResult
from devops_cli.ai.rag.qdrant import QdrantClient, QdrantClientError
from devops_cli.ai.rag.retriever import SemanticRetriever

__all__ = [
    "CodeChunk",
    "EmbeddingsEngine",
    "EmbeddingsError",
    "IndexStats",
    "OllamaEmbeddingModel",
    "QdrantClient",
    "QdrantClientError",
    "RAGContext",
    "SearchResult",
    "SemanticChunker",
    "SemanticRetriever",
    "WorkspaceIndexer",
    "format_rag_investigation_for_prompt",
    "investigate_rag_context",
    "resolve_qdrant_client",
]
