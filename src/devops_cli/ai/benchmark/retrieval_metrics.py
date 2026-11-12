"""Rank a model's queries with one numpy product, and score the ranking with pytrec_eval.

The embedding benchmark compares the query vectors of one run with the vectors of the whole
corpus. One row-normalized matrix product scores every pair, and pytrec_eval computes recall,
MRR and nDCG over the ranking of each query (#1928).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy
import pytrec_eval
from numpy.typing import NDArray

_NDCG_CUTOFF = 5
"""The rank at which the benchmark reports nDCG and recall."""

# Each metric that pytrec_eval computes for the benchmark, and the measure that gives it.
# pytrec_eval names the per-query key of a measure with its dot replaced by an underscore.
_MEASURES: dict[str, str] = {
    "recall_at_1": "recall.1",
    "recall_at_3": "recall.3",
    "recall_at_5": "recall.5",
    "mrr": "recip_rank",
    "ndcg_at_5": "ndcg_cut.5",
}


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """How one run ranked its queries, and what that ranking scores.

    `ranks` holds the 1-based rank of each query's target document. The metrics are the means
    over the queries, with each recall in percent. `target_similarities` and `margins` hold one
    value per query, and `mean_distractor_similarity` is the mean over every pair whose document
    is not the query's target, so `separation_score` is the mean target similarity minus it.
    """

    ranks: list[int]
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    ndcg_at_5: float
    target_similarities: list[float]
    margins: list[float]
    mean_margin: float
    mean_distractor_similarity: float
    separation_score: float


def _row_normalized(matrix: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
    """Each row scaled to unit length, with a zero row left at zero."""
    norms = numpy.linalg.norm(matrix, axis=1, keepdims=True)
    scaled: NDArray[numpy.float64] = numpy.divide(
        matrix, norms, out=numpy.zeros_like(matrix), where=norms > 0.0
    )
    return scaled


def similarity_matrix(
    query_vectors: Sequence[Sequence[float]],
    corpus_vectors: Sequence[Sequence[float]],
) -> NDArray[numpy.float64]:
    """The cosine similarity of each query to each corpus vector, as one matrix product."""
    queries = numpy.asarray(query_vectors, dtype=numpy.float64)
    corpus = numpy.asarray(corpus_vectors, dtype=numpy.float64)
    if queries.size == 0 or corpus.size == 0:
        return numpy.zeros((len(query_vectors), len(corpus_vectors)))
    product: NDArray[numpy.float64] = numpy.matmul(
        _row_normalized(queries), _row_normalized(corpus).T
    )
    return product


def _target_ranks(order: NDArray[numpy.intp], targets: NDArray[numpy.intp]) -> list[int]:
    """The 1-based position of each query's target document in its ranking."""
    positions = (order == targets[:, None]).argmax(axis=1) + 1
    return [int(position) for position in positions]


def _qrels_and_run(
    scores: NDArray[numpy.float64],
    order: NDArray[numpy.intp],
    targets: NDArray[numpy.intp],
    ranks: list[int],
    k: int,
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, float]]]:
    """The relevant document of each query, and the run that pytrec_eval scores.

    The run holds the top k documents of each query and the target document, so a target that
    ranks lower keeps its true rank and MRR counts 1/rank rather than 0.
    """
    qrels: dict[str, dict[str, int]] = {}
    run: dict[str, dict[str, float]] = {}
    for row, rank in enumerate(ranks):
        query = str(row)
        qrels[query] = {str(int(targets[row])): 1}
        depth = max(k, rank)
        run[query] = {
            str(int(document)): float(scores[row, document]) for document in order[row, :depth]
        }
    return qrels, run


def _mean_measure(evaluated: dict[str, dict[str, float]], measure: str) -> float:
    """The mean of one pytrec_eval measure over the queries of the run."""
    values = [per_query[measure.replace(".", "_")] for per_query in evaluated.values()]
    return sum(values) / len(values) if values else 0.0


def _margins(
    scores: NDArray[numpy.float64],
    targets: NDArray[numpy.intp],
    target_similarities: list[float],
) -> list[float]:
    """Each target's similarity minus the best similarity of another document of its query."""
    masked = numpy.where(
        numpy.arange(scores.shape[1])[None, :] == targets[:, None], -numpy.inf, scores
    )
    best = masked.max(axis=1)
    best_other = numpy.where(numpy.isfinite(best), best, 0.0)
    return [
        target - float(other) for target, other in zip(target_similarities, best_other, strict=True)
    ]


def _mean_distractor_similarity(
    scores: NDArray[numpy.float64], target_similarities: list[float]
) -> float:
    """The mean similarity of every pair whose document is not the query's target."""
    distractor_count = scores.size - len(target_similarities)
    if distractor_count <= 0:
        return 0.0
    return float((scores.sum() - sum(target_similarities)) / distractor_count)


def rank_and_score(
    query_vectors: Sequence[Sequence[float]],
    corpus_vectors: Sequence[Sequence[float]],
    target_indices: Sequence[int],
    k: int = _NDCG_CUTOFF,
) -> RetrievalResult:
    """Rank each query against the corpus, and score its target document with pytrec_eval."""
    scores = similarity_matrix(query_vectors, corpus_vectors)
    targets = numpy.asarray(target_indices, dtype=numpy.intp)
    order = numpy.argsort(-scores, axis=1, kind="stable")
    ranks = _target_ranks(order, targets)
    qrels, run = _qrels_and_run(scores, order, targets, ranks, k)
    evaluated = pytrec_eval.RelevanceEvaluator(qrels, set(_MEASURES.values())).evaluate(run)
    metrics = {name: _mean_measure(evaluated, measure) for name, measure in _MEASURES.items()}
    target_similarities = [float(scores[row, target]) for row, target in enumerate(targets)]
    margins = _margins(scores, targets, target_similarities)
    mean_distractor = _mean_distractor_similarity(scores, target_similarities)
    mean_target = (
        sum(target_similarities) / len(target_similarities) if target_similarities else 0.0
    )
    return RetrievalResult(
        ranks=ranks,
        recall_at_1=metrics["recall_at_1"] * 100.0,
        recall_at_3=metrics["recall_at_3"] * 100.0,
        recall_at_5=metrics["recall_at_5"] * 100.0,
        mrr=metrics["mrr"],
        ndcg_at_5=metrics["ndcg_at_5"],
        target_similarities=target_similarities,
        margins=margins,
        mean_margin=sum(margins) / len(margins) if margins else 0.0,
        mean_distractor_similarity=mean_distractor,
        separation_score=mean_target - mean_distractor,
    )
