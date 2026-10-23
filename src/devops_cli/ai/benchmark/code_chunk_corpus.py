"""A code-retrieval corpus for the embedding benchmark: each code chunk queried as the index is."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from devops_cli.ai.benchmark.document_chunker import SectionRetrievalTask
from devops_cli.ai.rag.chunker import SemanticChunker
from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.models import CodeChunk
from devops_cli.ai.run_store import digest, file_digest
from devops_cli.config.constants import (
    CONST_CHUNK_MODULE_PREAMBLE_SYMBOL,
    CONST_INDEX_LOOKUP_SYMBOLS,
)
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import ERRORS


def _code_chunk_query(chunk: CodeChunk) -> str:
    """The chunk's path and its first symbol names: the lookup `outlines` makes for a file."""
    return " ".join([chunk.file_path, *chunk.symbol_names[:CONST_INDEX_LOOKUP_SYMBOLS]])


def _defines_a_symbol(chunk: CodeChunk) -> bool:
    """Whether the chunk defines something a lookup can name: a symbol other than the marker the
    chunker puts on a file's preamble, whose content has neither the path nor the marker in it."""
    return any(name != CONST_CHUNK_MODULE_PREAMBLE_SYMBOL for name in chunk.symbol_names)


def _evenly_spaced[Item](items: list[Item], count: int) -> list[Item]:
    """`count` of the items, spread evenly across them, or all of them when there are no more."""
    if len(items) <= count:
        return items
    return [items[position * len(items) // count] for position in range(count)]


def load_code_chunk_corpus(
    code_dir: Path, sample_count: int
) -> tuple[list[SectionRetrievalTask], list[str]]:
    """The retrieval tasks and the corpus they rank, from the code chunks under `code_dir`.

    The corpus is the content of every chunk the workspace indexer would put in its code
    collection, taken from the files it collects and split by the chunker it uses; documentation
    is left out. A chunk can be a target when it defines a symbol and no other chunk's query is
    the same, since a query with two right answers has no single target; a file's preamble stays
    in the corpus as a distractor. Its query is its path relative to `code_dir` and its first
    symbol names, so no label, model or score is involved.
    `sample_count` targets, evenly spaced, become the tasks, each aimed at its index in the corpus.
    """
    root = code_dir.resolve()
    chunker = SemanticChunker()
    chunks = [
        chunk
        for path in WorkspaceIndexer.collect_files(root)
        for chunk in chunker.chunk_file(path, relative_to=root)
        if chunk.category != "docs"
    ]
    queries = [_code_chunk_query(chunk) for chunk in chunks]
    shared = Counter(queries)
    targets = [
        index
        for index, chunk in enumerate(chunks)
        if _defines_a_symbol(chunk) and shared[queries[index]] == 1
    ]
    if not targets:
        raise ValidationError(ERRORS.ai.benchmark_no_code_queries.format(path=root), field="code")
    tasks = [
        SectionRetrievalTask(
            id=f"code-task-{number}",
            target_section_index=index,
            target_heading=(
                f"{chunks[index].file_path}:{chunks[index].start_line}-{chunks[index].end_line}"
            ),
            query=queries[index],
            target_passage=chunks[index].content,
            category=chunks[index].category,
        )
        for number, index in enumerate(_evenly_spaced(targets, sample_count), 1)
    ]
    return tasks, [chunk.content for chunk in chunks]


def code_tree_digest(code_dir: Path) -> str:
    """A short digest of the files under `code_dir` the corpus is drawn from: each one's path
    relative to the directory and its bytes, so it changes when a file does and not with the
    way the directory is spelled or where it lies."""
    root = code_dir.resolve()
    return digest(
        {
            path.relative_to(root).as_posix(): file_digest(path)
            for path in WorkspaceIndexer.collect_files(root)
        }
    )
