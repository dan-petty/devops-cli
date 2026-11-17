"""The offline scorer of the gold set against one retrieval source (#3902).

`score_gold_set` holds the documents of one source in Qdrant and ranks them for each question of
the gold set through the `search` method of `SemanticRetriever`, which is the ranking that the
review loop uses. It reports the hit rate at k=5, the depth that the loop injects, and the share
of the entries that `mark_stale_entries` marked stale. `format_score_block` writes the Markdown
block that a person pastes into a pull request.

The two built-in sources are the checked-in knowledge base folder and the project digest that the
benchmark corpus builds from `docs/`. The scorer reaches Qdrant and the embedding model through
the seams of the retriever, so a test installs the fake client and the fake embedder and no
network call runs.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.benchmark.document_chunker import document_corpus_paths
from devops_cli.ai.benchmark.gold_set import GoldSet, GoldSetEntry
from devops_cli.ai.rag.embeddings import EmbedderProtocol
from devops_cli.ai.rag.retriever import SemanticRetriever

if TYPE_CHECKING:
    from devops_cli.ai.rag.qdrant import QdrantClient

# The depth of the ranked list that the review loop injects, and so the k of the hit rate.
_GOLD_SET_K = 5
# The collection that holds the documents of one scored source. It is a collection of its own, so
# the scorer neither reads nor disturbs the index of the project.
_GOLD_SET_COLLECTION = "devops_gold_set"
# The project name that each scored point carries, so a scored point is no point of the project.
_GOLD_SET_PROJECT = "gold-set"
# The header of the Markdown score block, and the alignment row that follows it.
_SCORE_BLOCK_HEADER = (
    "| Source | Hit rate at k=5 | Stale share | Hits | Entries |",
    "| :--- | ---: | ---: | ---: | ---: |",
)


class GoldSetDocument(BaseModel):
    """One document of a retrieval source, which a question of the gold set may hit (#3902)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(
        description="The path of the document, relative to the repository root, which a gold-set "
        "entry names as its expected source."
    )
    text: str = Field(description="The text that the scorer embeds and holds in Qdrant.")


