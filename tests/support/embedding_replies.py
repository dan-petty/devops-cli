"""Replies and engines that the embedding tests share: the HTTP answers of a gateway and a node.

The replies go through the `web` fake, so each one passes through the real client: its headers,
JSON body and status reach the engine as sent.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx2

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.config.constants import CONST_AI_GATEWAY_SERVED_BY_HEADER
from devops_cli.config.settings import AIConfig
from tests.support.fakes.http import WebFake

GATEWAY_URL = "http://example.com:4000/v1"
SERVING_BACKEND = "http://example.com:11434"


def answer_posts(web: WebFake, fake_post: Callable[..., httpx2.Response]) -> None:
    """Answer each request of the engine with `fake_post(url, json=<body>, headers=<headers>)`."""

    def answer(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content) if request.content else None
        return fake_post(str(request.url), json=body, headers=dict(request.headers))

    web.serve(answer)


def ollama_engine(nodes: list[str], **options: Any) -> EmbeddingsEngine:
    """An Ollama engine over `nodes`, with no Valkey tier."""
    ai_cfg = AIConfig(provider="ollama", ollama_urls=nodes, allow_private_network=True)
    ai_cfg.tasks.embedding.model = "bge-m3"
    return EmbeddingsEngine(ai_cfg, valkey_client=None, **options)


def serve(
    web: WebFake, *replies: Callable[[httpx2.Request], httpx2.Response]
) -> list[httpx2.Request]:
    """Answer the engine's requests with `replies` in turn, the last one for every later request.

    The `web` fake stands behind every client the engine opens, so each reply passes through the
    real client: its headers, JSON body and status reach the engine as sent.
    """
    queued = list(replies)
    sent: list[httpx2.Request] = []

    def answer(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        reply = queued.pop(0) if len(queued) > 1 else queued[0]
        return reply(request)

    web.serve(answer)
    return sent


def inputs(request: httpx2.Request) -> list[str]:
    return list(json.loads(request.content)["input"])


def gateway_reply(request: httpx2.Request) -> httpx2.Response:
    """A gateway `/v1/embeddings` reply that counts seven input tokens per text."""
    texts = inputs(request)
    return httpx2.Response(
        200,
        headers={CONST_AI_GATEWAY_SERVED_BY_HEADER: SERVING_BACKEND},
        json={
            "data": [{"index": i, "embedding": [0.5] * 4} for i in range(len(texts))],
            "usage": {"prompt_tokens": 7 * len(texts), "total_tokens": 7 * len(texts)},
        },
    )


def ollama_reply(request: httpx2.Request) -> httpx2.Response:
    """An Ollama `/api/embed` reply that counts five input tokens per text."""
    texts = inputs(request)
    return httpx2.Response(
        200, json={"embeddings": [[0.5] * 4 for _ in texts], "prompt_eval_count": 5 * len(texts)}
    )


def rate_limited(_request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(429, headers={"retry-after": "0"}, text="rate limited")


def gateway_config() -> AIConfig:
    ai_cfg = AIConfig(provider="gateway", gateway_url=GATEWAY_URL, allow_private_network=True)
    ai_cfg.tasks.embedding.model = "bge-m3:latest"
    return ai_cfg


def gateway_engine(ai_cfg: AIConfig | None = None, **options: Any) -> EmbeddingsEngine:
    config = gateway_config() if ai_cfg is None else ai_cfg
    return EmbeddingsEngine(config, api_key="sk-gateway", valkey_client=None, **options)


def ollama_config() -> AIConfig:
    ai_cfg = AIConfig(provider="ollama", ollama_urls=[SERVING_BACKEND], allow_private_network=True)
    ai_cfg.tasks.embedding.model = "bge-m3"
    return ai_cfg


def capture_embedding_posts(web: WebFake) -> list[tuple[str, str, str]]:
    """Record (url, authorization, model) for each embeddings POST and answer with a vector."""
    calls: list[tuple[str, str, str]] = []

    def fake_post(url: str, **kwargs: Any) -> httpx2.Response:
        url_str = str(url)
        if "embeddings" in url_str:
            headers = kwargs.get("headers") or {}
            payload = kwargs.get("json") or {}
            calls.append((url_str, headers.get("authorization", ""), payload.get("model", "")))
            return httpx2.Response(200, json={"data": [{"index": 0, "embedding": [0.5] * 8}]})
        return httpx2.Response(200, json={})

    answer_posts(web, fake_post)
    return calls
