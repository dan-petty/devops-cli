# Design

## Context

See proposal.md for the motivation and the scope (#3862, item 2 of #1329). The change is test-only. It touches no path under `src/`.

## Decisions

### 1. Doubles only at edges, through the shared fake

- **Decision**: a test of `ai/rag` installs `qdrant`, `embedder`, `valkey_client`, `web`, `clock`, `otlp`, `keyring_store`, `cluster` or `process_fake`, and runs the product code for real. The fakes gain scripting (`fail_next`, `before_embed`, `on_search`, `fail_operation`) where a test needs a slow, failing or refusing edge.
- **Alternative considered**: keep a hand-rolled double in each file and only drop the patches.
  - *Rejected*: ADR 0007 and `docs/TESTING.md` allow one fake for each edge. Ten doubles in eight files had drifted apart (for example, two `FakeQdrantClient` classes with different signatures from `QdrantProtocol`).

### 2. A loopback server shows what the native Qdrant client sends

- **Decision**: `serving_qdrant` in `tests/support/fakes/qdrant.py` is a loopback HTTP server that answers the REST calls the client makes to list collections, set up a collection and query points. It records each request, can cut a connection, and can serve a stored collection description. A test reads the API key header, the proxy prefix, the quantization config and the payload indexes from the record.
- **Alternative considered**: the native client in its in-memory mode (as the contract suite uses it).
  - *Rejected for these cases*: the mode drops quantization and payload indexes, and it has no transport to fail. It stays in use where the test needs only a working client (the span and search tests).
- **Alternative considered**: patch `NativeQdrantClient` at `devops_cli.ai.rag.qdrant`.
  - *Rejected*: it patches a devops-cli name, which is what the item removes.

### 3. Query stage times are not set by the test

- **Decision**: `time-machine` does not move `time.perf_counter` or `time.monotonic`. The stage test reads the OTLP fake and checks the stage and outcome labels, and that the total is not less than the sum of its stages.
- **Alternative considered**: patch `retriever.time` with a counter, as the old test did.
  - *Rejected*: it patches a devops-cli name. Exact stage durations are not a behavior of the retriever; the labels are.

### 4. The investigation concurrency test waits on thread state, not on a patch

- **Decision**: the test holds the probe lookup in the embedder (`before_embed`), starts the 19 other lookups, and releases the probe when every thread waits on a lock or an event (`sys._current_frames`). The old test patched `_PROBE_COORDINATOR.coordinate` to count arrivals.
- **Alternative considered**: count the lookups that entered `investigate_rag_context`.
  - *Rejected*: a thread that has entered may not yet wait. The probe could then fail first, and the late thread would send its own request. The test would fail on correct code on a loaded host.

### 5. The gateway dial double moves to the shared fakes

- **Decision**: `Gateway`, `GatewayConnection` and `dial_gateway` move from the old embeddings test file to `tests/support/fakes/gateway_dial.py`. Tests of a reply that arrives after the client closed its connection, and of the read timeout of one request, need a socket-level double, and the `web` fake sits above that level.
- **Alternative considered**: serve these cases with the `web` fake.
  - *Rejected*: the fake cannot show a closed connection or the read timeout that the engine passes to httpcore.

### 6. Tests of private names go, and the behavior stays

- **Decision**: a test of `_EmbeddingLRUCache`, `_apply_model_prefix`, `_calculate_backoff_delay`, `_reply_vectors`, `_probe_ollama_embed_dimension`, `_scan_file_drift` or `_build_quantization_config` becomes a test of `embed_texts`, `dimension`, `detect_drift` or `ensure_collection`. The tests that checked only the double (payload indexes of a fake, `test_rag_rrf.py`) are deleted. The cache key test of the server label file read a private dictionary, and the behavior it protected stays in the compatibility file.

### 7. A CLI test runs in `tmp_path`

- **Decision**: `tests/commands/test_ai_rag_commands.py` changes into `tmp_path` for each test, because the default index cache is the relative path `.data/rag`. Without it, tests wrote to the repository's `.data/rag` and shared their state. #1036 moves the default under the data directory and is not part of this item.
