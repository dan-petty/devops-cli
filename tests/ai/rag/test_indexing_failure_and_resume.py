"""A failed embedding stops an index run, stores no stand-in vector, and a later run resumes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.retriever import SemanticRetriever
from devops_cli.config.constants import CONST_EXIT_FAILURE
from devops_cli.config.settings import AIConfig

pytestmark = pytest.mark.usefixtures("keyring_store")


def _engine_with_no_endpoint() -> EmbeddingsEngine:
    """An engine that has no backend to ask, so it cannot embed any text."""
    return EmbeddingsEngine(AIConfig(provider="custom", ollama_urls=[]), valkey_client=None)


def _stored(qdrant: Any) -> set[str]:
    return {point["id"] for points in qdrant.collections.values() for point in points}


def _fail_on_batch(embedder: Any, number: int) -> None:
    """Make the embedder raise a gateway timeout on its `number`th request."""
    requests = 0

    def hook(texts: list[str], is_query: bool) -> None:
        nonlocal requests
        requests += 1
        if requests == number:
            raise RuntimeError("Gateway 504 Gateway Timeout")

    embedder.before_embed = hook


def test_a_query_that_cannot_be_embedded_fails_the_search(qdrant: Any) -> None:
    """Search and context retrieval raise the EmbeddingsError instead of searching with nothing.

    An empty result would read as "nothing relevant is indexed", and Qdrant is never asked.
    """
    engine = _engine_with_no_endpoint()
    retriever = SemanticRetriever(qdrant=qdrant, embedder=engine)

    with pytest.raises(EmbeddingsError) as from_search:
        retriever.search("how to run app")
    with pytest.raises(EmbeddingsError) as from_context:
        retriever.retrieve_context("how to run app")

    assert (from_search.value.details, from_context.value.details) == (
        {"model": engine.model, "provider": "custom"},
        {"model": engine.model, "provider": "custom"},
    )
    assert [call for call in qdrant.calls if call[0] == "search_points"] == []


def test_indexing_text_the_model_cannot_embed_raises_and_stores_nothing(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    """Indexing raises the EmbeddingsError and upserts no point, so no stand-in vector is stored.

    The file is not recorded as indexed either, so the next run retries it.
    """
    (tmp_path / "app.py").write_text("def run_app():\n    print('app running')\n", "utf-8")
    engine = _engine_with_no_endpoint()
    cache_dir = tmp_path / ".cache"
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=engine, cache_dir=cache_dir)

    with pytest.raises(EmbeddingsError) as raised:
        indexer.index_workspace(tmp_path, include_kb=False)
    retry = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=cache_dir).index_workspace(
        tmp_path, include_kb=False
    )

    assert raised.value.details["model"] == engine.model
    assert (retry["indexed_files"], retry["skipped_files"]) == (1, 0)


def test_a_failed_second_batch_ends_with_exit_1_and_keeps_the_first_batch(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    """A failed batch ends the run with exit 1 naming the files, and earlier batches stay for resume."""
    for name in ("file_a", "file_b", "file_c"):
        (tmp_path / f"{name}.py").write_text(f"def {name}(): pass\n", encoding="utf-8")
    embedder.batch_size = 1
    _fail_on_batch(embedder, 2)
    cache_dir = tmp_path / ".cache"
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=cache_dir)

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, include_kb=False)
    stored_after_failure = {p["payload"]["file_path"] for p in qdrant.collections["devops_code"]}
    embedder.before_embed = None
    resumed = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=cache_dir)
    result = resumed.index_workspace(tmp_path, include_kb=False, force=False)

    assert exc_info.value.exit_code == CONST_EXIT_FAILURE
    assert "Failed to embed batch from" in exc_info.value.message
    assert "Gateway 504 Gateway Timeout" in exc_info.value.message
    assert stored_after_failure == {"file_a.py"}
    assert (result["indexed_files"], result["skipped_files"]) == (2, 1)


def _interrupted_index(tmp_path: Path, qdrant: Any, embedder: Any) -> tuple[Path, Path]:
    """A multi-chunk big.py beside a one-chunk small.py, and the cache an embedding failure
    inside big.py left; small.py keeps the project in later scans."""
    (tmp_path / "small.py").write_text("def small():\n    return 1\n", encoding="utf-8")
    big = tmp_path / "big.py"
    big.write_text(
        "".join(
            f"def func_{n}():\n" + "".join(f"    value_{i} = {i}\n" for i in range(59))
            for n in range(4)
        ),
        encoding="utf-8",
    )
    embedder.batch_size = 1
    _fail_on_batch(embedder, 3)
    cache_dir = tmp_path / ".cache"
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=cache_dir)
    with pytest.raises(EmbeddingsError) as raised:
        indexer.index_workspace(tmp_path, project="p", include_kb=False)
    assert raised.value.error_code == "EMBEDDINGS_ERROR"
    embedder.before_embed = None
    return big, cache_dir


def _resume(tmp_path: Path, qdrant: Any, embedder: Any, cache_dir: Path) -> WorkspaceIndexer:
    resumed = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=cache_dir)
    resumed.index_workspace(tmp_path, project="p", include_kb=False)
    return resumed


def _chunk_ids(indexer: WorkspaceIndexer, path: Path, root: Path) -> set[str]:
    return {
        c.id for c in indexer.chunker.chunk_file(path, relative_to=root.resolve(), project_name="p")
    }


def test_a_failed_batch_inside_a_file_leaves_that_file_for_resume(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    """A file whose chunks span a failed batch is retried whole, so a resume stores all of them."""
    big, cache_dir = _interrupted_index(tmp_path, qdrant, embedder)
    resumed = _resume(tmp_path, qdrant, embedder, cache_dir)

    expected = _chunk_ids(resumed, big, tmp_path)

    assert (len(expected) > 1, expected - _stored(qdrant)) == (True, set())


def test_a_partly_stored_file_deleted_before_the_resume_leaves_no_points(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    big, cache_dir = _interrupted_index(tmp_path, qdrant, embedder)
    big.unlink()

    resumed = _resume(tmp_path, qdrant, embedder, cache_dir)

    assert _stored(qdrant) == _chunk_ids(resumed, tmp_path / "small.py", tmp_path)


def test_a_partly_stored_file_edited_before_the_resume_keeps_only_its_new_chunks(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    big, cache_dir = _interrupted_index(tmp_path, qdrant, embedder)
    big.write_text("# edited\n" * 5 + big.read_text(encoding="utf-8"), encoding="utf-8")

    resumed = _resume(tmp_path, qdrant, embedder, cache_dir)

    assert _stored(qdrant) == _chunk_ids(resumed, big, tmp_path) | _chunk_ids(
        resumed, tmp_path / "small.py", tmp_path
    )
