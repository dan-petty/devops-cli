"""Retrieval scores of an embedding benchmark: numpy ranks the passages, pytrec_eval scores them."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pytrec_eval
from numpy.typing import NDArray


@dataclass(frozen=True)
class RetrievalScores:
    """What a model's embeddings score on a list of retrieval tasks."""

    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    ndcg_at_5: float
    mean_margin: float
    separation: float
    category_accuracies: dict[str, float]

    @property
    def recall_1(self) -> float:
        return self.recall_at_1

    @property
    def recall_3(self) -> float:
        return self.recall_at_3

    @property
    def recall_5(self) -> float:
        return self.recall_at_5

    @property
    def ndcg_5(self) -> float:
        return self.ndcg_at_5


def rank_corpus(
    query_vectors: Sequence[Sequence[float]] | NDArray[np.float64],
    corpus_vectors: Sequence[Sequence[float]] | NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.int_]]:
    """Rank the corpus against the queries with one matrix product over row-normalized vectors."""
    q_mat = np.asarray(query_vectors, dtype=np.float64)
    c_mat = np.asarray(corpus_vectors, dtype=np.float64)

    if q_mat.size == 0 or c_mat.size == 0:
        scores = np.zeros((len(q_mat), len(c_mat)), dtype=np.float64)
        ranked = np.zeros((len(q_mat), len(c_mat)), dtype=int)
        return scores, ranked

    q_norms = np.linalg.norm(q_mat, axis=1, keepdims=True)
    c_norms = np.linalg.norm(c_mat, axis=1, keepdims=True)

    q_normed = np.divide(q_mat, q_norms, out=np.zeros_like(q_mat), where=q_norms > 0)
    c_normed = np.divide(c_mat, c_norms, out=np.zeros_like(c_mat), where=c_norms > 0)

    scores = np.matmul(q_normed, c_normed.T)
    ranked_indices = np.argsort(-scores, axis=1, kind="stable")
    return scores, ranked_indices


def score_retrieval(
    score_matrix: NDArray[np.float64],
    ranked_indices: NDArray[np.int_] | Sequence[Sequence[int]],
    targets: Sequence[int],
    categories: Sequence[str],
) -> RetrievalScores:
    """Score the ranking each query makes over the corpus, by cosine, against its target."""
    num_queries = len(targets)
    if num_queries == 0 or score_matrix.size == 0:
        return RetrievalScores(
            recall_at_1=0.0,
            recall_at_3=0.0,
            recall_at_5=0.0,
            mrr=0.0,
            ndcg_at_5=0.0,
            mean_margin=0.0,
            separation=0.0,
            category_accuracies={},
        )

    qrels: dict[str, dict[str, int]] = {}
    run: dict[str, dict[str, float]] = {}

    for q_idx in range(num_queries):
        qid = str(q_idx)
        target_idx = targets[q_idx]
        qrels[qid] = {str(target_idx): 1}

        q_ranked = ranked_indices[q_idx]
        num_docs = len(q_ranked)
        run[qid] = {str(doc_idx): float(num_docs - rank) for rank, doc_idx in enumerate(q_ranked)}

    evaluator = pytrec_eval.RelevanceEvaluator(
        qrels, {"recall_1", "recall_3", "recall_5", "recip_rank", "ndcg_cut_5"}
    )
    eval_results = evaluator.evaluate(run)

    recalls_1 = [eval_results[str(q)]["recall_1"] for q in range(num_queries)]
    recalls_3 = [eval_results[str(q)]["recall_3"] for q in range(num_queries)]
    recalls_5 = [eval_results[str(q)]["recall_5"] for q in range(num_queries)]
    mrrs = [eval_results[str(q)]["recip_rank"] for q in range(num_queries)]
    ndcgs = [eval_results[str(q)]["ndcg_cut_5"] for q in range(num_queries)]

    recall_at_1 = float(np.mean(recalls_1) * 100.0)
    recall_at_3 = float(np.mean(recalls_3) * 100.0)
    recall_at_5 = float(np.mean(recalls_5) * 100.0)
    mrr = float(np.mean(mrrs))
    ndcg_at_5 = float(np.mean(ndcgs))

    margins: list[float] = []
    target_sims: list[float] = []
    distractor_sims: list[float] = []

    for q_idx in range(num_queries):
        target_idx = targets[q_idx]
        num_chunks = score_matrix.shape[1]
        t_sim = float(score_matrix[q_idx, target_idx]) if 0 <= target_idx < num_chunks else 0.0
        target_sims.append(t_sim)

        other_sims = [
            float(score_matrix[q_idx, c_i]) for c_i in range(num_chunks) if c_i != target_idx
        ]
        best_other_sim = max(other_sims) if other_sims else 0.0
        margins.append(t_sim - best_other_sim)
        distractor_sims.extend(other_sims)

    mean_margin = float(np.mean(margins)) if margins else 0.0
    mean_t_sim = float(np.mean(target_sims)) if target_sims else 0.0
    mean_d_sim = float(np.mean(distractor_sims)) if distractor_sims else 0.0
    separation = mean_t_sim - mean_d_sim

    category_hits: dict[str, list[int]] = {}
    for q_idx in range(num_queries):
        cat = categories[q_idx]
        is_hit = 1 if recalls_1[q_idx] == 1.0 else 0
        category_hits.setdefault(cat, []).append(is_hit)

    category_accuracies = {
        cat: float(np.mean(hits) * 100.0) if hits else 0.0 for cat, hits in category_hits.items()
    }

    return RetrievalScores(
        recall_at_1=recall_at_1,
        recall_at_3=recall_at_3,
        recall_at_5=recall_at_5,
        mrr=mrr,
        ndcg_at_5=ndcg_at_5,
        mean_margin=mean_margin,
        separation=separation,
        category_accuracies=category_accuracies,
    )
