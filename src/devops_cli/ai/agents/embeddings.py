"""Pydantic AI Embeddings and vector representations interface."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_ai.embeddings import (
    Embedder as PydanticEmbedder,
)
from pydantic_ai.embeddings import (
    EmbeddingModel,
    EmbeddingSettings,
    KnownEmbeddingModelName,
    TestEmbeddingModel,
)
from pydantic_ai.embeddings import (
    EmbeddingResult as PydanticEmbeddingResult,
)
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.usage import RequestUsage

from devops_cli.ai.agents.spend import DEFAULT_MODEL_PRICING, ModelPricing
from devops_cli.config.settings import AIConfig


class EmbeddingCost(BaseModel):
    """Cost breakdown for an embedding generation request."""

    total_price: float = 0.0
    currency: str = "USD"


class EngineEmbeddingModel(EmbeddingModel):
    """Adapter bridging any EmbeddingsEngine to Pydantic AI's EmbeddingModel interface."""

    def __init__(
        self,
        engine: Any,
        model_name: str = "default",
        provider_name: str = "devops-cli",
    ) -> None:
        self._engine = engine
        self._model_name = model_name
        self._provider_name = provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def system(self) -> str:
        return self._provider_name

    def __str__(self) -> str:
        return self._model_name

    def __repr__(self) -> str:
        return f"EngineEmbeddingModel({self._model_name!r})"

    async def embed(
        self,
        inputs: str | Sequence[str],
        *,
        input_type: Literal["query", "document"],
        settings: EmbeddingSettings | None = None,
    ) -> PydanticEmbeddingResult:
        texts = [inputs] if isinstance(inputs, str) else list(inputs)
        is_query = input_type == "query"
        if is_query and len(texts) == 1 and hasattr(self._engine, "embed_query"):
            vectors: list[list[float]] = [
                await asyncio.to_thread(self._engine.embed_query, texts[0])
            ]
        elif hasattr(self._engine, "embed_texts"):
            vectors = await asyncio.to_thread(self._engine.embed_texts, texts, is_query=is_query)
        else:
            vectors = [[0.0] * 768 for _ in texts]

        est_tokens = sum(max(1, int(len(t.split()) * 1.3)) for t in texts)
        return PydanticEmbeddingResult(
            vectors,
            inputs=texts,
            input_type=input_type,
            model_name=self._model_name,
            provider_name=self._provider_name,
            timestamp=datetime.now(UTC),
            usage=RequestUsage(input_tokens=est_tokens),
        )


@dataclass
class EmbeddingResult(PydanticEmbeddingResult):
    """Result container for generated vector embeddings, extending Pydantic AI EmbeddingResult."""

    def __init__(
        self,
        embeddings: Sequence[Sequence[float]],
        *,
        inputs: Sequence[str] | None = None,
        texts: Sequence[str] | None = None,
        input_type: Literal["query", "document"] = "query",
        model_name: str | None = None,
        model: str | None = None,
        provider_name: str = "devops-cli",
        timestamp: datetime | None = None,
        usage: RequestUsage | None = None,
        provider_details: dict[str, Any] | None = None,
        provider_response_id: str | None = None,
    ) -> None:
        resolved_inputs = inputs if inputs is not None else (texts or [])
        resolved_model = model_name if model_name is not None else (model or "")
        super().__init__(
            embeddings,
            inputs=resolved_inputs,
            input_type=input_type,
            model_name=resolved_model,
            provider_name=provider_name,
            timestamp=timestamp or datetime.now(UTC),
            usage=usage or RequestUsage(),
            provider_details=provider_details,
            provider_response_id=provider_response_id,
        )

    def __len__(self) -> int:
        return len(self.embeddings)

    @property
    def texts(self) -> Sequence[str]:
        """Convenience property referencing input texts."""
        return self.inputs

    @property
    def model(self) -> str:
        """Convenience property referencing model name."""
        return self.model_name

    def __getitem__(self, item: int | slice | str) -> Any:
        """Access embedding by integer index, slice, or source text match."""
        if isinstance(item, (int, slice)):
            return self.embeddings[item]
        if isinstance(item, str):
            try:
                return super().__getitem__(item)
            except ValueError, IndexError:
                for idx, text in enumerate(self.inputs):
                    if text.strip() == item.strip():
                        return self.embeddings[idx]
                raise KeyError(f"Text '{item}' not found in embedding result inputs.") from None
        raise TypeError(
            f"EmbeddingResult indices must be integers or strings, not {type(item).__name__}"
        )

    def cost(self) -> Any:
        """Calculate approximate cost using Pydantic AI native pricing, with fallback for local models."""
        try:
            return super().cost()
        except Exception:
            pricing: ModelPricing | None = None
            model_lower = self.model_name.lower().split(":")[-1]
            for key, p in DEFAULT_MODEL_PRICING.items():
                if key.lower() in model_lower:
                    pricing = p
                    break
            if pricing is None:
                pricing = DEFAULT_MODEL_PRICING.get("default", ModelPricing())
            calc = pricing.calculate_cost(self.usage.input_tokens or 0, 0)
            return EmbeddingCost(total_price=calc)


