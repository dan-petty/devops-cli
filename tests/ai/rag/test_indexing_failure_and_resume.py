"""A failed embedding batch is retried, then skipped, stores no stand-in vector, and a later run
resumes; a permanent failure stops the run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.retriever import SemanticRetriever
from devops_cli.config.constants import CONST_EXIT_FAILURE
from devops_cli.config.settings import AIConfig

# A skipped batch waits once through the clock seam before its second attempt.
pytestmark = pytest.mark.usefixtures("keyring_store", "clock")


def _engine_with_no_endpoint() -> EmbeddingsEngine:
    """An engine that has no backend to ask, so it cannot embed any text."""
    return EmbeddingsEngine(AIConfig(provider="custom", ollama_urls=[]), valkey_client=None)


def _stored(qdrant: Any) -> set[str]:
    return {point["id"] for points in qdrant.collections.values() for point in points}


GATEWAY_TIMEOUT = "Gateway 504 Gateway Timeout"


def _reply_error(status: int | None, *, transient: bool) -> EmbeddingsError:
    """The `EmbeddingsError` of the engine for a reply with the HTTP `status`. With no status, a
    transient error is a timeout, and a permanent one is a malformed reply."""
    if status is not None:
        reason = GATEWAY_TIMEOUT if status == 504 else f"answered HTTP {status}"
    else:
        reason = (
            "failed: ReadTimeout: timed out" if transient else "returned 0 embeddings for 1 texts"
        )
    return EmbeddingsError(
        f"Embedding model m produced no embeddings: https://example.com/v1/embeddings {reason}",
        status=status,
        is_transient=transient,
    )


def _fail_on_batch(
    embedder: Any,
    number: int,
    *,
    failures: int | None = None,
    status: int | None = 504,
    transient: bool = True,
) -> list[list[str]]:
    """Make the embedder raise the error of a reply with `status` for the batch of its `number`th
    request, on each try or on the first `failures` tries, and return the tries of that batch."""
    requests = 0
    failing: list[str] | None = None
    tries: list[list[str]] = []

    def hook(texts: list[str], is_query: bool) -> None:
        nonlocal requests, failing
        requests += 1
        if requests == number:
            failing = texts
        if texts != failing:
            return
        tries.append(texts)
        if failures is None or len(tries) <= failures:
            raise _reply_error(status, transient=transient)

    embedder.before_embed = hook
    return tries


def _fail_each_batch(embedder: Any, status: int | None) -> list[list[str]]:
    """Make the embedder raise the permanent error of a reply with `status` for each request, and
    return the requests."""
    requests: list[list[str]] = []

    def hook(texts: list[str], is_query: bool) -> None:
        requests.append(texts)
        raise _reply_error(status, transient=False)

    embedder.before_embed = hook
    return requests


def _retry_waits(clock: Any) -> list[float]:
    """The waits before a second batch attempt: 10 s or more. The real git of the walk polls the
    exit of its child through `time.sleep`, with waits of milliseconds."""
    return [wait for wait in clock.waits if wait >= 10.0]


def _files(root: Path, count: int) -> None:
    """Write `file_a.py` and the next files up to `count`, each with one function of its name."""
    for letter in "abcdefg"[:count]:
        name = f"file_{letter}"
        (root / f"{name}.py").write_text(f"def {name}(): pass\n", encoding="utf-8")


def _three_files(root: Path) -> None:
    _files(root, 3)


def _fail_files(embedder: Any, errors: dict[str, EmbeddingsError]) -> list[list[str]]:
    """Make the embedder raise `errors[name]` for each request that holds the function `name`, and
    return those requests."""
    requests: list[list[str]] = []

    def hook(texts: list[str], is_query: bool) -> None:
        for name, error in errors.items():
            if any(f"def {name}()" in text for text in texts):
                requests.append(texts)
                raise error

    embedder.before_embed = hook
    return requests


def _time_out(*letters: str, status: int | None = 504) -> dict[str, EmbeddingsError]:
    """The transient error of a reply with `status` for the file of each of `letters`."""
    return {f"file_{letter}": _reply_error(status, transient=True) for letter in letters}


def _code_files(qdrant: Any) -> set[str]:
    return {p["payload"]["file_path"] for p in qdrant.collections["devops_code"]}


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


@pytest.mark.parametrize("status", [504, 429, None], ids=["server-error", "rate-limit", "timeout"])
def test_a_batch_that_fails_each_try_is_skipped_and_the_run_exits_1_naming_its_file(
    tmp_path: Path, qdrant: Any, embedder: Any, clock: Any, status: int | None
) -> None:
    """A transient failure gets one more attempt. The other batches are indexed, the run exits 1
    at the end with the file it did not index, and the next run embeds that file (#6717)."""
    _three_files(tmp_path)
    embedder.batch_size = 1
    tries = _fail_on_batch(embedder, 2, status=status)
    cache_dir = tmp_path / ".cache"
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=cache_dir)

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, include_kb=False)
    stored_after_failure = _code_files(qdrant)
    embedder.before_embed = None
    resumed = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=cache_dir)
    result = resumed.index_workspace(tmp_path, include_kb=False, force=False)

    error = exc_info.value
    assert (error.exit_code, len(tries), len(_retry_waits(clock))) == (CONST_EXIT_FAILURE, 2, 1)
    assert (_reply_error(status, transient=True).message in error.message) is True
    assert error.details["skipped_files"] == ["file_b.py"]
    assert stored_after_failure == {"file_a.py", "file_c.py"}
    assert (result["indexed_files"], result["skipped_files"]) == (1, 2)


