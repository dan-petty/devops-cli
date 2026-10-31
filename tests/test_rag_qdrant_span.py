"""The `qdrant.upsert_points` span names its server by host and port, never by the configured URL."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.telemetry.tracer import get_tracer, reset_tracer

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture
def sent_spans(
    monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any]
) -> Iterator[list[dict[str, Any]]]:
    """Capture every OTLP payload that the tracer sends."""
    config(telemetry={"enabled": True})
    reset_tracer()
    payloads: list[dict[str, Any]] = []
    monkeypatch.setattr(get_tracer(), "_send_payload", lambda path, p: payloads.append(p))
    yield payloads
    reset_tracer()


def _upsert_span_attributes(url: str, payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Upsert one point through a client for `url` and return the attributes of the span."""
    native = MagicMock()
    native.get_collection.return_value.config.params.vectors.size = 4
    client = QdrantClient(url, client=native, allow_private_network=True, timeout=5.0)

    client.upsert_points("devops_code", [{"id": "1", "vector": [0.1] * 4, "payload": {}}])

    (span,) = (
        span
        for payload in payloads
        for resource in payload["resourceSpans"]
        for scope in resource["scopeSpans"]
        for span in scope["spans"]
        if span["name"] == "qdrant.upsert_points"
    )
    attributes: dict[str, Any] = {}
    for attr in span["attributes"]:
        ((kind, raw),) = attr["value"].items()
        attributes[attr["key"]] = int(raw) if kind == "intValue" else raw
    return attributes


@pytest.mark.parametrize(
    ("url", "server"),
    [
        ("http://example.com:6333", ("example.com", 6333)),
        ("http://user:secret@example.com:6333/prefix/path", ("example.com", 6333)),
        ("https://token@example.com", ("example.com", 443)),
        ("k8s://devops/qdrant:6333", ("qdrant.devops", 6333)),
        ("k8s+https://user:secret@devops/qdrant:6333/path?q=secret", ("qdrant.devops", 6333)),
        ("k8s://devops/qdrant:http", ("qdrant.devops", None)),
    ],
    ids=["port", "userinfo-and-path", "user-only-default-port", "k8s", "k8s-userinfo", "k8s-named"],
)
def test_upsert_span_names_the_server_by_host_and_port(
    sent_spans: list[dict[str, Any]], url: str, server: tuple[str, int | None]
) -> None:
    attributes = _upsert_span_attributes(url, sent_spans)

    assert (attributes["server.address"], attributes.get("server.port")) == server
    assert not [
        value
        for value in attributes.values()
        if any(text in str(value) for text in ("secret", "token", "user", "/prefix", "://"))
    ]