class Embedder(PydanticEmbedder):
    """High-level unified interface for generating vector embeddings across providers, extending Pydantic AI Embedder."""

    def __init__(
        self,
        model: EmbeddingModel | KnownEmbeddingModelName | str = "openai:text-embedding-3-small",
        *,
        settings: EmbeddingSettings | None = None,
        dimensions: int | None = None,
        engine: Any | None = None,
        instrument: bool | Any | None = None,
    ) -> None:
        self.dimensions = dimensions
        self._custom_engine = engine
        self._model_arg = model

        resolved_model: EmbeddingModel | KnownEmbeddingModelName | str
        if engine is not None:
            resolved_model = EngineEmbeddingModel(engine, model_name=str(model))
        elif isinstance(model, EmbeddingModel):
            resolved_model = model
        elif isinstance(model, str):
            clean_model = model.strip()
            if clean_model.lower().startswith("ollama:"):
                from devops_cli.ai.rag.embeddings import OllamaEmbeddingModel

                resolved_model = OllamaEmbeddingModel(
                    model_name=clean_model[7:],
                    dimensions=dimensions,
                )
            else:
                resolved_model = clean_model
        else:
            resolved_model = model

        super().__init__(
            resolved_model,
            settings=settings or (EmbeddingSettings(dimensions=dimensions) if dimensions else None),
            instrument=instrument,
        )

    @property
    def model_name(self) -> str:
        """Return canonical model name string."""
        active = self.model
        if hasattr(active, "model_name"):
            return str(getattr(active, "model_name"))
        return str(active)

    def _get_engine(self) -> Any:
        """Return underlying engine or create default EmbeddingsEngine."""
        if self._custom_engine is not None:
            return self._custom_engine
        active = self.model
        if hasattr(active, "_engine"):
            return getattr(active, "_engine")
        if hasattr(active, "engine"):
            return getattr(active, "engine")
        from devops_cli.ai.rag.embeddings import EmbeddingsEngine
        from devops_cli.config.settings import load_settings

        try:
            cfg = load_settings().ai.model_copy(deep=True)
        except Exception:
            cfg = AIConfig()
        model_str = str(self._model_arg).strip()
        clean_model = model_str
        if clean_model.lower().startswith("ollama:"):
            clean_model = clean_model[7:]
            cfg.provider = "ollama"
        elif clean_model.lower().startswith("openai:"):
            clean_model = clean_model[7:]
            cfg.provider = "openai"
        cfg.rag.embedding_model = clean_model
        eng = EmbeddingsEngine(cfg)
        if self.dimensions is not None:
            eng._dimension = self.dimensions
        return eng

    def _wrap_result(self, res: PydanticEmbeddingResult) -> EmbeddingResult:
        if isinstance(res, EmbeddingResult):
            return res
        return EmbeddingResult(
            res.embeddings,
            inputs=res.inputs,
            input_type=res.input_type,
            model_name=res.model_name,
            provider_name=res.provider_name,
            timestamp=res.timestamp,
            usage=res.usage,
            provider_details=res.provider_details,
            provider_response_id=res.provider_response_id,
        )

    def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> EmbeddingResult:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                res = executor.submit(func, *args, **kwargs).result()
                return self._wrap_result(res)
        return self._wrap_result(func(*args, **kwargs))

    async def embed_query(self, query: str | Sequence[str], **kwargs: Any) -> EmbeddingResult:
        return self._wrap_result(await super().embed_query(query, **kwargs))

    def embed_query_sync(self, query: str | Sequence[str], **kwargs: Any) -> EmbeddingResult:
        return self._run_sync(super().embed_query_sync, query, **kwargs)

    async def embed_documents(self, documents: Sequence[str], **kwargs: Any) -> EmbeddingResult:
        return self._wrap_result(await super().embed_documents(documents, **kwargs))

    def embed_documents_sync(self, documents: Sequence[str], **kwargs: Any) -> EmbeddingResult:
        return self._run_sync(super().embed_documents_sync, documents, **kwargs)

    async def embed(
        self,
        inputs: str | Sequence[str],
        *,
        input_type: Literal["query", "document"],
        **kwargs: Any,
    ) -> EmbeddingResult:
        return self._wrap_result(await super().embed(inputs, input_type=input_type, **kwargs))

    def embed_sync(
        self,
        inputs: str | Sequence[str],
        *,
        input_type: Literal["query", "document"],
        **kwargs: Any,
    ) -> EmbeddingResult:
        return self._run_sync(super().embed_sync, inputs, input_type=input_type, **kwargs)


__all__ = [
    "Embedder",
    "EmbeddingCost",
    "EmbeddingModel",
    "EmbeddingResult",
    "EmbeddingSettings",
    "EngineEmbeddingModel",
    "OpenAIEmbeddingModel",
    "TestEmbeddingModel",
]
