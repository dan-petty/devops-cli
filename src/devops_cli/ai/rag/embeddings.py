"""Embeddings engine for Ollama and OpenAI-compatible providers."""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx2

from devops_cli.config.defaults import (
    DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_RAG_EMBEDDING_MODEL,
)
from devops_cli.config.settings import AIConfig
from devops_cli.http.validation import validate_service_url

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
        timeout: float = DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self.ai_config = ai_config or AIConfig()
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

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a list of text strings."""
        if not texts:
            return []

        provider = self.ai_config.provider.lower()
        if provider == "ollama":
            return self._embed_ollama(texts)
        elif provider in ("openai", "copilot"):
            return self._embed_openai(texts)
        else:
            # Fallback to Ollama if configured, otherwise deterministic vectors
            if self.ai_config.ollama_urls:
                try:
                    return self._embed_ollama(texts)
                except Exception as exc:
                    logger.debug("Ollama embedding fallback failed: %s", exc)
            return self._deterministic_fallback(texts)

    def embed_query(self, text: str) -> list[float]:
        """Generate vector embedding for a single search query."""
        results = self.embed_texts([text])
        if not results:
            raise EmbeddingsError(f"Failed to generate embedding for query: {text[:50]}")
        return results[0]

    def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        """Query Ollama server(s) for embeddings with parallel batching and automatic failover."""
        urls = self.ai_config.get_ollama_urls
        if not urls:
            return self._deterministic_fallback(texts)

        max_parallel = max(1, getattr(self.ai_config, "ollama_max_parallel", 2))
        chunk_batch_size = 32

        # Partition texts into sub-batches of up to chunk_batch_size
        batches: list[tuple[int, list[str]]] = [
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
                base_url = base_url.rstrip("/")
                try:
                    validate_service_url(
                        base_url, "Ollama", allow=self.ai_config.allow_private_network
                    )
                except Exception as exc:
                    last_err = exc
                    continue

                try:
                    with httpx2.Client(timeout=self.timeout) as client:
                        alt_endpoint = f"{base_url}/api/embed"
                        alt_payload = {"model": self.model, "input": batch_texts}
                        alt_res = client.post(alt_endpoint, json=alt_payload)
                        if alt_res.status_code == 200:
                            embs = alt_res.json().get("embeddings", [])
                            if embs and isinstance(embs, list) and len(embs) == len(batch_texts):
                                if embs[0] and self._dimension is None:
                                    self._dimension = len(embs[0])
                                return (batch_idx, embs)

                        # Fallback for single /api/embeddings endpoint
                        embs_fallback: list[list[float]] = []
                        for t in batch_texts:
                            endpoint = f"{base_url}/api/embeddings"
                            payload = {"model": self.model, "prompt": t}
                            res = client.post(endpoint, json=payload)
                            if res.status_code == 200:
                                single_emb = res.json().get("embedding", [])
                                if single_emb:
                                    embs_fallback.append(single_emb)
                                    continue
                            break
                        if len(embs_fallback) == len(batch_texts):
                            if embs_fallback[0] and self._dimension is None:
                                self._dimension = len(embs_fallback[0])
                            return (batch_idx, embs_fallback)
                except Exception as exc:
                    last_err = exc
                    continue

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

        try:
            with httpx2.Client(timeout=self.timeout) as client:
                res = client.post(f"{base_url}/embeddings", headers=headers, json=payload)
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