@pytest.mark.parametrize(
    ("number", "status"),
    [(1, 400), (2, 413), (3, 422)],
    ids=["first-batch-400", "middle-batch-413", "last-batch-422"],
)
def test_a_batch_whose_input_the_endpoint_refuses_is_skipped_with_no_retry(
    tmp_path: Path, qdrant: Any, embedder: Any, clock: Any, number: int, status: int
) -> None:
    """A reply that refuses the input of one batch, such as a text that is too long, repeats on
    each try. The run skips the batch at once and indexes the others (#6717)."""
    _three_files(tmp_path)
    embedder.batch_size = 1
    tries = _fail_on_batch(embedder, number, status=status, transient=False)
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=tmp_path / ".cache")

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, include_kb=False)

    refused = f"file_{'abc'[number - 1]}.py"
    error = exc_info.value
    assert (error.exit_code, len(tries), _retry_waits(clock)) == (CONST_EXIT_FAILURE, 1, [])
    assert (f"answered HTTP {status}" in error.message, error.details["skipped_files"]) == (
        True,
        [refused],
    )
    assert _code_files(qdrant) == {"file_a.py", "file_b.py", "file_c.py"} - {refused}


def test_two_refused_batches_before_an_embedded_batch_end_the_run(
    tmp_path: Path, qdrant: Any, embedder: Any, clock: Any
) -> None:
    """The LiteLLM proxy also answers an unknown model with HTTP 400. Two refused batches and no
    embedded batch point to the model, so the run stops at the second batch (#6717)."""
    _three_files(tmp_path)
    embedder.batch_size = 1
    requests = _fail_each_batch(embedder, 400)
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=tmp_path / ".cache")

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, include_kb=False)

    assert (len(requests), _retry_waits(clock), _code_files(qdrant)) == (2, [], set())
    assert (exc_info.value.exit_code, exc_info.value.status) == (CONST_EXIT_FAILURE, 400)
    assert "Failed to embed batch from 'file_b.py'" in exc_info.value.message


def test_a_batch_that_the_retry_embeds_is_indexed(
    tmp_path: Path, qdrant: Any, embedder: Any, clock: Any
) -> None:
    _three_files(tmp_path)
    embedder.batch_size = 1
    tries = _fail_on_batch(embedder, 2, failures=1)
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=tmp_path / ".cache")

    result = indexer.index_workspace(tmp_path, include_kb=False)

    assert (result["indexed_files"], len(tries), len(_retry_waits(clock))) == (3, 2, 1)
    assert _code_files(qdrant) == {"file_a.py", "file_b.py", "file_c.py"}


def test_a_skipped_code_batch_does_not_stop_the_docs_collection(
    tmp_path: Path, qdrant: Any, embedder: Any, clock: Any
) -> None:
    """The symptom of #6717: a code batch that timed out ended the run before the docs phase, so
    `devops_docs` stayed empty."""
    _files(tmp_path, 2)
    (tmp_path / "guide.md").write_text("# Guide\n\nRun the app.\n", encoding="utf-8")
    embedder.batch_size = 1
    _fail_files(embedder, _time_out("b", status=None))
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=tmp_path / ".cache")

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, include_kb=False)

    docs = {p["payload"]["file_path"] for p in qdrant.collections["devops_docs"]}
    assert (exc_info.value.details["skipped_files"], _code_files(qdrant), docs) == (
        ["file_b.py"],
        {"file_a.py"},
        {"guide.md"},
    )


