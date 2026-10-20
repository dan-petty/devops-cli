# Task: No Test Connects to a Localhost Service It Did Not Start, and a Guard Fails One That Does (#1741)

**Issue**: [#1741](https://github.com/dan-petty/devops-cli/issues/1741)
**Scope**: scope/ci
**Feasibility**: A probe of every in-process loopback connect over the full suite at `-n 4` found these. The network block refused every one, but each refusal sent its client into retry backoff.

| Service | Port | Tests | Connects |
|---|---|---|---|
| OTLP export | 4318 | 2,249 | 8,116 |
| Valkey | 6379 | 79 | |
| Qdrant | 6333 | 10 | |
| Ollama | 11434 | 5 | |
| Gateway | 4000 and 8787 | 2 | |
| k8s port-forward probes | 14 ports | 2 | |
| Ports picked by hand to refuse | various | about 12 | |

## Description

- [x] Tests that need a model take `model_fake`. A test that needs a service to be down uses `refusing_port`, a loopback port the test binds and never listens on, so the kernel refuses each connect. That covers Qdrant, the gateway, Valkey in tests that build their own `Settings()`, and the ports picked by hand. The k8s port-forward probes are refused at `socket.create_connection`.
- [x] Retry waits behind a direct `time.sleep` return at once through the stdlib clock fallback, and the embedding and `rag status` tests assert the backoffs they took.
- [x] The floor sends telemetry export and the Valkey cache to `unserved_side_channel_port`, a refusing port bound for the run.
- [x] The network block treats a loopback port as the test's while a socket in the test process binds it. `unexpected_loopback_connects` fails a test at teardown that connected to any other loopback port, naming host, port and thread, even when the code swallowed the refusal.
  - With bind tracking off, the guard's own test fails.
  - It covers in-process TCP loopback only, not child processes or AF_UNIX sockets.
- [x] The guard surfaced two leaks, fixed at the source:
  - the floor now clears the investigation cache after each test, which had carried one test's Qdrant address into the next;
  - `test_llm_client_properties_and_list_models` waits for its preload and asserts its result.
- [x] Six files (`test_ai_subcommands_rag`, `test_builtin_tools`, `test_rag_embeddings`, `test_rag_cli`, `test_rag_drift`, `test_ai_cmd`) went from 76.86s to 56.80s, run back to back at load 15-26.
  - `test_try_retrieve_rag_context_success`: 5.03s to 0.45s.
  - The unreachable-gateway embedding test: 4.21s to 0.18s.
  - Every assertion is kept, and product code is unchanged.
- Left to other items:
  - real connects to the Docker socket in 13 tests (#1316);
  - the knowledge-base sync cooldown that carries across tests (#1310);
  - a seam for retry sleeps (#1320);
  - `TieredCache` dialling `localhost:6379` whatever Valkey is configured (#1165).
