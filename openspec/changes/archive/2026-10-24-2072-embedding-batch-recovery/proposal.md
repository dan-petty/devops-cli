# Proposal

## Why

Issue #2072, the first of the three pull requests of #596: the embedding batch size of the engine had transitions that were wrong. `_embed_ollama` cuts the texts of a call at the batch size once, at the start of the call. Each slow batch of that call halved the size again, although no batch of the call was sent at the smaller size. One call with each batch slow thus took the size from 32 texts to 1 text. The two timeout paths did the same. In the other direction, each batch at or below the 2.0 s threshold counted toward an increase, with no cooldown and no margin below the threshold. Thus the size could grow back to the size that was slow. #430 also left `_halve_batch_size`, an alias that the no-shim rule of AGENTS.md does not permit.

## What Changes

- `_record_batch_latency` and the two timeout paths (`_try_single_candidate` for a direct Ollama node, `_post_openai_batch_with_retry` for the gateway and OpenAI-compatible APIs) give `_apply_aimd_decrease` the number of texts that the batch holds. A batch that holds more texts than the size in use does not halve the size: it was sent before an earlier decrease, and that decrease applies to it too.
- A batch to a direct Ollama node counts as fast only when it takes at most half of the latency threshold (`DEFAULT_RAG_EMBEDDING_INCREASE_LATENCY_RATIO`). A batch between that margin and the threshold stops the run of fast batches.
- A fast batch counts only when the cooldown (`DEFAULT_RAG_EMBEDDING_INCREASE_COOLDOWN_SECONDS`, 15 s) has passed since the last change of the size. Each decrease and each increase starts the cooldown again.
- The engine reads the latency of an Ollama batch and the time of the cooldown through `devops_cli.core.clock.monotonic`, the clock seam that the `clock` fixture fakes.
- `_halve_batch_size` and its tests go. `tests/test_rag_aimd.py` goes: its cases called the private methods, and the new tests in `tests/test_rag_embeddings.py` hold the same rules through `embed_texts`, the shared HTTP fake and two workers.
- The change alters the size of the batches that the engine sends to an embedding service, which the service observes, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `embedding-batch-size`: the number of texts in one embedding batch, how a slow or timed-out batch makes it smaller, and how fast batches make it larger again.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/rag/embeddings.py` (`_apply_aimd_decrease`, `_apply_aimd_increase`, `_record_batch_latency`, `_query_ollama_node_batch`, `_try_single_candidate`, `_post_openai_batch_with_retry`; `_halve_batch_size` deleted) and `src/devops_cli/config/defaults.py` (two new defaults, with their basis).
- Tests: `tests/test_rag_embeddings.py`; `tests/test_rag_aimd.py` deleted.
- The Valkey code of the engine does not change. #2073, the second pull request of #596, changes it.

## Feasibility

- On main at 0a2bfe1f, `src/devops_cli/ai/rag/embeddings.py` held `_halve_batch_size` (line 531), `_record_batch_latency(elapsed)` with no batch size (line 535), and `_embed_ollama`, which reads `_current_batch_size` once per call (lines 951-960). `_try_single_candidate` and `_post_openai_batch_with_retry` called `_apply_aimd_decrease()` with no batch size.
- On the base, the new tests failed (5 failed, 66 passed). Two parallel batches of 4 texts that timed out on an Ollama node took the size to 1 text, and the four fast halves that the engine sent next took it back to 4 texts with no cooldown, so the next call sent batches of 4 texts. Two gateway batches of 4 texts that timed out took the size to 1 text. The base read the latency of an Ollama batch with `time.monotonic`, which the `clock` fixture does not move, so the latency tests could not make a batch slow there. The cooldown and margin tests failed because the two defaults did not exist.
- After the change, a mutation of each rule fails its tests: with no skip of the larger batch, the three halving tests fail; with no cooldown, the cooldown test and the Ollama timeout test fail; with no margin, or with no stop of the run by a batch in the margin, the margin test fails.

## Existing Tool Considered

No library is used. The standard library and the dependencies of the project have no control of an adaptive batch size: tenacity and `devops_cli.ai.retries` give retry waits, and `ratelimit` gives a call window. The libraries for adaptive concurrency limits, such as Netflix concurrency-limits, are for the JVM. The change keeps the AIMD code that #430 added and adds three conditions to it: the skip of a larger batch, the margin and the cooldown. The cost to build is about 150,000 tokens, with the tests and this record, and about one hour of elapsed time. The cost to keep and fix it is small: about 40 lines in one module, held by five tests.

The time comes from the existing clock seam, `devops_cli.core.clock`, and the tests move it with the existing `ClockFake` over time-machine.

The change deletes `_halve_batch_size`, `tests/test_rag_aimd.py`, and the two tests of `tests/test_rag_embeddings.py` that called `_halve_batch_size` and `_record_batch_latency` directly.
