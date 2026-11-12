"""The embeddings engine as a Pydantic AI embedding model, its timeouts and its prompt prefixes."""

from __future__ import annotations

import httpx2
import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.config import defaults
from devops_cli.config.settings import AIConfig
from tests.support.embedding_replies import (
    SERVING_BACKEND,
    gateway_engine,
    inputs,
    ollama_config,
    ollama_reply,
    serve,
)
from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.mark.anyio
async def test_ollama_embedding_model_embeds_queries_and_documents(web: WebFake) -> None:
    """OllamaEmbeddingModel conforms to the Pydantic AI EmbeddingModel protocol."""
    from devops_cli.ai.rag.embeddings import OllamaEmbeddingModel

    sent = serve(web, ollama_reply)
    ai_cfg = AIConfig(provider="ollama", ollama_urls=[SERVING_BACKEND], allow_private_network=True)
    model = OllamaEmbeddingModel(model_name="all-minilm", ai_config=ai_cfg, dimensions=4)

    res_query = await model.embed("What is Kubernetes?", input_type="query")
    docs = ["Doc 1", "Doc 2"]
    res_docs = await model.embed(docs, input_type="document")

    assert (model.model_name, model.system) == ("all-minilm", "ollama")
    assert (
        res_query.embeddings,
        res_query.inputs,
        res_query.input_type,
        res_query.model_name,
        res_query.provider_name,
    ) == ([[0.5] * 4], ["What is Kubernetes?"], "query", "all-minilm", "ollama")
    assert (len(res_docs.embeddings), res_docs.inputs, res_docs.input_type) == (2, docs, "document")
    assert len(sent) == 2


def test_a_provider_that_returns_too_few_vectors_raises(web: WebFake) -> None:
    serve(
        web,
        lambda request: httpx2.Response(200, json={"data": [{"index": 0, "embedding": [0.1] * 8}]}),
    )

    with pytest.raises(EmbeddingsError, match="returned 1 embeddings for 2 texts"):
        gateway_engine().embed_texts(["text1", "text2"])


def test_the_timeout_is_bounded_by_default_and_a_setting_or_a_parameter_overrides_it() -> None:
    ai_cfg = AIConfig(provider="ollama", ollama_urls=[])
    default = EmbeddingsEngine(ai_cfg).timeout
    ai_cfg.tasks.embedding.timeout = 8.0
    from_config = EmbeddingsEngine(ai_cfg).timeout
    explicit = EmbeddingsEngine(ai_cfg, timeout=25.0).timeout

    assert (default, from_config, explicit) == (defaults.DEFAULT_RAG_EMBEDDING_TIMEOUT, 8.0, 25.0)


@pytest.mark.parametrize(
    ("model", "text", "is_query", "expected"),
    [
        ("bge-m3", "def search():", False, "def search():"),
        ("bge-m3", "def search():", True, "def search():"),
        (
            "qwen3-embedding",
            "search query",
            True,
            "Instruct: Given a code search query, retrieve relevant code or documentation\nQuery: search query",
        ),
        ("qwen3-embedding", "doc content", False, "doc content"),
        ("nomic-embed-text", "search query", True, "search_query: search query"),
        ("nomic-embed-text", "doc content", False, "search_document: doc content"),
        ("e5-base", "search query", True, "query: search query"),
        ("e5-base", "doc content", False, "passage: doc content"),
        ("other-model", "search query", True, "search query"),
        ("other-model", "doc content", False, "doc content"),
    ],
)
def test_a_model_family_gets_its_own_prompt_prefix(
    model: str, text: str, is_query: bool, expected: str, web: WebFake
) -> None:
    """The text a node receives has the per-model prompt prefix of bge-m3, qwen3, nomic or e5."""
    sent = serve(web, ollama_reply)
    config = ollama_config()
    config.tasks.embedding.model = model

    EmbeddingsEngine(config, valkey_client=None).embed_texts([text], is_query=is_query)

    assert inputs(sent[0]) == [expected]
