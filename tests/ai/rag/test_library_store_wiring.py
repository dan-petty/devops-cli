"""The library vector store is wired once, in `ai/rag/library_store.py` (#1329).

Qdrant, the embedder and Valkey come from their seams, so each test installs the fake of the
edge and no test patches a devops_cli name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.library_store import build_library_vector_store
from devops_cli.valkey.cache import shared_cache_tier

pytestmark = pytest.mark.usefixtures("keyring_store")

_CONFIGURED_QDRANT = "qdrant:\n  url: http://localhost:6333\n"


def test_a_dry_run_store_holds_no_client(tmp_path: Path) -> None:
    store = build_library_vector_store(tmp_path, dry_run=True)

    assert (store.qdrant_client, store.symbol_cache, store.embedder) == (None, None, None)


def test_the_live_store_holds_qdrant_the_embedder_and_the_valkey_tier(
    tmp_path: Path, qdrant: Any, embedder: Any, valkey: Any
) -> None:
    store = build_library_vector_store(tmp_path)

    assert (
        store.symbol_cache is not None,
        store.symbol_cache is shared_cache_tier(),
        store.qdrant_client is qdrant,
        store.embedder is embedder,
        store.local_contracts_dir,
    ) == (True, True, True, True, tmp_path)


def test_an_exact_lookup_needs_no_semantic_tier(
    tmp_path: Path, qdrant: Any, embedder: Any, valkey: Any
) -> None:
    store = build_library_vector_store(tmp_path, semantic_needed=False)

    assert (store.qdrant_client, store.embedder, store.symbol_cache is not None) == (
        None,
        None,
        True,
    )


def test_a_qdrant_that_does_not_answer_leaves_the_local_contracts_only(
    tmp_path: Path, qdrant: Any, embedder: Any, valkey: Any
) -> None:
    qdrant.refusing = True

    store = build_library_vector_store(tmp_path)

    assert (store.qdrant_client, store.embedder, store.symbol_cache is not None) == (
        None,
        None,
        True,
    )


def test_an_unconfigured_qdrant_leaves_the_local_contracts_only(
    tmp_path: Path, embedder: Any, valkey: Any, isolate_devops_cli_config: Path
) -> None:
    config = isolate_devops_cli_config
    config.write_text(config.read_text(encoding="utf-8").replace(_CONFIGURED_QDRANT, ""))

    store = build_library_vector_store(tmp_path)

    assert (store.qdrant_client, store.embedder) == (None, None)
