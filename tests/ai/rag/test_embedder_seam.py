"""The embedder seam: the installed embedder is the one `create_embedder` gives."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_embedder_protocol_and_fake() -> None:
    from devops_cli.ai.rag.embeddings import (
        EmbedderProtocol,
        create_embedder,
        get_embedder_override,
        install_embedder,
        reset_embedder,
    )
    from tests.support.fakes.embeddings import FakeEmbedder

    fake = FakeEmbedder()
    assert isinstance(fake, EmbedderProtocol)
    vecs = fake.embed_texts(["hello"])
    assert len(vecs) == 1
    assert len(vecs[0]) == 4
    assert fake.embed_query("hello") == vecs[0]

    install_embedder(fake)
    assert get_embedder_override() is fake
    assert create_embedder() is fake
    reset_embedder()
    assert get_embedder_override() is None
    engine = create_embedder()
    assert isinstance(engine, EmbeddingsEngine)


def test_embedder_fixture(embedder: Any) -> None:
    from devops_cli.ai.rag.embeddings import create_embedder

    client = create_embedder()
    assert client is embedder
    vectors = client.embed_texts(["test text"])
    assert len(vectors) == 1


def test_a_scripted_failure_raises_once_and_the_embedder_answers_again(embedder: Any) -> None:
    embedder.fail_next(EmbeddingsError("Timeout embedding", is_transient=True))

    with pytest.raises(EmbeddingsError, match="Timeout embedding") as raised:
        embedder.embed_query("first")
    answered = embedder.embed_query("second")

    assert (raised.value.is_transient, len(answered)) == (True, 4)


def test_a_failed_embedder_raises_a_permanent_error_until_it_recovers(embedder: Any) -> None:
    embedder.fail("model is not served")

    with pytest.raises(EmbeddingsError, match="model is not served") as raised:
        embedder.embed_texts(["text"])
    embedder.recover()

    assert (raised.value.is_transient, len(embedder.embed_texts(["text"]))) == (False, 1)
