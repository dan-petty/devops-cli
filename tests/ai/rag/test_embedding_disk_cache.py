"""The disk tier of the embedding cache: vectors that stay between two runs of the CLI (#4447)."""

from __future__ import annotations

import json
import logging
import sqlite3
from array import array
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fakeredis import FakeServer, FakeValkey

from devops_cli.ai.rag.embedding_disk_cache import EmbeddingDiskCache
from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.config.constants import CONST_AI_GATEWAY_SERVED_BY_HEADER
from devops_cli.config.settings import AIConfig
from devops_cli.telemetry.instruments import EMBEDDING_CACHE_LOOKUPS_TOTAL
from devops_cli.valkey.client import ValkeyClient
from tests.support.embedding_replies import (
    SERVING_BACKEND,
    gateway_config,
    gateway_engine,
    inputs,
    serve,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")


def _distinct_reply(request: httpx2.Request) -> httpx2.Response:
    """A gateway reply whose vector differs for each text and holds floats with no short form."""
    texts = inputs(request)
    vectors = [[float(len(text)), 1 / 3, -2.5e-7, 0.1] for text in texts]
    return httpx2.Response(
        200,
        headers={CONST_AI_GATEWAY_SERVED_BY_HEADER: SERVING_BACKEND},
        json={
            "data": [{"index": i, "embedding": v} for i, v in enumerate(vectors)],
            "usage": {"prompt_tokens": len(texts), "total_tokens": len(texts)},
        },
    )


def _run(path: Path, texts: list[str], config: AIConfig | None = None) -> list[list[float]]:
    """One run of the CLI: a new engine, with an empty memory cache, over the cache file."""
    return gateway_engine(config, disk_cache=EmbeddingDiskCache(path)).embed_texts(texts)


def test_a_second_run_reads_the_vectors_from_disk_and_sends_nothing(
    tmp_path: Path, web: WebFake
) -> None:
    sent = serve(web, _distinct_reply)
    path = tmp_path / "embeddings.db"
    first = _run(path, ["alpha", "beta two"])

    second = _run(path, ["alpha", "beta two"])

    assert (len(sent), second) == (1, first)


def test_a_run_sends_only_the_changed_texts_to_the_model(tmp_path: Path, web: WebFake) -> None:
    sent = serve(web, _distinct_reply)
    path = tmp_path / "embeddings.db"
    _run(path, ["one", "two", "three", "four", "five"])

    _run(path, ["one", "two changed", "three", "four", "five changed"])

    assert [inputs(request) for request in sent] == [
        ["one", "two", "three", "four", "five"],
        ["two changed", "five changed"],
    ]


def test_a_vector_of_another_model_is_a_miss(tmp_path: Path, web: WebFake) -> None:
    sent = serve(web, _distinct_reply)
    path = tmp_path / "embeddings.db"
    _run(path, ["shared text"])
    other = gateway_config()
    other.tasks.embedding.model = "other-embed:latest"

    _run(path, ["shared text"], other)

    assert [inputs(request) for request in sent] == [
        ["shared text"],
        ["shared text"],
    ]


def test_a_corrupt_entry_goes_to_the_model_and_its_vector_replaces_it(
    tmp_path: Path, web: WebFake
) -> None:
    sent = serve(web, _distinct_reply)
    path = tmp_path / "embeddings.db"
    first = _run(path, ["damaged"])
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE embeddings SET vector = x'0102'")
    conn.close()

    second = _run(path, ["damaged"])
    third = _run(path, ["damaged"])

    assert (len(sent), second, third) == (2, first, first)


def test_a_stored_vector_of_another_length_goes_to_the_model(tmp_path: Path, web: WebFake) -> None:
    """A row that holds two doubles, under a key whose vectors have four, is a miss."""
    sent = serve(web, _distinct_reply)
    path = tmp_path / "embeddings.db"
    first = _run(path, ["short row"])
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE embeddings SET vector = ?", (array("d", [1.0, 2.0]).tobytes(),))
    conn.close()

    second = _run(path, ["short row"])

    assert (len(sent), second) == (2, first)


def _six_doubles_reply(request: httpx2.Request) -> httpx2.Response:
    """A gateway reply whose vectors have six doubles: the same model name serves a new model."""
    texts = inputs(request)
    return httpx2.Response(
        200,
        headers={CONST_AI_GATEWAY_SERVED_BY_HEADER: SERVING_BACKEND},
        json={"data": [{"index": i, "embedding": [0.25] * 6} for i in range(len(texts))]},
    )


def test_vectors_of_a_new_length_remove_the_rows_of_the_old_length(
    tmp_path: Path, web: WebFake
) -> None:
    sent = serve(web, _distinct_reply, _six_doubles_reply)
    path = tmp_path / "embeddings.db"
    _run(path, ["old row"])
    _run(path, ["new row"])

    again = _run(path, ["old row", "new row"])

    assert ([inputs(request) for request in sent], again) == (
        [["old row"], ["new row"], ["old row"]],
        [[0.25] * 6, [0.25] * 6],
    )


def test_a_vector_of_the_model_that_a_direct_openai_request_names_is_a_miss_at_the_gateway(
    tmp_path: Path, web: WebFake
) -> None:
    """A direct OpenAI request sends `text-embedding-3-small` for `qwen3-embedding:0.6b`; the
    gateway gets the configured name, so the vector of the one is no hit for the other."""
    sent = serve(web, _distinct_reply)
    path = tmp_path / "embeddings.db"
    direct = AIConfig(
        provider="openai", api_base_url="http://example.com:1234/v1", allow_private_network=True
    )
    direct.tasks.embedding.model = "qwen3-embedding:0.6b"
    gateway = gateway_config()
    gateway.tasks.embedding.model = "qwen3-embedding:0.6b"
    _run(path, ["same text"], direct)

    _run(path, ["same text"], gateway)

    assert [json.loads(request.content)["model"] for request in sent] == [
        "text-embedding-3-small",
        "qwen3-embedding:0.6b",
    ]


def test_a_cache_file_that_is_not_a_database_leaves_each_text_to_the_model(
    tmp_path: Path, web: WebFake, caplog: pytest.LogCaptureFixture
) -> None:
    sent = serve(web, _distinct_reply)
    path = tmp_path / "embeddings.db"
    path.write_bytes(b"not a database " * 100)

    with caplog.at_level(logging.WARNING, logger="devops_cli.ai.rag.embedding_disk_cache"):
        vectors = _run(path, ["text"])

    assert (len(sent), vectors, str(path) in caplog.text) == (
        1,
        [[4.0, 1 / 3, -2.5e-7, 0.1]],
        True,
    )


def test_a_vector_that_no_run_used_for_thirty_days_is_removed(
    tmp_path: Path, web: WebFake, clock: ClockFake
) -> None:
    """A read keeps a vector; a write removes each vector that no run read or wrote for 30 days."""
    sent = serve(web, _distinct_reply)
    path = tmp_path / "embeddings.db"
    _run(path, ["kept", "dropped"])
    clock.shift(timedelta(days=20))
    _run(path, ["kept"])
    clock.shift(timedelta(days=20))
    _run(path, ["new"])

    _run(path, ["kept", "dropped"])

    assert [inputs(request) for request in sent] == [["kept", "dropped"], ["new"], ["dropped"]]


def _lookups(otlp: FakeCollector) -> list[tuple[dict[str, Any], float]]:
    return sorted(
        otlp.points(EMBEDDING_CACHE_LOOKUPS_TOTAL.name), key=lambda point: point[0]["result"]
    )


def test_a_text_that_only_the_disk_holds_counts_as_a_disk_hit(
    tmp_path: Path, otlp: FakeCollector, web: WebFake
) -> None:
    serve(web, _distinct_reply)
    path = tmp_path / "embeddings.db"
    _run(path, ["on disk"])
    otlp.clear()

    _run(path, ["on disk", "not cached"])

    assert _lookups(otlp) == [({"result": "hit", "tier": "disk"}, 1.0), ({"result": "miss"}, 1.0)]


def test_valkey_answers_before_the_disk_and_a_disk_hit_fills_valkey(
    tmp_path: Path,
    otlp: FakeCollector,
    valkey_server: FakeServer,
    valkey_client: ValkeyClient,
    web: WebFake,
) -> None:
    """A run with an empty Valkey reads the vector from disk and puts it in Valkey, so the next
    run gets it from Valkey."""
    sent = serve(web, _distinct_reply)
    path = tmp_path / "embeddings.db"
    _run(path, ["chunk"])
    tiers: list[list[tuple[dict[str, Any], float]]] = []
    for _ in range(2):
        otlp.clear()
        EmbeddingsEngine(
            gateway_config(),
            api_key="sk-gateway",
            valkey_client=valkey_client,
            disk_cache=EmbeddingDiskCache(path),
        ).embed_texts(["chunk"])
        tiers.append(_lookups(otlp))

    assert (len(sent), tiers, FakeValkey(server=valkey_server).dbsize()) == (
        1,
        [[({"result": "hit", "tier": "disk"}, 1.0)], [({"result": "hit", "tier": "valkey"}, 1.0)]],
        1,
    )
