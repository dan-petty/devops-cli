"""`retrieve_rag_context`: the grounding text the AI commands add to a prompt, over the fakes (#1329).

The investigation itself is held by `tests/ai/rag/test_investigation_context.py`. These cases hold
what the command helper adds: the settings switch, the knowledge base check and the answer of
`None` for every failure.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.investigator import clear_investigation_cache
from devops_cli.commands.ai import retrieve_rag_context
from tests.support.fakes.qdrant import seed_chunk, seed_knowledge_base

pytestmark = pytest.mark.usefixtures("keyring_store")

QUERY = "class LLMClient: pass"


@pytest.fixture(autouse=True)
def _fresh_investigation_cache() -> None:
    clear_investigation_cache()


def test_a_disabled_rag_returns_none_and_sends_no_request(
    config: Callable[..., Path], qdrant: Any, embedder: Any
) -> None:
    config(ai={"rag": {"enabled": False}})

    assert retrieve_rag_context(QUERY) is None
    assert (qdrant.calls, embedder.calls) == ([], [])


def test_a_matching_chunk_is_returned_as_prompt_text(
    config: Callable[..., Path], qdrant: Any, embedder: Any
) -> None:
    config(ai={"rag": {"enabled": True}})
    seed_knowledge_base(qdrant, embedding_model=embedder.model)
    seed_chunk(qdrant, embedder, QUERY, file_path="src/devops_cli/ai/client.py")

    text = retrieve_rag_context(QUERY)

    assert text is not None
    assert ("class LLMClient: pass" in text, "src/devops_cli/ai/client.py" in text) == (True, True)


def test_an_unreachable_qdrant_returns_none(
    config: Callable[..., Path], qdrant: Any, embedder: Any
) -> None:
    config(ai={"rag": {"enabled": True}})
    qdrant.refusing = True

    assert retrieve_rag_context(QUERY) is None


def test_a_knowledge_base_that_cannot_be_embedded_returns_none(
    config: Callable[..., Path], qdrant: Any, embedder: Any
) -> None:
    config(ai={"rag": {"enabled": True}})
    embedder.fail("model not served")

    assert retrieve_rag_context(QUERY) is None
