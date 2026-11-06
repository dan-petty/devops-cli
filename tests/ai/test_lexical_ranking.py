"""Sparse lexical ranking: tokens and BM25 scores."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from devops_cli.ai.lexical import LexicalMatch, bm25_scores, tokenize


def test_tokenize_lowercases_and_splits_on_word_boundaries() -> None:
    """Tokens are lowercase words, with punctuation dropped."""
    assert tokenize("Set_Cached(key, TTL=30)") == ["set_cached", "key", "ttl", "30"]


def test_bm25_ranks_the_document_containing_the_query_term_first() -> None:
    """A literal term match outranks documents that never mention it."""
    documents = [
        "the connection pool manages sockets",
        "authentication uses a bearer token for each request",
        "generic helper utilities and shared formatting",
    ]
    ranked = bm25_scores("bearer token", documents)

    assert ranked[0].index == 1
    assert ranked[0].score > 0.0


def test_bm25_omits_documents_with_no_matching_terms() -> None:
    """A zero score means no query term appeared, not a tie at the bottom."""
    ranked = bm25_scores("kubernetes", ["postgres replication", "redis eviction"])
    assert ranked == []


def test_bm25_returns_nothing_for_empty_input() -> None:
    """Empty queries, corpora, and punctuation-only queries all yield no ranking."""
    assert bm25_scores("", ["content"]) == []
    assert bm25_scores("query", []) == []
    assert bm25_scores("!!! ???", ["content"]) == []


def test_bm25_skips_empty_documents() -> None:
    """A document with no tokens cannot match and is excluded."""
    ranked = bm25_scores("token", ["", "a bearer token"])
    assert [match.index for match in ranked] == [1]


def test_bm25_rewards_term_frequency() -> None:
    """A document mentioning the term more often scores higher."""
    ranked = bm25_scores("cache", ["cache cache cache layer", "cache layer"])
    assert ranked[0].index == 0


def test_bm25_discounts_terms_common_to_every_document() -> None:
    """A term appearing everywhere carries little discriminating weight.

    Inverse document frequency is what stops a ubiquitous word from dominating the
    ranking, so the rarer term must decide the order.
    """
    documents = [
        "cache layer for vectors",
        "cache layer for embeddings",
        "cache layer for quantization",
    ]
    ranked = bm25_scores("cache quantization", documents)
    assert ranked[0].index == 2


def test_bm25_honours_the_result_limit() -> None:
    """The ranking is truncated to the requested number of matches."""
    ranked = bm25_scores("token", ["token a", "token b", "token c"], limit=2)
    assert len(ranked) == 2


def test_bm25_ranking_is_deterministic_for_tied_scores() -> None:
    """Equal scores fall back to input order, so results never shuffle between runs."""
    documents = ["token alpha", "token beta"]
    first = [m.index for m in bm25_scores("token", documents)]
    second = [m.index for m in bm25_scores("token", documents)]
    assert first == second


def test_lexical_match_is_immutable() -> None:
    """A scored match cannot be mutated after ranking."""
    match = LexicalMatch(index=0, score=1.0)
    with pytest.raises(FrozenInstanceError) as raised:
        match.score = 2.0  # type: ignore[misc]
    assert "cannot assign" in str(raised.value).lower() or "frozen" in str(raised.value).lower()
