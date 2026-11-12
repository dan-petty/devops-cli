"""Tests of the benchmark's numpy ranking and its pytrec_eval retrieval metrics (#1928)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy
import pytest

from devops_cli.ai.vector_similarity import cosine_similarity

if TYPE_CHECKING:
    from pytest import MonkeyPatch

# Two query vectors and four corpus vectors, none of unit length, so a raw matrix product
# would score each pair differently from the cosine.
_QUERY_VECTORS = [[1.0, 2.0, 0.0], [0.0, 1.0, 3.0]]
_CORPUS_VECTORS = [
    [2.0, 0.0, 1.0],
    [1.0, 1.0, 1.0],
    [0.0, 4.0, 1.0],
    [3.0, 0.0, 0.0],
]

# One query direction and six corpus vectors whose cosine to it falls as the second
# coordinate grows, so target 0 ranks first, target 2 third and target 5 sixth.
_ORDERED_CORPUS_VECTORS = [[1.0, y] for y in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)]
_ORDERED_QUERY_VECTORS = [[1.0, 0.0] for _ in range(3)]
_ORDERED_TARGET_INDICES = [0, 2, 5]


def _reference_metrics(
    query_vectors: list[list[float]],
    corpus_vectors: list[list[float]],
    target_indices: list[int],
    k: int = 5,
) -> tuple[float, float, float, float, float]:
    """The five metrics that the pairwise loop of the runner computed before #1928."""
    top1_hits = top3_hits = top5_hits = 0
    reciprocal_ranks: list[float] = []
    ndcg_scores: list[float] = []
    for q_vec, target_idx in zip(query_vectors, target_indices, strict=True):
        scored = sorted(
            (
                (c_idx, cosine_similarity(q_vec, c_vec))
                for c_idx, c_vec in enumerate(corpus_vectors)
            ),
            key=lambda pair: pair[1],
            reverse=True,
        )
        rank = [c_idx for c_idx, _sim in scored].index(target_idx) + 1
        reciprocal_ranks.append(1.0 / rank)
        ndcg_scores.append(1.0 / math.log2(rank + 1) if rank <= k else 0.0)
        top1_hits += int(rank == 1)
        top3_hits += int(rank <= 3)
        top5_hits += int(rank <= k)
    total = len(query_vectors)
    return (
        top1_hits / total * 100.0,
        top3_hits / total * 100.0,
        top5_hits / total * 100.0,
        sum(reciprocal_ranks) / len(reciprocal_ranks),
        sum(ndcg_scores) / len(ndcg_scores),
    )


def test_similarity_matrix_matches_pairwise_cosine(monkeypatch: MonkeyPatch) -> None:
    """The ranking scores with one numpy product, and each score is the pairwise cosine."""
    from devops_cli.ai.benchmark.retrieval_metrics import similarity_matrix

    matmul_calls: list[tuple[object, ...]] = []
    real_matmul = numpy.matmul

    def spy_matmul(*args: object, **kwargs: object) -> object:
        matmul_calls.append(args)
        return real_matmul(*args, **kwargs)

    def refuse_pairwise(*_args: object, **_kwargs: object) -> float:
        raise AssertionError("the ranking called cosine_similarity for one pair")

    monkeypatch.setattr(numpy, "matmul", spy_matmul)
    monkeypatch.setattr("devops_cli.ai.vector_similarity.cosine_similarity", refuse_pairwise)

    scores = similarity_matrix(_QUERY_VECTORS, _CORPUS_VECTORS)

    assert len(matmul_calls) == 1
    assert scores.shape == (len(_QUERY_VECTORS), len(_CORPUS_VECTORS))
    for q_index, q_vec in enumerate(_QUERY_VECTORS):
        for c_index, c_vec in enumerate(_CORPUS_VECTORS):
            expected = cosine_similarity(q_vec, c_vec)
            assert scores[q_index][c_index] == pytest.approx(expected, abs=1e-9, rel=0.0)


def test_similarity_matrix_of_zero_length_vectors_is_zero() -> None:
    """A vector of no dimension scores zero against each document, as the pairwise helper did."""
    from devops_cli.ai.benchmark.retrieval_metrics import similarity_matrix

    scores = similarity_matrix([[], []], [[], [], []])

    assert scores.shape == (2, 3)
    assert not scores.any()


def test_metrics_match_the_pure_python_reference() -> None:
    """The pytrec_eval metrics equal the pairwise loop's for targets ranked 1, 3 and 6."""
    from devops_cli.ai.benchmark.retrieval_metrics import rank_and_score

    result = rank_and_score(
        _ORDERED_QUERY_VECTORS, _ORDERED_CORPUS_VECTORS, _ORDERED_TARGET_INDICES
    )

    assert result.ranks == [1, 3, 6]
    expected = _reference_metrics(
        _ORDERED_QUERY_VECTORS, _ORDERED_CORPUS_VECTORS, _ORDERED_TARGET_INDICES
    )
    assert (
        result.recall_at_1,
        result.recall_at_3,
        result.recall_at_5,
        result.mrr,
        result.ndcg_at_5,
    ) == pytest.approx(expected)
