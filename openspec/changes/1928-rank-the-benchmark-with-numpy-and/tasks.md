# Tasks

## 1. Declare numpy and pytrec-eval-terrier, add the pytrec_eval stub and its invariant test

Kind: other. Reads: `pyproject.toml`, `typings/jq.pyi`, `tests/invariants/test_architectural_invariants.py`. Changes: `pyproject.toml`, `uv.lock`, `typings/pytrec_eval.pyi` (new), `tests/invariants/test_declared_dependencies.py` (new).

- [ ] 1.1 Write `tests/invariants/test_declared_dependencies.py` first: it reads `pyproject.toml` with tomllib and asserts that numpy and pytrec-eval-terrier are in the dependency list; it reads `uv.lock` and asserts, for the package entry of each of the two, a resolved version and a wheel of the entry whose file name ends in `.whl` and holds `linux` and `x86_64`; it reads `typings/pytrec_eval.pyi` and asserts the names RelevanceEvaluator and evaluate; and it asserts that the project configuration holds one `[[tool.mypy.overrides]]` entry, with no pytrec_eval module. Then add numpy and pytrec-eval-terrier to the dependency list of `pyproject.toml` at the versions that the lock resolves, in the exact-pin style of the file, add a `[tool.deptry]` table above `[tool.deptry.per_rule_ignores]` with `package_module_name_map = { "pytrec-eval-terrier" = "pytrec_eval" }`, add `typings/pytrec_eval.pyi` with the RelevanceEvaluator class, its constructor and its evaluate method in the shape of `typings/jq.pyi`, run `uv lock` so `uv.lock` resolves both libraries and their linux x86_64 wheels, and add no `[[tool.mypy.overrides]]` entry. Stop and report the fault if a lock entry of either library holds no linux x86_64 wheel, because the issue's criterion then does not hold
  - Verification: `$ uv run devops ci test tests/invariants/test_declared_dependencies.py` passes

## 2. Add the numpy ranking and the pytrec_eval metrics module

Kind: behavior. Reads: `src/devops_cli/ai/vector_similarity.py`, `src/devops_cli/ai/benchmark/embedding_runner.py`, `typings/pytrec_eval.pyi`. Changes: `src/devops_cli/ai/benchmark/retrieval_metrics.py` (new), `tests/ai/benchmark/test_retrieval_metrics.py` (new).

- [ ] 2.1 `tests/ai/benchmark/test_retrieval_metrics.py::test_ranking_matches_cosine_similarity_in_one_matmul` fails first, then `tests/ai/benchmark/test_retrieval_metrics.py::test_metrics_match_fixed_expected_values`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_retrieval_metrics.py` fails on the base
- [ ] 2.2 Add `src/devops_cli/ai/benchmark/retrieval_metrics.py` with rank_corpus, which turns the query and corpus vectors into two float64 arrays, divides each row by its Euclidean norm, leaves a zero-norm row at zero, and takes one numpy.matmul; it returns the score matrix, one row for each query and one column for each chunk, and the ranked chunk indices of each query, best first, from a stable sort, so that equal scores keep the corpus order. Add score_retrieval, which takes the score matrix, the ranked indices, and the target index and the category of each query. It builds the qrels from the targets and one run from the ranked indices, with a run score that falls as the rank goes up, so that pytrec_eval keeps the order of rank_corpus for equal scores. It asks pytrec_eval.RelevanceEvaluator for recall.1, recall.3, recall.5, recip_rank and ndcg_cut.5. It reads the target score and the best distractor score of each query from the score matrix for the margins and the separation, and it takes the per-category accuracies from the rank-1 hits. It returns the three recalls as percentages with mrr, ndcg_at_5, the mean margin, the separation and the per-category accuracies. Write the cases of `tests/ai/benchmark/test_retrieval_metrics.py` first, and import the new module inside each test function, so that each case fails on the base and does not stop the collection: one on a 2-query by 4-chunk fixture of non-unit vectors that compares each score of the matrix with cosine_similarity within 1e-9 and counts one matrix product call, one on a qrels whose targets rank 1, 3 and 6 that asserts 100/3 and 200/3 percent for the recalls, one on a zero-norm row, and one on a fixed score matrix that asserts the margins and the separation
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_retrieval_metrics.py` passes

