"""Deterministic embeddings fake for tests (#1317).

Provides fixed-dimension deterministic vectors for given texts, records call history,
and supports simulated provider errors.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterator
from typing import Any

import pytest

from devops_cli.ai.rag.embeddings import EmbedderProtocol, EmbeddingsError


def _deterministic_vector(text: str, dimension: int) -> list[float]:
    """Generate a deterministic unit vector for a text."""
    if dimension <= 0:
        return []
    # Seed with SHA-256 digest of text
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [float(digest[i % len(digest)] + 1) for i in range(dimension)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw] if norm > 0.0 else [1.0] + [0.0] * (dimension - 1)


class FakeEmbedder(EmbedderProtocol):
    """Deterministic in-memory embedder fake satisfying EmbedderProtocol."""

    def __init__(
        self,
        dimension: int = 4,
        *,
        failing: bool = False,
        failure_message: str | None = None,
    ) -> None:
        self.dimension = dimension
        self.failing = failing
        self.failure_message = failure_message
        self.calls: list[tuple[list[str], bool]] = []
        self.recorded_texts: list[tuple[str, bool]] = []

    def embed_texts(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        if self.failing:
            raise EmbeddingsError(
                self.failure_message or "Embedding provider error", is_transient=False
            )
        self.calls.append((list(texts), is_query))
        for t in texts:
            self.recorded_texts.append((t, is_query))
        return [_deterministic_vector(t, self.dimension) for t in texts]

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text], is_query=False)[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self.embed_texts(texts, is_query=False)

    def fail(self, message: str | None = None) -> None:
        self.failing = True
        self.failure_message = message


@pytest.fixture
def embedder() -> Iterator[Any]:
    """Install an in-memory FakeEmbedder as the embedder seam override, and return it."""
    from devops_cli.ai.rag.embeddings import install_embedder, reset_embedder

    fake = FakeEmbedder()
    install_embedder(fake)
    try:
        yield fake
    finally:
        reset_embedder()
