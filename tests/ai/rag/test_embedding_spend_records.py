"""Each embedding request reaches the spend ledger, with the tokens its reply counted (#1623)."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.spend.ledger import SpendLedger
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_SERVED_BY_HEADER,
)
from devops_cli.config.settings import AIConfig
from devops_cli.telemetry.tracer import get_recent_spans
from tests.support.embedding_replies import (
    SERVING_BACKEND,
    gateway_engine,
    gateway_reply,
    inputs,
    ollama_config,
    ollama_reply,
    rate_limited,
    serve,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")


_LEDGER_ROWS = (
    "SELECT provider, server, model, prompt_tokens, completion_tokens, cached, request_type,"
    " served_by FROM ai_spend_records ORDER BY id"
)


def _ledger_rows(ledger: SpendLedger) -> list[tuple[Any, ...]]:
    with contextlib.closing(sqlite3.connect(ledger.db_path)) as conn:
        return conn.execute(_LEDGER_ROWS).fetchall()


_GATEWAY_ROW = (
    "gateway",
    "example.com:4000",
    "bge-m3:latest",
    7,
    0,
    0,
    "embedding",
    SERVING_BACKEND,
)


def test_a_gateway_batch_records_one_embedding_row_with_the_replys_tokens_and_backend(
    spend_ledger: SpendLedger, web: WebFake
) -> None:
    """One `/v1/embeddings` request writes one ledger row with the tokens the reply counted.

    The row names the gateway as its server and the backend the gateway's header names.
    """
    sent = serve(web, gateway_reply)

    gateway_engine().embed_texts(["first chunk", "second chunk"])

    assert (len(sent), _ledger_rows(spend_ledger)) == (
        1,
        [(*_GATEWAY_ROW[:3], 14, *_GATEWAY_ROW[4:])],
    )


def test_a_hosted_gateway_embedding_is_priced_at_the_deployment_model_that_it_names(
    spend_ledger: SpendLedger, web: WebFake
) -> None:
    """A gateway reply that a hosted API served names its deployment model in
    `x-litellm-model-name`. The row is priced at that model and keeps the requested model (#2031).
    """

    def hosted_reply(request: httpx2.Request) -> httpx2.Response:
        texts = inputs(request)
        return httpx2.Response(
            200,
            headers={
                CONST_AI_GATEWAY_SERVED_BY_HEADER: "https://api.openai.com",
                "x-litellm-model-name": "openai/text-embedding-3-small",
            },
            json={
                "data": [{"index": i, "embedding": [0.5] * 4} for i in range(len(texts))],
                "usage": {"prompt_tokens": 1_000_000, "total_tokens": 1_000_000},
            },
        )

    serve(web, hosted_reply)

    gateway_engine().embed_texts(["hosted chunk"])

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute(
            "SELECT model, served_model, pricing_source, cost_usd FROM ai_spend_records"
        ).fetchall()
    assert rows == [("bge-m3:latest", "openai/text-embedding-3-small", "genai_prices:openai", 0.02)]


def test_a_batch_retried_after_http_429_records_one_row(
    clock: ClockFake, spend_ledger: SpendLedger, web: WebFake
) -> None:
    """A batch the gateway refuses once and then answers is one request in the ledger."""
    sent = serve(web, rate_limited, gateway_reply)

    gateway_engine().embed_texts(["rate limited chunk"])

    assert (len(sent), _ledger_rows(spend_ledger)) == (2, [_GATEWAY_ROW])


def test_batches_sent_in_parallel_record_one_row_each(
    spend_ledger: SpendLedger, web: WebFake
) -> None:
    """Each batch the engine sends in parallel writes its own row."""
    sent = serve(web, gateway_reply)
    engine = gateway_engine(batch_size=1)

    engine.embed_texts(["chunk one", "chunk two", "chunk three"])

    assert (len(sent), _ledger_rows(spend_ledger)) == (3, [_GATEWAY_ROW] * 3)


def test_an_ollama_batch_records_the_tokens_its_reply_counted(
    spend_ledger: SpendLedger, web: WebFake
) -> None:
    """An Ollama `/api/embed` batch takes its tokens from the reply's `prompt_eval_count`."""
    serve(web, ollama_reply)

    EmbeddingsEngine(ollama_config(), valkey_client=None).embed_texts(["one", "two"])

    assert _ledger_rows(spend_ledger) == [
        ("ollama", "example.com:11434", "bge-m3", 10, 0, 0, "embedding", None)
    ]


def test_an_ollama_batch_names_its_server_without_the_password_of_its_url(
    spend_ledger: SpendLedger, otlp: FakeCollector, web: WebFake
) -> None:
    """A configured URL with userinfo names its server by host and port in the ledger, the
    counters and the batch span, and no record holds the password."""
    serve(web, ollama_reply)
    ai_cfg = AIConfig(
        provider="ollama",
        ollama_urls=["http://user:pw@example.com:11434"],
        allow_private_network=True,
    )
    ai_cfg.tasks.embedding.model = "bge-m3"

    EmbeddingsEngine(ai_cfg, valkey_client=None).embed_texts(["one"])

    with contextlib.closing(sqlite3.connect(spend_ledger.db_path)) as conn:
        rows = conn.execute("SELECT server, backend_info FROM ai_spend_records").fetchall()
    (span,) = [s for s in get_recent_spans() if s["name"] == "ai.rag.ollama_embed_batch"]
    span_server = {
        a["key"]: next(iter(a["value"].values()))
        for a in span["attributes"]
        if a["key"].startswith("server.")
    }
    counter_servers = {
        attrs["server"] for attrs, _value in otlp.points("devops_cli_ai_requests_total")
    }
    assert (rows, counter_servers, span_server) == (
        [("example.com:11434", "ollama (example.com:11434)")],
        {"example.com:11434"},
        {"server.address": "example.com", "server.port": "11434"},
    )


def test_a_call_the_cache_answers_records_no_request(
    spend_ledger: SpendLedger, web: WebFake
) -> None:
    """Texts the cache answers send no request, so they add no row and no tokens."""
    sent = serve(web, gateway_reply)
    engine = gateway_engine()

    engine.embed_texts(["cached chunk"])
    engine.embed_texts(["cached chunk"])

    assert (len(sent), _ledger_rows(spend_ledger)) == (1, [_GATEWAY_ROW])


@pytest.mark.parametrize(
    ("make_engine", "reply", "row"),
    [
        (gateway_engine, gateway_reply, _GATEWAY_ROW),
        (
            lambda: EmbeddingsEngine(ollama_config(), valkey_client=None),
            ollama_reply,
            ("ollama", "example.com:11434", "bge-m3", 5, 0, 0, "embedding", None),
        ),
    ],
    ids=["gateway", "ollama"],
)
def test_the_dimension_probe_records_its_request(
    spend_ledger: SpendLedger,
    make_engine: Callable[[], EmbeddingsEngine],
    reply: Callable[[httpx2.Request], httpx2.Response],
    row: tuple[Any, ...],
    web: WebFake,
) -> None:
    """The request that probes the model's dimension is an embedding request like any other."""
    serve(web, reply)

    dimension = make_engine().dimension

    assert (dimension, _ledger_rows(spend_ledger)) == (4, [row])


@pytest.mark.anyio
@pytest.mark.parametrize("wrapper", ["ollama", "engine"])
async def test_the_embedding_models_report_the_tokens_the_provider_counted(
    spend_ledger: SpendLedger, wrapper: str, web: WebFake
) -> None:
    """Both pydantic-ai embedding models report the reply's token count, not an estimate."""
    from devops_cli.ai.rag.embeddings import EngineEmbeddingModel, OllamaEmbeddingModel

    serve(web, ollama_reply)
    model = (
        OllamaEmbeddingModel("bge-m3", ai_config=ollama_config())
        if wrapper == "ollama"
        else EngineEmbeddingModel(EmbeddingsEngine(ollama_config(), valkey_client=None))
    )

    result = await model.embed(["three words here", "two words"], input_type="document")

    assert result.usage.input_tokens == 10
