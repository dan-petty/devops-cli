# Design

## Context

`EmbeddingsEngine` in `src/devops_cli/ai/rag/embeddings.py` keeps one batch size for all of its calls. `_embed_ollama` and `_embed_openai` read it once at the start of a call and cut the texts of the call into batches of that size. Two workers send the batches of a call to a direct Ollama node in parallel by default (`DEFAULT_OLLAMA_MAX_PARALLEL`). After each Ollama batch, `_record_batch_latency` halves the size (AIMD multiplicative decrease) or counts a fast batch toward an increase of two texts (AIMD additive increase). A timeout on a node or at the gateway halves the size too. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- The parallel slow or timed-out batches of one size halve the batch size once.
- The size grows back only after a cooldown, and only from batches that are fast by a margin below the threshold.
- No alias of `_apply_aimd_decrease` stays.

**Non-Goals:**

- The circuit breaker of the Valkey cache tier and of the RAG lookup pause (#2073).
- The failback of gateway routes (#1986).
- An increase on the gateway path. That path records no latency, as before.

## Decisions

- **The sent size is the number of texts that the batch holds.** `_query_ollama_node_batch`, `_try_single_candidate` and `_post_openai_batch_with_retry` have the texts of the batch, so they give `len(batch)` with no new parameter. A split half of a batch that failed on each node holds fewer texts, and a slow half halves the size when it is not larger than the size in use. Rejected: the batch size that the call read at its start. Four methods would get one more parameter (`_embed_batch_with_subdivision`, `_try_query_candidate_nodes`, `_try_single_candidate`, `_query_ollama_node_batch`), and a slow half of 2 texts would not halve a size of 2 texts, because the call read 4. Rejected: a count of the changes of the size that each batch keeps from the time it was sent. The issue names the size, and the size gives the same result for the parallel batches of a call without one more field.
- **A skipped decrease changes nothing.** A batch that holds more texts than the size in use gives no information about the size in use. So it does not halve the size, does not start the cooldown and does not stop the run of fast batches.
- **The cooldown starts at each change of the size, and a fast batch in the cooldown does not count.** Rejected: a cooldown after a decrease only. After such a cooldown, 32 fast batches would take the size from 1 text to 32 texts as fast as before, which is the measurement of #596. With the cooldown at each change, the size grows by at most two texts in each cooldown.
- **The cooldown is the default read timeout of a node, 15 s.** A node gives its reply or its timeout for a request in that time or less. Thus no request that was sent before a change counts toward the next increase. The comment at the default in `src/devops_cli/config/defaults.py` gives this basis.
- **The margin is half of the threshold.** One increase step adds 2 texts, so the new size is at most two times the old size for a size of 2 texts or more. When the latency increases at most linearly with the size, a size whose batch takes half of the threshold can become two times as large and stay at or below the threshold. The 0.5 margin is also the margin that #596 names. The comment at the default gives this basis.
- **A batch between the margin and the threshold stops the run of fast batches.** The increase needs fast batches in a row (`CONST_AIMD_SUCCESS_THRESHOLD`), and a batch near the threshold is not fast.
- **The latency comes from the clock seam.** `_query_ollama_node_batch` reads `devops_cli.core.clock.monotonic`, which is `time.monotonic` in production, as the cooldown does. The `clock` fixture moves that reading, so a test makes a batch slow with no real wait. Rejected: patch `time.monotonic` in the tests. docs/TESTING.md permits a patch of the standard library only when no seam exists, and time-machine does not move `time.monotonic`.

## Risks / Trade-offs

- [The size grows back slowly] → From 1 text to 32 texts takes at least 16 cooldowns, about 4 minutes, of fast batches. A run with a slow node sends smaller batches for a longer time, which is the purpose of the cooldown.
- [The last batch of a call holds fewer texts] → When it is slow, it halves the size again if the size in use is not smaller than it. That batch gives information at a size that is not larger than the size in use.
