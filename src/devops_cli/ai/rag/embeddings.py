"""Embeddings engine for Ollama and OpenAI-compatible providers."""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import as_completed
from typing import Any

import httpx2

from devops_cli.config.defaults import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_RAG_EMBEDDING_MODEL,
)
from devops_cli.config.settings import AIConfig
from devops_cli.http.validation import validate_service_url
from devops_cli.telemetry import (
    ContextPropagatingThreadPoolExecutor as ThreadPoolExecutor,
)
from devops_cli.telemetry import (
    trace_span,
)

logger = logging.getLogger(__name__)


class EmbeddingsError(RuntimeError):
    """Raised when embeddings generation fails across all endpoints."""


class EmbeddingsEngine:
    """Generates dense vector embeddings using Ollama or OpenAI endpoints."""

    def __init__(
        self,
        ai_config: AIConfig | None = None,
        *,
        api_key: str | None = None,
        timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    ) -> None:
        base_config = ai_config or AIConfig()
        self.ai_config = base_config.for_task("embedding")
        self.api_key = api_key
        self.timeout = min(timeout, 120.0)
        self.model = self.ai_config.rag.embedding_model or DEFAULT_RAG_EMBEDDING_MODEL
        self._dimension: int | None = None

    def _infer_default_dimension(self) -> int:
        """Infer default embedding dimension from active model name."""
        if self._dimension is not None:
            return self._dimension
        m = self.model.lower()
        if "qwen" in m:
            return 1024
        if "nomic" in m or "bge-base" in m:
            return 768
        if "text-embedding-3-small" in m:
            return 1536
        if "text-embedding-3-large" in m:
            return 3072
        if "all-minilm" in m or "bge-small" in m:
            return 384
        return 1024

    def embed_texts(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        """Generate vector embeddings for a list of text strings."""
        if not texts:
            return []

        with trace_span(
            "ai.rag.embed_texts",
            attributes={
                "rag.texts_count": len(texts),
                "rag.model": str(self.model),
                "rag.provider": str(self.ai_config.provider),
                "rag.is_query": is_query,
            },
        ):
            # Model-aware task prefixing for asymmetric models
            prefixed_texts = self._apply_model_prefix(texts, is_query=is_query)

            provider = self.ai_config.provider.lower()
            api_base = self.ai_config.api_base_url or ""
            if provider in ("openai", "copilot"):
                return self._embed_openai(prefixed_texts)
            if provider == "ollama" or (not provider and ":11434" in api_base):
                return self._embed_ollama(prefixed_texts)
            if self.ai_config.ollama_urls:
                return self._embed_ollama(prefixed_texts)
            return self._deterministic_fallback(prefixed_texts)

    def embed_query(self, text: str) -> list[float]:
        """Generate vector embedding for a single search query."""
        results = self.embed_texts([text], is_query=True)
        if not results:
            raise EmbeddingsError(f"Failed to generate embedding for query: {text[:50]}")
        return results[0]

    def _apply_model_prefix(self, texts: list[str], *, is_query: bool) -> list[str]:
        """Apply asymmetric task prefix based on embedding model architecture."""
        m = self.model.lower()
        if "nomic" in m:
            prefix = "search_query: " if is_query else "search_document: "
            return [
                t if t.startswith(("search_query: ", "search_document: ")) else f"{prefix}{t}"
                for t in texts
            ]
        elif "qwen" in m or "bge" in m or "e5" in m:
            prefix = "query: " if is_query else "passage: "
            return [t if t.startswith(("query: ", "passage: ")) else f"{prefix}{t}" for t in texts]
        return texts

    def _fetch_fallback_single_embeddings(
        self, client: httpx2.Client, base_url: str, batch_texts: list[str]
    ) -> list[list[float]] | None:
        """Sequential single-prompt embedding fallback for legacy Ollama versions."""
        embs_fallback: list[list[float]] = []
        for t in batch_texts:
            endpoint = f"{base_url}/api/embeddings"
            payload = {"model": self.model, "prompt": t}
            res = client.post(endpoint, json=payload)
            if res.status_code != 200:
                return None
            single_emb = res.json().get("embedding", [])
            if not single_emb:
                return None
            embs_fallback.append(single_emb)
        return embs_fallback if len(embs_fallback) == len(batch_texts) else None

    def _try_batch_embed_endpoint(
        self, client: httpx2.Client, base_url: str, batch_texts: list[str]
    ) -> list[list[float]] | None:
        """Attempt /api/embed batch endpoint."""
        alt_payload = {"model": self.model, "input": batch_texts}
        alt_res = client.post(f"{base_url}/api/embed", json=alt_payload)
        if alt_res.status_code == 200:
            embs = alt_res.json().get("embeddings", [])
            if embs and isinstance(embs, list) and len(embs) == len(batch_texts):
                return embs
        return None

    def _query_ollama_node_batch(
        self, base_url: str, batch_texts: list[str]
    ) -> list[list[float]] | None:
        """Attempt to fetch batch embeddings from a single Ollama node."""
        validate_service_url(base_url, "Ollama", allow=self.ai_config.allow_private_network)
        with trace_span(
            "ai.rag.ollama_embed_batch",
            attributes={
                "server.address": base_url,
                "rag.batch_size": len(batch_texts),
                "rag.model": str(self.model),
            },
        ):
            client_timeout = httpx2.Timeout(self.timeout, connect=1.0)
            with httpx2.Client(timeout=client_timeout) as client:
                embs = self._try_batch_embed_endpoint(client, base_url, batch_texts)
                if embs is not None:
                    return embs
                return self._fetch_fallback_single_embeddings(client, base_url, batch_texts)

    def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        """Compute Ollama embeddings with multi-node round-robin distribution and batching."""
        if self.ai_config.rag.embedding_url:
            raw_url = self.ai_config.rag.embedding_url.strip().rstrip("/")
            if not raw_url.startswith(("http://", "https://")):
                raw_url = f"http://{raw_url}"
            urls = [raw_url]
        else:
            urls = (
                self.ai_config.get_ollama_urls
                if hasattr(self.ai_config, "get_ollama_urls")
                else (
                    self.ai_config.ollama_urls
                    or [self.ai_config.api_base_url or "http://localhost:11434"]
                )
            )
        chunk_batch_size = 8
        max_parallel = max(1, min(16, getattr(self.ai_config, "ollama_max_parallel", 2)))

        batches = [
            (idx, texts[i : i + chunk_batch_size])
            for idx, i in enumerate(range(0, len(texts), chunk_batch_size))
        ]

        def _embed_single_batch(
            batch_tuple: tuple[int, list[str]],
        ) -> tuple[int, list[list[float]]]:
            batch_idx, batch_texts = batch_tuple
            last_err: Exception | None = None

            # Distribute starting node across candidates via round-robin offset
            n_urls = len(urls)
            start_offset = batch_idx % n_urls
            candidate_urls = [urls[(start_offset + j) % n_urls] for j in range(n_urls)]

            for base_url in candidate_urls:
                try:
                    embs = self._query_ollama_node_batch(base_url.rstrip("/"), batch_texts)
                except Exception as exc:
                    last_err = exc
                    continue
                if not (embs and embs[0]):
                    continue
                self._dimension = self._dimension or len(embs[0])
                return (batch_idx, embs)

            if last_err:
                logger.debug(
                    "Ollama embedding batch %d failed across nodes: %s",
                    batch_idx,
                    last_err,
                )
            return (batch_idx, self._deterministic_fallback(batch_texts))

        total_workers = min(len(batches), max(1, len(urls) * max_parallel))
        results: list[tuple[int, list[list[float]]]] = []

        if total_workers > 1:
            with ThreadPoolExecutor(max_workers=total_workers) as executor:
                futures = [executor.submit(_embed_single_batch, b) for b in batches]
                for future in as_completed(futures):
                    results.append(future.result())
        else:
            for b in batches:
                results.append(_embed_single_batch(b))

        results.sort(key=lambda x: x[0])
        all_embeddings: list[list[float]] = [emb for _, batch_res in results for emb in batch_res]
        return all_embeddings

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Query OpenAI-compatible /v1/embeddings API."""
        base_url = (self.ai_config.api_base_url or "https://api.openai.com/v1").rstrip("/")
        validate_service_url(base_url, "OpenAI", allow=self.ai_config.allow_private_network)

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        model = self.model
        if model in ("all-minilm", "qwen3-embedding:0.6b"):
            model = "text-embedding-3-small"

        payload: dict[str, Any] = {
            "model": model,
            "input": texts,
        }

        endpoint = (
            f"{base_url}/embeddings" if base_url.endswith("/v1") else f"{base_url}/v1/embeddings"
        )
        try:
            client_timeout = httpx2.Timeout(self.timeout, connect=1.0)
            with httpx2.Client(timeout=client_timeout) as client:
                res = client.post(endpoint, headers=headers, json=payload)
                if res.status_code != 200:
                    raise EmbeddingsError(f"OpenAI embeddings HTTP {res.status_code}: {res.text}")
                data = res.json()
                items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                embs = [item["embedding"] for item in items]
                if embs and self._dimension is None:
                    self._dimension = len(embs[0])
                return embs
        except Exception as exc:
            logger.warning("OpenAI embeddings failed: %s. Using fallback.", exc)
            return self._deterministic_fallback(texts)

    def _deterministic_fallback(
        self, texts: list[str], dimensions: int | None = None
    ) -> list[list[float]]:
        """Generate deterministic normalized hash-based embeddings when no model is reachable."""
        dim = dimensions or self._infer_default_dimension()
        embeddings: list[list[float]] = []
        for text in texts:
            vec = [0.0] * dim
            # Generate deterministic pseudo-random float vector from text hash
            for i in range(dim):
                token_hash = hashlib.sha256(f"{text}_{i}".encode()).hexdigest()
                val = (int(token_hash[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0
                vec[i] = round(val, 6)

            # Cosine normalize
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [round(v / norm, 6) for v in vec]
            embeddings.append(vec)
        return embeddings