class GoldSetScore(BaseModel):
    """The hit rate at k=5 and the stale share of the gold set against one source (#3902)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(description="The name of the scored retrieval source, as its row shows it.")
    entries: int = Field(description="The number of entries that the scorer searched.")
    hits: int = Field(description="The number of entries whose expected source is in the top five.")
    stale: int = Field(description="The number of entries that the stale marking marked.")
    hit_rate_at_5: float = Field(
        description="The number of hits divided by the number of entries, from 0 to 1."
    )
    stale_share: float = Field(
        description="The number of stale entries divided by the number of entries, from 0 to 1."
    )


def knowledge_base_source(kb_dir: Path, *, repo_root: Path) -> list[GoldSetDocument]:
    """One document for each Markdown article of the knowledge base folder at `kb_dir` (#3902).

    Each document path is relative to `repo_root`, which is how a gold-set entry names its expected
    source.
    """
    articles = (
        path
        for path in sorted(kb_dir.rglob("*.md"))
        if path.is_file() and not path.is_symlink() and not path.name.startswith(".")
    )
    return _documents(articles, repo_root)


def project_digest_source(repo_root: Path) -> list[GoldSetDocument]:
    """One document for each page of the benchmark corpus under `repo_root` (#3902).

    The corpus is the docs directory, which holds the generated knowledge base index, the
    top-level documents and the task prompts. One document holds a whole page, so its path stays
    the path that a gold-set entry names.
    """
    return _documents(document_corpus_paths(repo_root), repo_root)


def score_gold_set(
    gold_set: GoldSet,
    documents: Sequence[GoldSetDocument],
    *,
    source: str,
    qdrant: QdrantClient,
    embedder: EmbedderProtocol,
    collection: str = _GOLD_SET_COLLECTION,
) -> GoldSetScore:
    """Score `source` on `gold_set` with the documents that it holds (#3902).

    The collection is dropped first, so a document that the source no longer holds leaves no point
    behind, and each document then becomes one point with the embedder's vector, its path and the
    embedder's model. A hit is an entry whose expected source is one of the five results that the
    retriever ranks for its question.
    """
    _index_documents(qdrant, embedder, collection, documents)
    retriever = _retriever(qdrant, embedder, collection)
    hits = sum(1 for entry in gold_set.entries if _is_hit(retriever, collection, entry))
    entries = len(gold_set.entries)
    stale = sum(1 for entry in gold_set.entries if entry.stale)
    return GoldSetScore(
        source=source,
        entries=entries,
        hits=hits,
        stale=stale,
        hit_rate_at_5=_share(hits, entries),
        stale_share=_share(stale, entries),
    )


def format_score_block(scores: Sequence[GoldSetScore]) -> str:
    """The Markdown block that holds one row for each scored source (#3902)."""
    lines = list(_SCORE_BLOCK_HEADER)
    for score in scores:
        lines.append(
            f"| {score.source} | {score.hit_rate_at_5:.3f} | {score.stale_share:.3f} "
            f"| {score.hits} | {score.entries} |"
        )
    return "\n".join(lines)


def _documents(paths: Iterable[Path], repo_root: Path) -> list[GoldSetDocument]:
    """The documents that the readable, non-empty pages of `paths` hold."""
    documents: list[GoldSetDocument] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if text.strip():
            documents.append(GoldSetDocument(path=_relative_path(path, repo_root), text=text))
    return documents


def _relative_path(path: Path, repo_root: Path) -> str:
    """`path` relative to `repo_root`, or its own text when it is not below the root."""
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _index_documents(
    qdrant: QdrantClient,
    embedder: EmbedderProtocol,
    collection: str,
    documents: Sequence[GoldSetDocument],
) -> None:
    """Hold one point for each document in `collection`, with the embedder's vector."""
    qdrant.delete_collection(collection)
    if not documents:
        return
    vectors = embedder.embed_texts([document.text for document in documents])
    model = _embedding_model(embedder)
    qdrant.ensure_collection(collection, len(vectors[0]))
    qdrant.upsert_points(
        collection,
        [
            _point(document, vector, model)
            for document, vector in zip(documents, vectors, strict=True)
        ],
    )


def _point(document: GoldSetDocument, vector: list[float], model: str) -> dict[str, Any]:
    """The Qdrant point of one document, with the payload that the retriever reads back."""
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, document.path)),
        "vector": vector,
        "payload": {
            "file_path": document.path,
            "start_line": 1,
            "end_line": max(1, document.text.count("\n") + 1),
            "content": document.text,
            "language": "markdown",
            "doc_type": "docs",
            "category": "docs",
            "project_name": _GOLD_SET_PROJECT,
            "embedding_model": model,
        },
    }


def _embedding_model(embedder: EmbedderProtocol) -> str:
    """The model name that a point records, which a search reads back to check the collection."""
    model = getattr(embedder, "model", getattr(embedder, "model_name", ""))
    return model if isinstance(model, str) else ""


def _retriever(
    qdrant: QdrantClient, embedder: EmbedderProtocol, collection: str
) -> SemanticRetriever:
    """The retriever that ranks one collection of scored documents, at the depth of the loop."""
    return SemanticRetriever(
        qdrant,
        embedder,
        code_collection=collection,
        docs_collection=collection,
        default_top_k=_GOLD_SET_K,
        default_score_threshold=0.0,
    )


def _is_hit(retriever: SemanticRetriever, collection: str, entry: GoldSetEntry) -> bool:
    """Whether the top five results of the entry's question hold its expected source."""
    results = retriever.search(
        entry.question,
        top_k=_GOLD_SET_K,
        score_threshold=0.0,
        collection=collection,
        rerank=False,
        hybrid=False,
    )
    return any(result.chunk.file_path == entry.expected_source for result in results)


def _share(part: int, total: int) -> float:
    """`part` of `total` as a number from 0 to 1, and 0.0 when the set holds no entry."""
    return part / total if total else 0.0


__all__ = [
    "GoldSetDocument",
    "GoldSetScore",
    "format_score_block",
    "knowledge_base_source",
    "project_digest_source",
    "score_gold_set",
]
