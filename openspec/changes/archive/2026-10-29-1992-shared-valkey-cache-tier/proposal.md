# Proposal

## Why

Issue #1992: each fail-soft cache built its own Valkey client. While Valkey was down, each cache spent its own connection attempt, and a silent host cost the full `valkey.timeout` (2.0 s) for each one.

#2073 put each cache behind a `ValkeyCacheTier` with a pybreaker circuit breaker. That removed the engine's probe client and its literal `0.1`. But each `EmbeddingsEngine` and each `CloudflareRadarClient` still built its own tier through `configured_cache_tier`, so each held its own client, pool and breaker. `devops ai ingest` built a fifth client through the private `_resolve_client` of the `devops valkey` command, and pinged it.

## What Changes

- `shared_cache_tier()` in `valkey/cache.py` builds one tier for each process from the loaded settings, on first use, under a lock. The embeddings engine, the Radar client and the library store of `devops ai ingest` use it. A client that a caller passes still gets its own tier.
- `ValkeyClient` takes `connect_timeout` (valkey-py's `socket_connect_timeout`). The shared tier waits `DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS` (0.25 s), and never longer than `valkey.timeout`, for a connection. A command still waits `valkey.timeout`.
- When the tier cannot be built, for example because `valkey.url` is not valid, the process logs one warning and each cache runs with no Valkey tier. Before, each cache gave up in silence through `except Exception`.
- `LibraryVectorStore` takes the tier (`symbol_cache`) in place of a client. `devops ai ingest` passes the shared tier, so it pings nothing and no longer imports the command module's private function. A dry run has no tier.
- The floor resets the shared tier after each test. The generic reset rule of `docs/TESTING.md` covers it.
- The `valkey.timeout` description names the shorter connect wait of the cache.
- A cache now behaves differently when Valkey is down or `valkey.url` is not valid, so the change carries a spec delta in `valkey-cache-tier`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `valkey-cache-tier`: the caches of a process share one tier; the tier waits a short time for a connection; a tier that cannot be built gives one warning.

## Impact

- `src/devops_cli/valkey/cache.py`, `src/devops_cli/valkey/client.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`.
- `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/security/vulnerability_lookup.py`, `src/devops_cli/ai/rag/library_store.py`, `src/devops_cli/commands/ai_ingest.py`.
- `tests/conftest.py`, `tests/test_valkey_cache_tier.py`, `tests/test_library_vector_tier.py`, `tests/fixtures/swallowed_failures_ceilings.json`.
- The generated `docs/CONFIGURATION.md` and `docs/ENV_VARS.md`.

## Feasibility

Measured on origin/main `6ae7123d` (2026-10-29, host load about 10):

- Two `EmbeddingsEngine`s and one `CloudflareRadarClient` built 3 `ValkeyClient`s and 3 tiers, and none of them was shared. `devops ai ingest` built one more client and pinged it.
- First reads of 3 tiers while Valkey refused the connection took 0.002 s. While the host was silent (`192.0.2.1:6379`), they took 6.01 s, 2.0 s for each tier. With one shared tier, a silent host costs one attempt of at most 0.25 s in each 60 s cooldown.
- A connect to a listening loopback socket took a median of 24 µs, with a p99 of 154 µs and a maximum of 583 µs (2,000 connects). A connect from the gateway pod to an Ollama Service on another node of the homelab took a median of 116 µs, with a p99 of 293 µs and a maximum of 411 µs (500 connects). So 0.25 s is more than 400 times the slowest connect.
- valkey-py's `ConnectionPool` takes `socket_connect_timeout` apart from `socket_timeout` (valkey-py 6.2.0, `valkey/connection.py`).
- #1113, the parent, is closed. Its last comment names #1992 as the owner of this step. #596 is closed, and #2073 built the breaker that this change shares.

## Existing Tool Considered

valkey-py's own `ConnectionPool` and `socket_connect_timeout` give the sharing and the short connect wait. pybreaker, from #2073, gives the breaker. The change builds no breaker, no half-open state and no cooldown of its own. It deletes `_resolve_runtime_valkey_client` and `_symbol_cache_tier`, and the three `except Exception` sites that each cache had around its own tier.
