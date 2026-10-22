# Task: valkey-py replaces the hand-written RESP client, connection pool and protocol parser (#1113)

**Issue**: [#1113](https://github.com/dan-petty/devops-cli/issues/1113)
**Scope**: scope/cli, scope/security
**Feasibility**: Checked against valkey-py 6.2.0 (released 2026-10-12, MIT, `requires-python >=3.11`, `py.typed`, no required runtime dependency on Python 3.14), installed into the project environment with `uv add`, which adds only valkey, fakeredis 2.40.0 (dev group) and redis 8.1.0 to `uv.lock`. A client over `valkey.ConnectionPool` was run on CPython 3.14.7 against fakeredis's in-memory Valkey server and against loopback sockets: a wrong password, a refused port, a silent listener, a rejected command and a dropped server each raise a valkey-py exception, and a pipeline raises it from `execute`, outside any single-command wrapper, so the client maps failures around every call it makes. `uv run mypy src` (strict) accepts the client once calls into valkey-py's unannotated functions go through one helper. `python -X importtime` shows no `valkey` module imported by `devops --help`. The checks for Part 2 ran on the release tip 3ef69850. A search of `src` and `tests` found no user outside the deleted code. The search covered the two package names, every exported symbol, the tier constants and the `ai.cache.backend` option. A search of `src` found no reader of the setting. A config file that still holds `ai.cache.backend` loads. The next save drops the key, because `AICacheConfig` ignores unknown keys. Now `devops config get ai.cache.backend` exits 1 with `Unknown config key`.

## Description

Part 1 of #1113 follows the owner decision of 2026-10-22, which names valkey-py 6.2.0 as the client. The hand-written RESP stack (`protocol.py`), connection pool (`pool.py`), pipeline byte chunking and INFO parser are replaced by valkey-py. `ValkeyClient` stays the one seam the callers use: it keeps the destination check that refuses link-local and, unless private networks are allowed, non-public addresses, now repeated each time a connection dials, and it raises the `ValkeyError` family for every failure valkey-py reports. The pool, the token-bucket rate limiter and the tiered cache's `cached` decorator, `get_cache` and `reset_cache`, which no code in `src/` used, are deleted with their tests, constants and ceiling entry. With the pool gone `get_cache` could build only an L1 cache, while `cached` still offered `tier="l2"` and the module still called L2 Valkey.

Part 2 of #1113 deletes the rest of the old cache code. It deletes the `devops_cli.cache` package. That package holds `TieredCache`, `devops_cli.cache.LRUCache`, `CacheStats` and the two key builders. Part 2 also deletes `ValkeyCacheProvider` in `devops_cli.ai.cache`, the tests of both packages and the `ai.cache.backend` setting. Only the provider used the tiered cache. Only tests built the provider. Nothing read `ai.cache.backend`. The response cache of `devops ai cache` (`ai/response_cache.py`) has its own memory and disk tiers. It has no backend choice.

Behaviour that changes with Part 2:

- `ai.cache.backend` and `DEVOPS_CLI_AI_CACHE_BACKEND` do not exist. The config loader ignores a saved `ai.cache.backend` key, and the next save drops it. There is no shim.
- Part 2 deletes `ValkeyClient.delete` and `ValkeyClient.scan_iter`, because only the provider called them. It also deletes `DEFAULT_VALKEY_SCAN_COUNT`, which only `scan_iter` read.
- Part 2 deletes the constants that only the deleted code read: `DEFAULT_AI_CACHE_TTL_SECONDS`, `DEFAULT_CACHE_L1_MAX_ENTRIES`, `DEFAULT_CACHE_TTL_SECONDS`, `CONST_CACHE_KEY_SEPARATOR`, `CONST_CACHE_TIER_L1`, `CONST_CACHE_TIER_L2`, `CONST_CACHE_TIER_L1_L2` and `CONST_CACHE_TIERS`. `CONST_CACHE_NAMESPACE_ROOT` stays, because `ai/run_store.py` reads it.
- The Valkey knowledge-base page no longer claims a review-findings cache. Its `valkey-py` example class has the name `EmbeddingCache`. Its key examples use the real embedding key pattern `valkey:rag:embedding:<sha256-hex-digest>`.

Behaviour that changes with the library:

- Replies decode as UTF-8 with replacement, as before. `execute` returns replies as the server sent them (`PONG`, `OK`), so `devops valkey cli` prints what it printed.
- `set` takes `ex=` only; the `ttl=` and `ex_seconds=` keywords of the old client are gone. `ai/rag/library_store.py` passed `ttl=`, which valkey-py rejects, so the call is changed to `ex=` and a test now stores symbols through the real client.
- `set(..., ex=0)` and a negative `ex` reach the server, which rejects them; the old client sent a plain `SET`. A `bool` command argument raises `ValkeyCommandError`, which the old client sent as `true`.
- A pipeline goes out in batches of at most `DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS` commands. The 8 MiB byte budget is dropped: it was a target, not a guarantee, and valkey-py does not bound the payload.
- The embeddings engine probes Valkey with a throwaway client at 0.1 s and keeps a second client at the configured timeout, since valkey-py has no socket to retime.

## Acceptance Criteria

- [x] `valkey/protocol.py`, `valkey/pool.py` and `valkey/rate_limiter.py` are gone, and no file in the tree outside the historical archive names `encode_command`, `parse_resp`, `ValkeyConnectionPool`, `get_pool`, `reset_pool`, `parse_info_response` or `ValkeyTokenBucketRateLimiter`.
- [x] Every `DEFAULT_VALKEY_*` constant that only the deleted code read is deleted from `config/defaults.py`; the conftest reset entries for `devops_cli.valkey.pool` and `devops_cli.cache.tiered` and the `valkey/pool.py` swallowed-failures ceiling are removed, and the `cache/tiered.py` ceiling is lowered by the one swallow `_resolve_backend` held.
- [x] The destination check refuses a link-local target always and a non-public one unless private networks are allowed, at construction and again at the dial (`TestValkeyClientDestination` in `tests/test_valkey.py`).
- [x] A wrong password, a rejected command, a pipeline error, a dropped server, a refused port and a silent server raise `ValkeyAuthenticationError`, `ValkeyCommandError`, `ValkeyCommandError`, `ValkeyConnectionError`, `ValkeyConnectionError` and `ValkeyTimeoutError` (`TestValkeyClientFailures`).
- [x] One shared in-memory Valkey server (`tests/support/fakes/valkey.py`, fakeredis `FakeServer`) backs the client, tiered-cache, library-store and `devops valkey` tests, and 8 threads sharing one client each read their own replies.
- [x] `TieredCache` takes an explicit backend and is L1-only without one; `ValkeyCacheProvider.flush_ai_cache` lists its keys before testing for emptiness. `cached`, `get_cache`, `reset_cache` and the re-exports of the three are gone, and the module describes L2 as the backend a caller injects. Part 2 deletes the module.
- [x] The client's own `password`, `db`, `decode_responses`, `encoding_errors` and `allow_private_network` arguments are checked through the pool it builds, not through the fake's pool: a loopback server records what a new connection sends (`AUTH` with the password only when one is given, `SELECT` with the database number only when it is not 0), a reply that is not UTF-8 decodes with replacement through `get` and `execute`, and a name that resolves to loopback at the dial is refused when private networks are disallowed (`TestValkeyClientConnection` and `TestValkeyClientDestination`). Each of those tests fails when its constructor argument is ignored.
- [x] `devops docs generate --sync-readme` leaves `devops docs check` clean, `uv run devops ci --only deps,constructs,lockfile` passes, and `uv run mypy src`, `uv run ruff check src tests` and `uv run ruff format --check src tests` pass.
- [x] `src/devops_cli/cache/`, `src/devops_cli/ai/cache/`, `tests/test_cache_tiered.py` and `TestValkeyCacheProvider` are gone.
- [x] A whole-word search of `src`, `tests` and `docs` finds no `devops_cli.cache`, `TieredCache`, `devops_cli.cache.LRUCache`, `CacheStats`, `build_cache_key`, `digest_key` or `ValkeyCacheProvider`. The search skips the archive and the task files. The `cachetools.LRUCache` of the GitHub session transport is a different class, and it stays.
- [x] `ai.cache.backend` is no option, no environment variable and no `AICacheConfig` field. `test_the_ai_cache_backend_is_not_a_config_option` checks the option, the variable, the field and the exit code of `devops config get ai.cache.backend`. It fails on the tree before Part 2 and passes after it.
- [x] The commit removes the `cache/tiered.py` entry from `tests/fixtures/swallowed_failures_ceilings.json`. The suppression ceilings equal their measured counts, so none changes.
- Pending a person: against a real Valkey 8 (a workstation instance, then the cluster's run index), `uv run devops valkey ping`, `uv run devops valkey info`, `uv run devops valkey stats`, `uv run devops valkey cli INFO server` and `uv run devops ai runs reindex` succeed. The in-memory server has no INFO command, so CI reads INFO only from a canned loopback reply.
- Pending a person: with `requirepass` set on that server, `uv run devops valkey ping` reports an authentication error under a wrong keyring password and connects under the right one.

## Deliverables

- [x] Add `valkey==6.2.0` to the dependencies and `fakeredis[valkey]==2.40.0` to the `dev` group, and lock them.
- [x] Rewrite `src/devops_cli/valkey/client.py` as a client over valkey-py: endpoint parsing, destination check, a guarded connection class, failure mapping, and the commands the callers use.
- [x] Delete `protocol.py`, `pool.py` and `rate_limiter.py`, and empty the package `__init__.py` of their re-exports.
- [x] Remove the pool from `TieredCache`, delete `cached`, `get_cache` and `reset_cache`, change `library_store.py` to `ex=`, and rework `_init_valkey` in `ai/rag/embeddings.py`.
- [x] Delete the pool, RESP, rate-limiter and socket-level client tests and `tests/test_valkey_concurrency.py`; add client tests over the shared fake and over loopback sockets, one of which records the commands a connection sends and answers INFO from a canned reply; move the tiered-cache, library-store and `devops valkey set` / `cli` tests onto the shared fake.
- [x] Remove the rate-limiter bullet from the Valkey knowledge-base page and add the fake to `docs/TESTING.md`.
- [x] Delete `src/devops_cli/cache/`, `src/devops_cli/ai/cache/`, `tests/test_cache_tiered.py` and `TestValkeyCacheProvider`, and remove the `ai.cache.backend` option, its environment variable and its `AICacheConfig` field.
- [x] Delete `ValkeyClient.delete`, `ValkeyClient.scan_iter` and the constants that only the deleted code read, and keep `CONST_CACHE_NAMESPACE_ROOT`.
- [x] Lower the swallowed-failure ceilings, edit the knowledge-base class name and key examples, and regenerate `docs/ENV_VARS.md` and `docs/CONFIGURATION.md`.
- [x] Add a short note to the task files of #154, #312 and #1741, which describe the deleted code as present.
- Not done: one validated `valkey.url` with `--url` on the `devops valkey` commands, in place of `valkey.host`, `valkey.port` and `valkey.db` (a later Part of #1113).
- Not done: resolve a name once, check every answer and dial the checked address, under #898's resolve-and-check function (a later Part of #1113).
- Not done: build the k8s URLs with `httpx2.URL` (a later Part of #1113).
- [x] Fix the dashboard INFO reading and its plaintext password. `docs/agent/tasks/task-1113-the-valkey-dashboard-panel-reads-the-real-client.md` describes this step.
- Not done: share one fail-soft client between the embeddings, library-symbol and threat-intel caches (a later Part of #1113).
- Not done: add a contract suite for the in-memory Valkey server. A recorded exchange or a local Valkey must become available first (a later Part of #1113).
- Not done: add the changelog fragment `changelog.d/1113.md`. The Part that closes #1113 adds it.