## 3. Rank the benchmark through the new module and delete the inline helper

Kind: behavior. Reads: `src/devops_cli/ai/benchmark/embedding_runner.py`, `src/devops_cli/ai/benchmark/retrieval_metrics.py`, `src/devops_cli/ai/vector_similarity.py`, `tests/ai/benchmark/test_ai_benchmark.py`, `tests/ai/benchmark/test_embedding_benchmark.py`, `tests/ai/client/test_ai_client_providers_and_embeddings.py`. Changes: `src/devops_cli/ai/benchmark/embedding_runner.py`, `tests/ai/benchmark/test_ai_benchmark.py`, `tests/ai/benchmark/test_embedding_benchmark.py`, `tests/ai/client/test_ai_client_providers_and_embeddings.py`.

- [ ] 3.1 `tests/ai/benchmark/test_embedding_benchmark.py::test_runner_scores_a_target_absent_from_the_corpus_as_zero` fails first, then `tests/ai/benchmark/test_ai_benchmark.py::test_embedding_benchmark_runner_and_metrics` passes with no import of the removed helper. No test names the removed helper: the negative search of task 3.2 proves the removal, as the issue asks
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_ai_benchmark.py tests/ai/benchmark/test_embedding_benchmark.py tests/ai/client/test_ai_client_providers_and_embeddings.py` fails on the base
- [ ] 3.2 Replace the scoring block of `src/devops_cli/ai/benchmark/embedding_runner.py` with one call to rank_corpus and one to score_retrieval, delete compute_ndcg_at_k, and drop the cosine_similarity import; the math import stays, because the vector health check still takes math.sqrt. In `tests/ai/benchmark/test_ai_benchmark.py`, `tests/ai/benchmark/test_embedding_benchmark.py` and `tests/ai/client/test_ai_client_providers_and_embeddings.py`, import cosine_similarity from `src/devops_cli/ai/vector_similarity.py`, and remove each line that names compute_ndcg_at_k: the imports, the assertions, the comments and the docstring of `tests/ai/benchmark/test_embedding_benchmark.py::test_compute_ndcg_and_report_rendering`, whose report part stays as `test_report_rendering`. In `tests/ai/benchmark/test_embedding_benchmark.py`, add the absent-target case
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_ai_benchmark.py tests/ai/benchmark/test_embedding_benchmark.py tests/ai/client/test_ai_client_providers_and_embeddings.py` passes
  - Verification: `$ ! git grep -n compute_ndcg_at_k -- src tests`

## 4. Remove the C901 marker from the benchmark evaluation

Kind: other. Reads: `src/devops_cli/ai/benchmark/embedding_runner.py`. Changes: `src/devops_cli/ai/benchmark/embedding_runner.py`.

- [ ] 4.1 Remove the C901 suppression marker from the benchmark evaluation function in `src/devops_cli/ai/benchmark/embedding_runner.py`, now that every metric computation sits in the new module, and leave the function under the cap of 10. The lint row runs Ruff with C901 and RUF100, so it reports a function over the cap and a marker that is no longer needed
  - Verification: `$ uv run devops ci --check --only lint` passes

## 5. Import both libraries in the Service Image smoke probes of both workflows

Kind: other. Reads: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `tests/commands/test_ci.py`. Changes: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `tests/commands/test_ci.py`.

- [ ] 5.1 Add numpy and pytrec_eval to the python probe of the Run Service Image Smoke Test step in both `.github/workflows/ci.yml` and `.github/workflows/release.yml`, and keep the two run blocks byte-identical, because the parity test in `tests/commands/test_ci.py` compares them. Add a test to `tests/commands/test_ci.py`, next to the parity test, that reads both smoke steps and asserts that each run block names numpy and pytrec_eval
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
