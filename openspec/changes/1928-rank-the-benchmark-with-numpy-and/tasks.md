# Tasks

## 1. Add the numpy ranking and pytrec_eval metrics module

Reads: `src/devops_cli/ai/benchmark/embedding_runner.py`, `src/devops_cli/ai/vector_similarity.py`, `tests/ai/benchmark/test_embedding_benchmark.py`, `pyproject.toml`. Changes: `src/devops_cli/ai/benchmark/retrieval_metrics.py` (new), `tests/ai/benchmark/test_retrieval_metrics.py` (new), `pyproject.toml`, `uv.lock`.

- [x] 1.1 Write `test_similarity_matrix_matches_pairwise_cosine` and `test_metrics_match_the_pure_python_reference` in `tests/ai/benchmark/test_retrieval_metrics.py`; the first spies on `numpy.matmul` and patches `cosine_similarity`, and both fail before `retrieval_metrics` exists
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_retrieval_metrics.py` fails on the base
- [x] 1.2 Add `numpy==2.5.4` and `pytrec-eval-terrier` at the version that `uv lock` resolves, pinned with `==` like every other runtime dependency, to `[project].dependencies` in `pyproject.toml`, and add a `[[tool.mypy.overrides]]` entry for `pytrec_eval.*` with `ignore_missing_imports = true`. Run `uv lock`. Create `src/devops_cli/ai/benchmark/retrieval_metrics.py` with `similarity_matrix(query_vectors, corpus_vectors)`, which row-normalizes both matrices, keeps a zero row at zero, and returns one `numpy.matmul` product, and `rank_and_score(query_vectors, corpus_vectors, target_indices, k=5)`, which takes the top k indices per query, builds the qrels and the run of the top k plus the target document, and returns a `RetrievalResult` with the ranks, recall at 1, 3 and 5 in percent, MRR and nDCG at 5 from `pytrec_eval`, the target similarities, the margins and the mean distractor similarity
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_retrieval_metrics.py` passes

## 2. Rank the benchmark through the retrieval metrics module

Reads: `src/devops_cli/ai/benchmark/retrieval_metrics.py`, `src/devops_cli/ai/benchmark/embedding_runner.py`, `tests/ai/benchmark/test_embedding_benchmark.py`. Changes: `src/devops_cli/ai/benchmark/embedding_runner.py`, `tests/ai/benchmark/test_embedding_benchmark.py`, `tests/ai/benchmark/test_ai_benchmark.py`, `tests/ai/client/test_ai_client_providers_and_embeddings.py`.

- [ ] 2.1 Write `test_the_benchmark_ranks_each_query_with_the_retrieval_metrics_module` in `tests/ai/benchmark/test_embedding_benchmark.py`, which patches `embedding_runner.rank_and_score` with a spy and fails before the runner calls it; delete the `compute_ndcg_at_k` cases from `tests/ai/benchmark/test_embedding_benchmark.py`, `tests/ai/benchmark/test_ai_benchmark.py` and `tests/ai/client/test_ai_client_providers_and_embeddings.py`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_embedding_benchmark.py` fails on the base
- [ ] 2.2 In `evaluate_model_on_server`, replace the per-pair loop, the accumulators and `compute_ndcg_at_k` with one call to `rank_and_score` over the query and corpus vectors, and fill recall at 1, 3 and 5, MRR, nDCG at 5, the mean margin, the separation score and the category hits from its result. Delete the `compute_ndcg_at_k` function, the `cosine_similarity` import and the `# noqa: C901` marker from the method. Remove the `compute_ndcg_at_k` imports and assertions from the three test modules, and point every `cosine_similarity` import that names `devops_cli.ai.benchmark.embedding_runner` at `devops_cli.ai.vector_similarity`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_embedding_benchmark.py` passes

## 3. Import the new libraries in the Service Image smoke test

Reads: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `tests/commands/test_ci.py`. Changes: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `tests/commands/test_ci.py`.

- [ ] 3.1 Add `import numpy, pytrec_eval` to the `python -c` probe of the `Run Service Image Smoke Test` step in `.github/workflows/ci.yml` and `.github/workflows/release.yml`, so the two `run` blocks stay identical. Extend `test_service_image_smoke_test_parity` in `tests/commands/test_ci.py` to assert that the shared block imports both modules
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
