"""Tests for retrieval metrics computed with numpy ranking and pytrec_eval."""

from unittest.mock import patch

import numpy as np

from devops_cli.ai.vector_similarity import cosine_similarity


def test_ranking_matches_cosine_similarity_in_one_matmul() -> None:
    from devops_cli.ai.benchmark.retrieval_metrics import rank_corpus

    # 2 queries, 4 chunks, non-unit vectors
    queries = [
        [1.0, 2.0, 3.0],
        [4.0, 0.5, -1.0],
    ]
    corpus = [
        [2.0, 1.0, 0.0],
        [-1.0, 2.0, 2.0],
        [0.5, -0.5, 1.0],
        [3.0, 3.0, 3.0],
    ]

    with patch("numpy.matmul", wraps=np.matmul) as mock_matmul:
        scores, ranked_indices = rank_corpus(queries, corpus)

    # Asserts one matrix product call
    assert mock_matmul.call_count == 1

    # Verify score matrix shape: (2, 4)
    assert scores.shape == (2, 4)

    # Compare each score with cosine_similarity within 1e-9
    for q_idx, q_vec in enumerate(queries):
        for c_idx, c_vec in enumerate(corpus):
            expected = cosine_similarity(q_vec, c_vec)
            assert abs(scores[q_idx, c_idx] - expected) < 1e-9

    # Verify ranked_indices order
    for q_idx in range(len(queries)):
        q_scores = scores[q_idx]
        sorted_indices = list(ranked_indices[q_idx])
        for i in range(len(sorted_indices) - 1):
            assert q_scores[sorted_indices[i]] >= q_scores[sorted_indices[i + 1]]


def test_metrics_match_fixed_expected_values() -> None:
    from devops_cli.ai.benchmark.retrieval_metrics import score_retrieval

    # Query 0: target 0 ranks 1
    # Query 1: target 2 ranks 3
    # Query 2: target 5 ranks 6
    scores = np.array(
        [
            [10.0, 9.0, 8.0, 7.0, 6.0, 5.0],
            [10.0, 9.0, 8.0, 7.0, 6.0, 5.0],
            [10.0, 9.0, 8.0, 7.0, 6.0, 5.0],
        ],
        dtype=np.float64,
    )
    ranked_indices = np.array(
        [
            [0, 1, 2, 3, 4, 5],
            [0, 1, 2, 3, 4, 5],
            [0, 1, 2, 3, 4, 5],
        ],
        dtype=int,
    )
    targets = [0, 2, 5]
    categories = ["catA", "catA", "catB"]

    result = score_retrieval(scores, ranked_indices, targets, categories)

    # Recall at 1 is 100/3 percent, recall at 3 and 5 are 200/3 percent
    assert abs(result.recall_at_1 - (100.0 / 3.0)) < 1e-9
    assert abs(result.recall_at_3 - (200.0 / 3.0)) < 1e-9
    assert abs(result.recall_at_5 - (200.0 / 3.0)) < 1e-9
    assert abs(result.mrr - 0.5) < 1e-9
    assert abs(result.ndcg_at_5 - 0.5) < 1e-9

    # Per-category accuracies: catA has 1 hit out of 2 (50%), catB has 0 hits out of 1 (0%)
    assert abs(result.category_accuracies["catA"] - 50.0) < 1e-9
    assert abs(result.category_accuracies["catB"] - 0.0) < 1e-9


def test_zero_norm_row_keeps_zero_score() -> None:
    from devops_cli.ai.benchmark.retrieval_metrics import rank_corpus

    queries = [
        [0.0, 0.0, 0.0],
        [1.0, 2.0, 3.0],
    ]
    corpus = [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
    ]

    scores, _ranked_indices = rank_corpus(queries, corpus)
    assert np.all(scores[0] == 0.0)
    assert scores[1, 1] == 0.0


def test_margins_and_separation_on_fixed_score_matrix() -> None:
    from devops_cli.ai.benchmark.retrieval_metrics import score_retrieval

    # 2 queries, 3 chunks
    # Query 0: target 0, score 0.8. Distractors: 0.6, 0.2.
    #   best distractor = 0.6. margin = 0.8 - 0.6 = 0.2
    #   distractors = [0.6, 0.2]
    # Query 1: target 1, score 0.9. Distractors: 0.5, 0.1.
    #   best distractor = 0.5. margin = 0.9 - 0.5 = 0.4
    #   distractors = [0.5, 0.1]
    # Mean margin = (0.2 + 0.4) / 2 = 0.3
    # Mean target sim = (0.8 + 0.9) / 2 = 0.85
    # Mean distractor sim = (0.6 + 0.2 + 0.5 + 0.1) / 4 = 1.4 / 4 = 0.35
    # Separation = 0.85 - 0.35 = 0.5
    scores = np.array(
        [
            [0.8, 0.6, 0.2],
            [0.5, 0.9, 0.1],
        ],
        dtype=np.float64,
    )
    ranked_indices = np.array(
        [
            [0, 1, 2],
            [1, 0, 2],
        ],
        dtype=int,
    )
    targets = [0, 1]
    categories = ["cat1", "cat2"]

    result = score_retrieval(scores, ranked_indices, targets, categories)
    assert abs(result.mean_margin - 0.3) < 1e-9
    assert abs(result.separation - 0.5) < 1e-9
