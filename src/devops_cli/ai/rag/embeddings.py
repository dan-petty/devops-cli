"""Embeddings engine for Ollama and OpenAI-compatible providers."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx2

from devops_cli.config.defaults import DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS
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
        self.timeout = min(timeout, 60.0)
        self.model = self.ai_config.rag.embedding_model or "all-minilm"

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
        """Query Ollama server(s) for embeddings with automatic failover."""
        urls = self.ai_config.get_ollama_urls
        last_exc: Exception | None = None

        for base_url in urls:
            base_url = base_url.rstrip("/")
            try:
                validate_service_url(base_url, "Ollama", allow=self.ai_config.allow_private_network)
            except Exception as exc:
                last_exc = exc
                continue

            # Try Ollama /api/embeddings per text
            embeddings: list[list[float]] = []
            failed_node = False

            with httpx2.Client(timeout=self.timeout) as client:
                for text in texts:
                    endpoint = f"{base_url}/api/embeddings"
                    payload = {"model": self.model, "prompt": text}
                    try:
                        res = client.post(endpoint, json=payload)
                        if res.status_code != 200:
                            # Try /api/embed format
                            alt_endpoint = f"{base_url}/api/embed"
                            alt_payload = {"model": self.model, "input": text}
                            alt_res = client.post(alt_endpoint, json=alt_payload)
                            if alt_res.status_code == 200:
                                embs = alt_res.json().get("embeddings", [])
                                if embs and isinstance(embs[0], list):
                                    embeddings.append(embs[0])
                                    continue
                            failed_node = True
                            last_exc = EmbeddingsError(f"Ollama HTTP {res.status_code}: {res.text}")
                            break
                        data = res.json()
                        emb = data.get("embedding", [])
                        if not emb:
                            failed_node = True
                            break
                        embeddings.append(emb)
                    except Exception as exc:
                        failed_node = True
                        last_exc = exc
                        break

            if not failed_node and len(embeddings) == len(texts):
                return embeddings

        if last_exc:
            logger.warning(
                "Ollama embeddings failed across all nodes: %s. Using fallback.", last_exc
            )
        return self._deterministic_fallback(texts)

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Query OpenAI-compatible /v1/embeddings API."""
        base_url = (self.ai_config.api_base_url or "https://api.openai.com/v1").rstrip("/")
        validate_service_url(base_url, "OpenAI", allow=self.ai_config.allow_private_network)

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        model = self.model
        if model == "all-minilm":
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
                return [item["embedding"] for item in items]
        except Exception as exc:
            logger.warning("OpenAI embeddings failed: %s. Using fallback.", exc)
            return self._deterministic_fallback(texts)

    def _deterministic_fallback(self, texts: list[str], dimensions: int = 384) -> list[list[float]]:
        """Generate deterministic normalized hash-based embeddings when no model is reachable."""
        embeddings: list[list[float]] = []
        for text in texts:
            vec = [0.0] * dimensions
            # Generate deterministic pseudo-random float vector from text hash
            for i in range(dimensions):
                token_hash = hashlib.sha256(f"{text}_{i}".encode()).hexdigest()
                val = (int(token_hash[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0
                vec[i] = round(val, 6)

            # Cosine normalize
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [round(v / norm, 6) for v in vec]
            embeddings.append(vec)
        return embeddings
