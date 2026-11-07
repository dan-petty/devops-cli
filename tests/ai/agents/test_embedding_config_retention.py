"""An embedding model keeps its configuration: settings, tags and task overrides."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.ai.agents.embeddings import Embedder
from devops_cli.ai.rag.embeddings import EmbeddingsEngine, OllamaEmbeddingModel
from devops_cli.config.settings import AIConfig, AIEmbeddingTaskOverride
from tests.support.embedding_replies import ollama_reply, serve
from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_an_engine_without_a_config_uses_the_model_and_nodes_of_the_settings(
    config: Callable[..., Any], web: WebFake
) -> None:
    """EmbeddingsEngine defaults to the loaded `ai` settings rather than a blank AIConfig."""
    config(
        ai={
            "tasks": {
                "embedding": {
                    "model": "embeddinggemma:300m",
                    "ollama_urls": ["http://example.com:11434"],
                }
            }
        }
    )
    sent = serve(web, ollama_reply)
    engine = EmbeddingsEngine()

    engine.embed_texts(["hello"])

    assert (engine.model, str(sent[0].url), json.loads(sent[0].content)["model"]) == (
        "embeddinggemma:300m",
        "http://example.com:11434/api/embed",
        "embeddinggemma:300m",
    )


def test_an_engine_prefers_the_embedding_task_model_of_its_config() -> None:
    ai_cfg = AIConfig()
    ai_cfg.tasks.embedding = AIEmbeddingTaskOverride(model="custom-task-embed:v1")

    assert EmbeddingsEngine(ai_cfg).model == "custom-task-embed:v1"


def test_the_ollama_embedding_model_uses_the_model_of_the_settings(
    config: Callable[..., Any],
) -> None:
    config(ai={"tasks": {"embedding": {"model": "embeddinggemma:300m"}}})

    assert OllamaEmbeddingModel().model_name == "embeddinggemma:300m"


@pytest.mark.parametrize(
    ("spec", "model"),
    [
        ("ollama:embeddinggemma:300m", "embeddinggemma:300m"),
        ("ollama:qwen3:14b-q8_0", "qwen3:14b-q8_0"),
    ],
)
def test_an_embedder_keeps_the_colon_tag_of_a_model_name(
    spec: str, model: str, config: Callable[..., Any], web: WebFake
) -> None:
    """A model name such as embeddinggemma:300m is not cut at its tag."""
    config(ai={"ollama_urls": ["http://example.com:11434"]})
    sent = serve(web, ollama_reply)

    Embedder(spec).embed_query_sync("hello")

    assert json.loads(sent[0].content)["model"] == model
