"""Pydantic AI Embeddings and vector representations interface."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.agents.context import AgentUsage
from devops_cli.ai.agents.spend import DEFAULT_MODEL_PRICING, ModelPricing
from devops_cli.config.settings import AIConfig


class EmbeddingCost(BaseModel):
    """Cost breakdown for an embedding generation request."""

    total_price: float = 0.0
    currency: str = "USD"


class EmbeddingResult(BaseModel):
    """Result container for generated vector embeddings."""

    embeddings: list[list[float]] = Field(default_factory=list)
    texts: list[str] = Field(default_factory=list)
    usage: AgentUsage = Field(default_factory=AgentUsage)
    model: str = ""

    def __getitem__(self, item: int | str) -> list[float]:
        """Access embedding by integer index or source text match."""
        if isinstance(item, int):
            return self.embeddings[item]
        if isinstance(item, str):
            try:
                idx = self.texts.index(item)
                return self.embeddings[idx]
            except ValueError:
                for idx, t in enumerate(self.texts):
                    if t.strip() == item.strip():
                        return self.embeddings[idx]
                raise KeyError(f"Text '{item}' not found in embedding result texts.")
        raise TypeError(
            f"EmbeddingResult indices must be integers or strings, not {type(item).__name__}"
        )

    def __len__(self) -> int:
        return len(self.embeddings)

    def cost(self) -> EmbeddingCost:
        """Calculate approximate USD cost based on token usage and model pricing."""
        pricing: ModelPricing | None = None
        model_lower = self.model.lower().split(":")[-1]
        for key, p in DEFAULT_MODEL_PRICING.items():
            if key.lower() in model_lower:
                pricing = p
                break
        if pricing is None:
            pricing = DEFAULT_MODEL_PRICING.get("default", ModelPricing())
        calc = pricing.calculate_cost(self.usage.input_tokens, 0)
        return EmbeddingCost(total_price=calc)


class Embedder(BaseModel):
    """High-level unified interface for generating vector embeddings across providers."""

    model: str = "openai:text-embedding-3-small"
    dimensions: int | None = None
    engine: Any | None = None

    def _get_engine(self) -> Any:
        if self.engine is not None:
            return self.engine
        from devops_cli.ai.rag.embeddings import EmbeddingsEngine

        cfg = AIConfig()
        clean_model = self.model.split(":")[-1]
        cfg.rag.embedding_model = clean_model
        if "openai" in self.model.lower():
            cfg.provider = "openai"
        elif "ollama" in self.model.lower():
            cfg.provider = "ollama"
        eng = EmbeddingsEngine(cfg)
        if self.dimensions is not None:
            eng._dimension = self.dimensions
        return eng

    def embed_query_sync(self, query: str) -> EmbeddingResult:
        """Embed a single search query synchronously."""
        engine = self._get_engine()
        vec = engine.embed_query(query)
        est_tokens = max(1, int(len(query.split()) * 1.3))
        usage = AgentUsage(input_tokens=est_tokens, total_tokens=est_tokens)
        return EmbeddingResult(
            embeddings=[vec],
            texts=[query],
            usage=usage,
            model=self.model,
        )

    async def embed_query(self, query: str) -> EmbeddingResult:
        """Embed a single search query asynchronously."""
        return await asyncio.to_thread(self.embed_query_sync, query)

    def embed_documents_sync(self, documents: list[str]) -> EmbeddingResult:
        """Embed multiple documents synchronously."""
        engine = self._get_engine()
        vectors = engine.embed_texts(documents, is_query=False)
        total_tokens = sum(max(1, int(len(doc.split()) * 1.3)) for doc in documents)
        usage = AgentUsage(input_tokens=total_tokens, total_tokens=total_tokens)
        return EmbeddingResult(
            embeddings=vectors,
            texts=list(documents),
            usage=usage,
            model=self.model,
        )

    async def embed_documents(self, documents: list[str]) -> EmbeddingResult:
        """Embed multiple documents asynchronously."""
        return await asyncio.to_thread(self.embed_documents_sync, documents)
