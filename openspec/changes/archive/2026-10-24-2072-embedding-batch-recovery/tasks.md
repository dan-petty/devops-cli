# Tasks

## 1. A slow batch halves the batch size once for the size it was sent at

- [x] 1.1 Write `test_parallel_slow_batches_halve_the_batch_size_once_for_the_size_they_were_sent_at`, `test_parallel_batches_that_time_out_on_an_ollama_node_halve_the_batch_size_once` and `test_parallel_gateway_batches_that_time_out_halve_the_batch_size_once` in `tests/test_rag_embeddings.py`, through `embed_texts`, the shared HTTP fake `_serve`, the `clock` fixture and two workers, and verify that `uv run devops ci test tests/test_rag_embeddings.py` fails on the base
- [x] 1.2 Give `_apply_aimd_decrease` the number of texts of the batch from `_record_batch_latency` and the two timeout paths, skip the decrease for a batch that holds more texts than the size in use, read the latency of an Ollama batch through `devops_cli.core.clock.monotonic`, and verify that `uv run devops ci test tests/test_rag_embeddings.py` passes
- [x] 1.3 Delete `_halve_batch_size`, its two tests in `tests/test_rag_embeddings.py` and `tests/test_rag_aimd.py`, whose cases the new tests hold through the public interface, and verify that `uv run devops ci test src/devops_cli/ai/rag/embeddings.py` passes

## 2. The batch size grows back only after a cooldown and below a margin

- [x] 2.1 Write `test_fast_batches_grow_the_batch_size_once_per_cooldown_up_to_the_configured_size` and `test_only_a_batch_within_the_margin_below_the_latency_threshold_counts_as_fast` in `tests/test_rag_embeddings.py`, and verify that `uv run devops ci test tests/test_rag_embeddings.py` fails on the base
- [x] 2.2 Add `DEFAULT_RAG_EMBEDDING_INCREASE_LATENCY_RATIO` and `DEFAULT_RAG_EMBEDDING_INCREASE_COOLDOWN_SECONDS` to `src/devops_cli/config/defaults.py` with the basis of each value, count a fast batch only within the margin and after the cooldown of the last change, start the cooldown at each change, and verify that `uv run devops ci test tests/test_rag_embeddings.py` passes
- [x] 2.3 Verify that `uv run ruff check`, `uv run ruff format --check` and `uv run mypy src/devops_cli/ai/rag/embeddings.py src/devops_cli/config/defaults.py` pass, regenerate the docs with `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- Pending a person: run `devops ai rag index` on a repository against the direct Ollama nodes while one node is slow, and read the `rag.embedding.batch_size` metric. The size halves once for each slow size and grows by two texts at most once in each 15 s.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
