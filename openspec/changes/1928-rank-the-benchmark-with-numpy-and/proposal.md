# Proposal

## Why

The embedding benchmark ranks every query against every chunk in pure Python and holds its own recall, MRR and nDCG code, which takes 57 seconds on the #481 fixture where a numpy matrix product and pytrec_eval give the same scores in 0.7 seconds. #1928 replaces that path and removes its C901 suppression.

## What Changes

- Add `src/devops_cli/ai/benchmark/retrieval_metrics.py` with one row-normalized numpy matrix product and `pytrec_eval` recall, MRR and nDCG.
- Rank each query once in `evaluate_model_on_server` and remove `compute_ndcg_at_k`, the inline loop and the `# noqa: C901` marker.
- Declare `numpy` and `pytrec-eval-terrier` in `pyproject.toml`, lock both in `uv.lock`, and add the `pytrec_eval.*` mypy override.
- Add `tests/ai/benchmark/test_retrieval_metrics.py` and update the three test modules that import `compute_ndcg_at_k` or the runner's `cosine_similarity`.
- Import `numpy` and `pytrec_eval` in the Service Image smoke test of `.github/workflows/ci.yml` and `.github/workflows/release.yml`, and extend its parity test.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `embedding-benchmark-ranking`: The benchmark ranks with one matrix product, The retrieval metrics come from pytrec_eval, The runner holds no private nDCG helper, The runner passes the complexity cap without a suppression, The Service image imports the new libraries

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/benchmark/retrieval_metrics.py`, `pyproject.toml`, `uv.lock`, `src/devops_cli/ai/benchmark/embedding_runner.py`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`
- Tests: `tests/ai/benchmark/test_retrieval_metrics.py`, `tests/ai/benchmark/test_embedding_benchmark.py`, `tests/ai/benchmark/test_ai_benchmark.py`, `tests/ai/client/test_ai_client_providers_and_embeddings.py`, `tests/commands/test_ci.py`

## Feasibility

- The code premise is confirmed: `src/devops_cli/ai/benchmark/embedding_runner.py` is a file of the staging commit, and its ranking loop calls the pairwise helper at `src/devops_cli/ai/benchmark/embedding_runner.py:449:sim = cosine_similarity(q_vec, c_vec)`.
- The timing figures of the issue (57 seconds and 0.7 seconds) are not checked, because this run has no network and runs no benchmark.
- The library facts (maintained, MIT licensed, no advisory, Python 3.14 wheels) are not checked, because this run has no network and no package index.
- The loop that the issue replaces starts at `src/devops_cli/ai/benchmark/embedding_runner.py:443:for idx, (eval_item, q_vec) in enumerate(zip(pairs, query_vectors, strict=False)):`, and the method carries the suppression at `src/devops_cli/ai/benchmark/embedding_runner.py:350:def evaluate_model_on_server( # noqa: C901`.
- `search_code` with `compute_ndcg_at_k` shows the definition at `src/devops_cli/ai/benchmark/embedding_runner.py:69:def compute_ndcg_at_k(ranked_indices: list[int], target_idx: int, k: int = 5) -> float:` and the only call at `src/devops_cli/ai/benchmark/embedding_runner.py:466:ndcg = compute_ndcg_at_k(ranked_indices, target_idx, k=5)`.
- `references` for `compute_ndcg_at_k` lists 4 files and 14 lines: the runner and `tests/ai/benchmark/test_ai_benchmark.py`, `tests/ai/benchmark/test_embedding_benchmark.py` and `tests/ai/client/test_ai_client_providers_and_embeddings.py`; the plan changes all four.
- The probe line "The path `retrieval_metrics.py` is no file of the staging commit. No commit in the history deleted or renamed it." confirms that the module is new, so the plan creates it.
- The probe line "The path `.data/agent/scratch/481a-numpy-ranking.patch` is no file of the staging commit. No commit in the history deleted or renamed it." shows that the patch and its test count cannot be read here, so the plan writes the change from the tests.
- `AGENTS.md:20:Keep your own files out of git.` keeps `.data/agent/` out of the repository, so the patch is no input of this plan.
- The pairwise helper divides by both norms at `src/devops_cli/ai/vector_similarity.py:20:return float(dot / (norm_a * norm_b))`, so the plan normalizes both matrices before the product.
- `numpy` is in the lock through `formulaic` at `uv.lock:1283:{ name = "numpy" }`, and its entry at `uv.lock:2549:name = "numpy"` holds a cp314 manylinux x86_64 wheel; the plan declares it directly and adds `pytrec-eval-terrier`.
- The pull request Service Image job rebuilds on a dependency change because `.github/workflows/ci.yml:429:pyproject.toml` and `.github/workflows/ci.yml:430:uv.lock` are in `IMAGE_CONTENT_PATHS`, and its smoke test runs the probe at `.github/workflows/ci.yml:485:--entrypoint python "$IMAGE" -c "import getpass, pathlib, subprocess`.
- The two smoke-test blocks must stay identical, as `tests/commands/test_ci.py:1496:def test_service_image_smoke_test_parity() -> None:` asserts, so both workflow files change.
- The release service image build sets `.github/workflows/release.yml:411:platforms: linux/amd64`, and the pull request Service Image job runs on `ubuntu-26.04` with no platform override; an aarch64 wheel is not checked here.
- First checks against the real system: `uv lock` needs the network and the checkout of the repository, then `uv run devops ci lockfile` and `uv run devops ci deps` need the checkout, and `uv run devops ci test tests/ai/benchmark/test_retrieval_metrics.py` needs the checkout.
- `uv run devops ci test tests/ai/benchmark/test_embedding_benchmark.py` and `uv run devops ci test tests/commands/test_ci.py` each need the checkout of the repository.
- The plan introduces no new program: `uv`, `pytest`, `ruff` and `mypy` are runner tools of the image, the failure classes are `test`, `lint` and `types`, and the pod runs non-root with a read-only root filesystem, every capability dropped and the `RuntimeDefault` seccomp profile.
- If `uv lock` finds no `linux/amd64` wheel for `pytrec-eval-terrier`, the issue cannot be built as written, the failure class is `premise_false`, and the plan adds no fallback code.

## Existing Tool Considered

numpy 2.5.4 for the matrix product and pytrec-eval-terrier (imported as pytrec_eval) for recall, MRR and nDCG; no project code replaces either.

## Dependencies

None.