@pytest.mark.parametrize("status", [504, 429, None], ids=["server-error", "rate-limit", "timeout"])
def test_a_transient_failure_of_the_first_batch_ends_the_run(
    tmp_path: Path, qdrant: Any, embedder: Any, clock: Any, status: int | None
) -> None:
    """An endpoint that fails the first batch of a run, before any batch got vectors, is down. The
    run stops after the two tries of that batch, and does not wait on each later batch."""
    _three_files(tmp_path)
    embedder.batch_size = 1
    requests = _fail_files(embedder, _time_out("a", "b", "c", status=status))
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=tmp_path / ".cache")

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, include_kb=False)

    error = exc_info.value
    assert (error.exit_code, len(requests), len(_retry_waits(clock))) == (CONST_EXIT_FAILURE, 2, 1)
    assert (error.details["skipped_files"], _stored(qdrant)) == (["file_a.py"], set())
    assert (_reply_error(status, transient=True).message in error.message) is True


def test_three_batches_in_a_row_that_fail_end_the_run(
    tmp_path: Path, qdrant: Any, embedder: Any, clock: Any
) -> None:
    """An endpoint that goes down in a run fails each later batch. After three batches in a row
    fail both tries, the run stops and sends no request for the other files."""
    _files(tmp_path, 6)
    embedder.batch_size = 1
    requests = _fail_files(embedder, _time_out("b", "c", "d", "e", "f"))
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=tmp_path / ".cache")

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, include_kb=False)

    error = exc_info.value
    assert (error.exit_code, len(requests), len(_retry_waits(clock))) == (CONST_EXIT_FAILURE, 6, 3)
    assert error.details["skipped_files"] == ["file_b.py", "file_c.py", "file_d.py"]
    assert (GATEWAY_TIMEOUT in error.message, _code_files(qdrant)) == (True, {"file_a.py"})


@pytest.mark.parametrize("between", ["embedded", "refused"])
def test_a_batch_that_the_endpoint_answers_sets_the_count_of_failed_batches_to_0(
    tmp_path: Path, qdrant: Any, embedder: Any, clock: Any, between: str
) -> None:
    """Two failed batches, a batch that gets vectors or whose input the endpoint refuses, and two
    more failed batches are not three failed batches in a row: the run goes on to the last file."""
    _files(tmp_path, 7)
    embedder.batch_size = 1
    errors = _time_out("b", "c", "e", "f")
    if between == "refused":
        errors["file_d"] = _reply_error(400, transient=False)
    _fail_files(embedder, errors)
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=tmp_path / ".cache")

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, include_kb=False)

    skipped = sorted(f"{name}.py" for name in errors)
    assert exc_info.value.details["skipped_files"] == skipped
    assert _code_files(qdrant) == {f"file_{letter}.py" for letter in "abcdefg"} - set(skipped)


@pytest.mark.parametrize(
    "status", [401, 403, 404, None], ids=["unauthorized", "forbidden", "not-found", "no-status"]
)
def test_a_permanent_failure_ends_the_run_with_no_retry(
    tmp_path: Path, qdrant: Any, embedder: Any, clock: Any, status: int | None
) -> None:
    """A refused key, an unserved model or a malformed reply fails each batch, so the run stops at
    the first one and asks no more."""
    _three_files(tmp_path)
    embedder.batch_size = 1
    requests = _fail_each_batch(embedder, status)
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=tmp_path / ".cache")

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, include_kb=False)

    assert (len(requests), _retry_waits(clock), exc_info.value.exit_code) == (
        1,
        [],
        CONST_EXIT_FAILURE,
    )
    assert "Failed to embed batch from 'file_a.py'" in exc_info.value.message


def _interrupted_index(tmp_path: Path, qdrant: Any, embedder: Any) -> tuple[Path, Path]:
    """A multi-chunk big.py beside a one-chunk small.py, and the cache that a batch inside big.py
    left when it failed both tries; small.py keeps the project in later scans."""
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


def test_a_resume_with_no_cache_file_embeds_the_partly_stored_file_and_skips_the_others(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    """The store, not a cache file, shows that big.py lacks a chunk, as in a new ingest pod."""
    big, _ = _interrupted_index(tmp_path, qdrant, embedder)
    embedded = len(embedder.calls)

    resumed = _resume(tmp_path, qdrant, embedder, tmp_path / ".new-pod-cache")

    texts = sorted(text for batch, _ in embedder.calls[embedded:] for text in batch)
    big_chunks = resumed.chunker.chunk_file(big, relative_to=tmp_path.resolve(), project_name="p")
    assert texts == sorted(chunk.content for chunk in big_chunks)
    assert _chunk_ids(resumed, big, tmp_path) - _stored(qdrant) == set()


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
