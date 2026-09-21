"""Sparse lexical ranking shared by conversation search and RAG hybrid retrieval.

Dense vector similarity captures meaning but routinely misses exact token matches — an
error code, a flag name, a symbol like ``_set_cached`` — because the embedding smooths
over precisely the characters that make the query specific. BM25 scores those literal
matches, and fusing the two rankings recovers what either alone would drop.

The scoring lives here rather than beside a caller so both consumers share one
implementation, and a correction to the ranking benefits both.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from devops_cli.config.defaults import (
    DEFAULT_BM25_B,
    DEFAULT_BM25_K1,
)

_TOKEN_REGEX = re.compile(r"\w+")


@dataclass(frozen=True)
class LexicalMatch:
    """One scored document, identified by its position in the input sequence."""

    index: int
    score: float


def tokenize(text: str) -> list[str]:
    """Split text into lowercase word tokens."""
    return _TOKEN_REGEX.findall(text.lower())


def _inverse_document_frequency(total_docs: int, doc_frequency: int) -> float:
    """Compute the BM25 IDF weight for a term, floored so it never goes negative."""
    ratio = max(0.0, (total_docs - doc_frequency + 0.5) / (doc_frequency + 0.5)) + 1.0
    return math.log(ratio)


def _score_document(
    terms: Sequence[str],
    tokens: Sequence[str],
    doc_length: int,
    doc_frequencies: dict[str, int],
    total_docs: int,
    avg_length: float,
    k1: float,
    b: float,
) -> float:
    """Score one document against the query terms."""
    term_counts: dict[str, int] = defaultdict(int)
    for token in tokens:
        term_counts[token] += 1

    score = 0.0
    for term in terms:
        frequency = term_counts.get(term, 0)
        if frequency == 0:
            continue
        idf = _inverse_document_frequency(total_docs, doc_frequencies.get(term, 0))
        denominator = frequency + k1 * (1.0 - b + b * (doc_length / max(0.0001, avg_length)))
        score += idf * (frequency * (k1 + 1.0)) / max(0.0001, denominator)
    return score


def bm25_scores(
    query: str,
    documents: Sequence[str],
    *,
    k1: float = DEFAULT_BM25_K1,
    b: float = DEFAULT_BM25_B,
    limit: int | None = None,
) -> list[LexicalMatch]:
    """Rank documents against a query using BM25, best match first.

    Documents scoring zero are omitted, so an empty result means no query term appeared
    rather than that everything tied.
    """
    clean_query = query.strip().lower()
    if not clean_query or not documents:
        return []

    terms = list(dict.fromkeys(_TOKEN_REGEX.findall(clean_query)))
    if not terms:
        return []

    doc_tokens = [tokenize(doc) for doc in documents]
    doc_lengths = [len(tokens) for tokens in doc_tokens]
    total_docs = len(documents)
    avg_length = sum(doc_lengths) / max(1, total_docs)
    doc_frequencies = {term: sum(1 for tokens in doc_tokens if term in tokens) for term in terms}

    matches = [
        LexicalMatch(
            index=index,
            score=_score_document(
                terms,
                tokens,
                length,
                doc_frequencies,
                total_docs,
                avg_length,
                k1,
                b,
            ),
        )
        for index, (tokens, length) in enumerate(zip(doc_tokens, doc_lengths, strict=True))
        if length > 0
    ]

    ranked = sorted(
        (match for match in matches if match.score > 0.0),
        key=lambda match: (-match.score, match.index),
    )
    return ranked[:limit] if limit is not None else ranked


__all__ = [
    "LexicalMatch",
    "bm25_scores",
    "tokenize",
]
