# Design

## Decisions

- **Put the matrix product and the metrics in `src/devops_cli/ai/benchmark/retrieval_metrics.py`.**: The inline loop and the five accumulators are what makes `evaluate_model_on_server` long and complex, and a separate module makes the ranking testable on a fixed fixture.
- **Row-normalize both matrices before the product, and keep a zero row at zero.**: `src/devops_cli/ai/vector_similarity.py:20:return float(dot / (norm_a * norm_b))` divides by both norms, so a raw product changes every score.
- **Give `pytrec_eval` a run of the top k documents plus the target document for each query.**: The current MRR divides 1 by the target's rank even beyond k, and a run of the top k alone would report 0 for a target at rank 6.
- **Add a `[[tool.mypy.overrides]]` entry for `pytrec_eval.*` with `ignore_missing_imports = true`.**: pytrec-eval-terrier ships no type information, and mypy strict refuses an import of an untyped package; the override keeps the untyped call in one module.
- **Keep `cosine_similarity` in `src/devops_cli/ai/vector_similarity.py` and point the test imports that read it from the runner at that module.**: `src/devops_cli/roadmap/nearest.py` still ranks its candidates with the helper, so the helper stays and only the benchmark stops calling it per pair.
- **Build the `linux/amd64` Service image in the pull request check and import both libraries in its smoke test.**: The job rebuilds on a change of `pyproject.toml`, `uv.lock` or `src`, so the check proves that the new wheel installs in the image rather than only that the lock resolves.
- **Give the ranking its own capability, `embedding-benchmark-ranking`.**: The `ai-benchmark` capability covers the servers that the benchmark sends requests to, so the ranking and the metrics keep their own purpose.

## Rejected alternatives

- **Apply the finished patch at `.data/agent/scratch/481a-numpy-ranking.patch`.**: The probe says the path is no file of the staging commit, and `AGENTS.md:20:Keep your own files out of git.` keeps `.data/agent/` out of the repository.
- **Use a raw numpy dot product with no normalization.**: `src/devops_cli/ai/vector_similarity.py:20:return float(dot / (norm_a * norm_b))` divides by both norms, so raw scores would change the ranking.
- **Keep the inline metrics and the C901 suppression.**: The per-pair loop at `src/devops_cli/ai/benchmark/embedding_runner.py:443:for idx, (eval_item, q_vec) in enumerate(zip(pairs, query_vectors, strict=False)):` is the path that the issue replaces and the reason for the marker.
- **Wait for a `linux/arm64` wheel of `pytrec-eval-terrier` before the change.**: The release service image build sets `.github/workflows/release.yml:411:platforms: linux/amd64`, and the pull request Service Image job runs on `ubuntu-26.04` with no platform override.
- **Keep `compute_ndcg_at_k` in the runner as a re-export for the three test modules.**: `AGENTS.md:3:a change removes the old path and adds no shim.` refuses a compatibility shim for a removed name.

## Unchanged references

- `src/devops_cli/ai/vector_similarity.py` (definition): The helper stays for the shortlist ranking, and the benchmark stops calling it per pair.
- `src/devops_cli/roadmap/nearest.py` (import): The shortlist still ranks its candidates with `cosine_similarity`; the benchmark change does not touch it.
- `tests/support/fakes/qdrant.py` (import): The Qdrant fake keeps its scoring; the benchmark change does not touch it.

## Security

Two runtime dependencies enter the Service and runner images: numpy, already locked through formulaic, and pytrec-eval-terrier, a new compiled extension that only the embedding benchmark imports. A person must confirm that pytrec-eval-terrier is MIT licensed, maintained and free of advisories, and that its linux/amd64 Python 3.14 wheel resolves, because the image installs the lock with hashes. `uv run devops ci deps` fails if the import leaves the declared dependency, `uv run devops ci lockfile` fails if `pyproject.toml` and `uv.lock` differ, and the Service Image check fails if the image cannot import numpy or pytrec_eval.
