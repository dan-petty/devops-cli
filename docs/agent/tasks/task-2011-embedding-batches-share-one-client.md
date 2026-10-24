# Task: A Timed-Out Embedding Batch Leaves the HTTP Client of the Other Parallel Batches Open (#2011)

**Issue**: [#2011](https://github.com/dan-petty/devops-cli/issues/2011)
**Scope**: scope/ai
**Feasibility**: Confirmed in the library source and in the Ollama logs of the cluster. In httpcore2 2.13.1, `ConnectionPool.close()` closes each connection of the pool, also a connection that another thread reads. A read on a closed socket raises `ReadError: [Errno 9] Bad file descriptor`. When a request fails, `HTTP11Connection._response_closed()` closes the connection of that request, and the pool removes it at the next request. Thus a retry gets a new connection from the same client. On 2026-10-23, `ollama-48gib-slow` answered 360 of 430 embedding requests, and the slowest reply took 76 s. The other 70 requests ended with status 400 after 29 to 30 s, which is the 30 s read timeout of the client. On `ollama-48gib`, the first request after a cold load of the embedder (18.57 s) ended at 29.75 s.

## Description

`EmbeddingsEngine` sends up to four embedding batches in parallel to the gateway, through one `httpx2.Client`. When one batch got a transient error, such as a read timeout, its retry closed that client. The other batches then read their replies from closed sockets and failed with `Bad file descriptor`. Each of them closed the client again, and `devops roadmap intake` reported a healthy gateway as down.

Now only `EmbeddingsEngine.close()` closes the client. A retry sends on the same client, and its connection pool replaces the connection that failed. This is the standard httpx pattern: one client for the life of its owner.

The read timeout of a gateway batch is the named default `DEFAULT_RAG_EMBEDDING_BATCH_TIMEOUT`, 120 s. Before, it was a hidden floor of 30 s, which stopped 70 batches on 2026-10-23. 120 s is more than 1.5 times the slowest reply that a tier gave on that day, and it is the cap that the engine puts on a configured timeout. A configured `ai.tasks.embedding.timeout` sets the read timeout of a gateway batch, also below 30 s. `DEFAULT_RAG_EMBEDDING_TIMEOUT` (15 s) stays the read timeout of one direct Ollama node, so that a batch fails over to the next node fast.

## Acceptance Criteria

- [x] A transient error in one parallel batch does not close the client that another batch uses. `test_a_batch_that_times_out_leaves_the_parallel_batches_their_connections` sends four batches through the real httpx2 client and httpcore2 pool. The first batch times out while the other three wait for their replies, and the three get their replies on their own connections.
- [x] No embedding request fails with `Bad file descriptor` because another batch closed the client. The same test records each reply that comes to a closed connection, and it finds none. On the base, three batches failed with `[Errno 9] Bad file descriptor`.
- [x] The read timeout of an intake embedding batch is a named default. `test_the_largest_intake_batch_gets_a_reply_as_slow_as_the_slowest_measured` sends 32 texts of 4,000 characters to a gateway that replies after 76 s, and the batch gets its reply. `test_a_configured_embedding_timeout_is_the_read_timeout_of_a_gateway_batch` shows that a configured timeout sets the read timeout.
- [x] The tests run offline: a fake socket under the httpcore2 pool answers each request.
- Pending a person: after the merge, run `env -u DEVOPS_CLI_AI_TASK_EMBEDDING_TIMEOUT uv run devops roadmap intake --plan --title "<title>" --body-file <file>`. The duplicate check embeds the board items and completes, no `Bad file descriptor` warning shows, and `--plan` writes nothing.

## Deliverables

- [x] `src/devops_cli/ai/rag/embeddings.py`: the retry path does not close the shared client. `close()` closes it once, and the client waits `batch_timeout` for a reply.
- [x] `src/devops_cli/config/defaults.py`: `DEFAULT_RAG_EMBEDDING_BATCH_TIMEOUT` (120 s), with the measurements that set it.
- [x] `tests/test_rag_embeddings.py`: the three tests above, over `_Gateway`, a fake socket under the real httpcore2 pool.
- [x] `tests/fixtures/swallowed_failures_ceilings.json`: the ceiling of `embeddings.py` goes from 12 to 10, because the `except Exception: pass` of the old reset is gone.
- [x] `k8s/llm/gateway/configmap.yaml` and `docs/agent/tasks/task-481-embeddings-through-the-gateway.md` no longer give the old client timeout.
