"""Embeddings engine for Ollama and OpenAI-compatible providers."""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from concurrent.futures import as_completed
from typing import Any

import httpx2

from devops_cli.config.defaults import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_RAG_EMBEDDING_CACHE_SIZE,
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


# =============================================================================
# In-Memory SHA-256 Keyed Embedding LRU Cache
# =============================================================================


class _EmbeddingLRUCache:
    """Thread-safe in-memory LRU cache for embedding vectors, keyed by SHA-256 of (text + model)."""

    def __init__(self, maxsize: int = DEFAULT_RAG_EMBEDDING_CACHE_SIZE) -> None:
        self._maxsize = max(1, maxsize)
        self._store: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits: int = 0
        self.misses: int = 0

    def _key(self, text: str, model: str) -> str:
        """Compute deterministic SHA-256 cache key for (text, model) pair."""
        return hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()

    def get(self, text: str, model: str) -> list[float] | None:
        """Return cached embedding vector or None on miss."""
        key = self._key(text, model)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self.hits += 1
                return self._store[key]
            self.misses += 1
            return None

    def put(self, text: str, model: str, vector: list[float]) -> None:
        """Insert or update a cache entry, evicting the LRU entry when at capacity."""
        key = self._key(text, model)
        with self._lock:
            if key in self._store:
                self._store[key] = vector
                self._store.move_to_end(key)
            else:
                if len(self._store) >= self._maxsize:
                    self._store.popitem(last=False)  # Evict LRU
                self._store[key] = vector
                self._store.move_to_end(key)

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        """Evict all cached entries and reset counters."""
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0


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
        cache_size: int = DEFAULT_RAG_EMBEDDING_CACHE_SIZE,
    ) -> None:
        base_config = ai_config or AIConfig()
        self.ai_config = base_config.for_task("embedding")
        self.api_key = api_key
        self.timeout = min(timeout, 120.0)
        self.model = self.ai_config.rag.embedding_model or DEFAULT_RAG_EMBEDDING_MODEL
        self._dimension: int | None = None
        self._cache = _EmbeddingLRUCache(maxsize=cache_size)

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
        """Generate vector embeddings for a list of text strings with LRU cache acceleration."""
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
            # Split texts into cache hits and misses
            cached: dict[int, list[float]] = {}
            miss_indices: list[int] = []
            miss_texts: list[str] = []
            for idx, text in enumerate(texts):
                hit = self._cache.get(text, self.model)
                if hit is not None:
                    cached[idx] = hit
                else:
                    miss_indices.append(idx)
                    miss_texts.append(text)

            from devops_cli.telemetry import record_metric

            record_metric("devops_cli_embedding_cache_hits_total", len(cached), unit="1")
            record_metric("devops_cli_embedding_cache_misses_total", len(miss_texts), unit="1")
            record_metric("devops_cli_embedding_cache_size", self._cache.size, unit="1")

            if miss_texts:
                # Model-aware task prefixing for asymmetric models (only for misses)
                prefixed_miss = self._apply_model_prefix(miss_texts, is_query=is_query)

                provider = self.ai_config.provider.lower()
                api_base = self.ai_config.api_base_url or ""
                if provider in ("openai", "copilot"):
                    fresh = self._embed_openai(prefixed_miss)
                elif provider == "ollama" or (not provider and ":11434" in api_base):
                    fresh = self._embed_ollama(prefixed_miss)
                elif self.ai_config.ollama_urls:
                    fresh = self._embed_ollama(prefixed_miss)
                else:
                    fresh = self._deterministic_fallback(prefixed_miss)

                for miss_idx, (original_text, vector) in zip(miss_indices, zip(miss_texts, fresh)):
                    self._cache.put(original_text, self.model, vector)
                    cached[miss_idx] = vector

            return [cached[i] for i in range(len(texts))]

    def embed_query(self, text: str) -> list[float]:
        """Generate vector embedding for a single search query with LRU cache acceleration."""
        hit = self._cache.get(text, self.model)
        if hit is not None:
            return hit
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
