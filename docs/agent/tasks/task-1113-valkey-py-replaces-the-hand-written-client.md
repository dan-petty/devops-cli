# Task: valkey-py replaces the hand-written RESP client, connection pool and protocol parser (#1113)

**Issue**: [#1113](https://github.com/dan-petty/devops-cli/issues/1113)
**Scope**: scope/cli, scope/security
**Feasibility**: Checked against valkey-py 6.2.0 (released 2026-10-12, MIT, `requires-python >=3.11`, `py.typed`, no required runtime dependency on Python 3.14), installed into the project environment with `uv add`, which adds only valkey, fakeredis 2.40.0 (dev group) and redis 8.1.0 to `uv.lock`. A client over `valkey.ConnectionPool` was run on CPython 3.14.7 against fakeredis's in-memory Valkey server and against loopback sockets: a wrong password, a refused port, a silent listener, a rejected command and a dropped server each raise a valkey-py exception, and a pipeline raises it from `execute`, outside any single-command wrapper, so the client maps failures around every call it makes. `uv run mypy src` (strict) accepts the client once calls into valkey-py's unannotated functions go through one helper. `python -X importtime` shows no `valkey` module imported by `devops --help`.

## Description

First step of #1113, whose owner decision of 2026-10-22 names valkey-py 6.2.0 as the client. The hand-written RESP stack (`protocol.py`), connection pool (`pool.py`), pipeline byte chunking and INFO parser are replaced by valkey-py. `ValkeyClient` stays the one seam the callers use: it keeps the destination check that refuses link-local and, unless private networks are allowed, non-public addresses, now repeated each time a connection dials, and it raises the `ValkeyError` family for every failure valkey-py reports. The pool, the token-bucket rate limiter and the tiered cache's `cached` decorator, `get_cache` and `reset_cache`, which no code in `src/` used, are deleted with their tests, constants and ceiling entry. With the pool gone `get_cache` could build only an L1 cache, while `cached` still offered `tier="l2"` and the module still called L2 Valkey.

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
- [x] `TieredCache` takes an explicit backend and is L1-only without one; `ValkeyCacheProvider.flush_ai_cache` lists its keys before testing for emptiness. `cached`, `get_cache`, `reset_cache` and the re-exports of the three are gone, and the module describes L2 as the backend a caller injects.
- [x] The client's own `password`, `db`, `decode_responses`, `encoding_errors` and `allow_private_network` arguments are checked through the pool it builds, not through the fake's pool: a loopback server records what a new connection sends (`AUTH` with the password only when one is given, `SELECT` with the database number only when it is not 0), a reply that is not UTF-8 decodes with replacement through `get` and `execute`, and a name that resolves to loopback at the dial is refused when private networks are disallowed (`TestValkeyClientConnection` and `TestValkeyClientDestination`). Each of those tests fails when its constructor argument is ignored.
- [x] `devops docs generate --sync-readme` leaves `devops docs check` clean, `uv run devops ci --only deps,constructs,lockfile` passes, and `uv run mypy src`, `uv run ruff check src tests` and `uv run ruff format --check src tests` pass.
- Pending a person: against a real Valkey 8 (a workstation instance, then the cluster's run index), `uv run devops valkey ping`, `uv run devops valkey info`, `uv run devops valkey stats`, `uv run devops valkey cli INFO server` and `uv run devops ai runs reindex` succeed. The in-memory server has no INFO command, so CI reads INFO only from a canned loopback reply.
- Pending a person: with `requirepass` set on that server, `uv run devops valkey ping` reports an authentication error under a wrong keyring password and connects under the right one.

## Deliverables

- [x] Add `valkey==6.2.0` to the dependencies and `fakeredis[valkey]==2.40.0` to the `dev` group, and lock them.
- [x] Rewrite `src/devops_cli/valkey/client.py` as a client over valkey-py: endpoint parsing, destination check, a guarded connection class, failure mapping, and the commands the callers use.
- [x] Delete `protocol.py`, `pool.py` and `rate_limiter.py`, and empty the package `__init__.py` of their re-exports.
- [x] Remove the pool from `TieredCache`, delete `cached`, `get_cache` and `reset_cache`, change `library_store.py` to `ex=`, and rework `_init_valkey` in `ai/rag/embeddings.py`.
- [x] Delete the pool, RESP, rate-limiter and socket-level client tests and `tests/test_valkey_concurrency.py`; add client tests over the shared fake and over loopback sockets, one of which records the commands a connection sends and answers INFO from a canned reply; move the tiered-cache, library-store and `devops valkey set` / `cli` tests onto the shared fake.
- [x] Remove the rate-limiter bullet from the Valkey knowledge-base page and add the fake to `docs/TESTING.md`.
- Delete the unused `devops_cli.cache` package (`TieredCache` and its key helpers, whose only user is `ValkeyCacheProvider`), `ValkeyCacheProvider` and the `ai.cache.backend` option: a later step of #1113.
- Replace `valkey.host`, `valkey.port` and `valkey.db` with a validated `valkey.url`, with `--url` on the `devops valkey` commands: a later step of #1113.
- Resolve a name once, check every answer and dial the checked address, under #898's resolve-and-check function: a later step of #1113.
- Build the k8s URLs with `httpx2.URL`, and fix the dashboard's INFO reading and its plaintext password: a later step of #1113.
- Share one fail-soft Valkey client between the embeddings, library-symbol and threat-intel caches: a later step of #1113.
- A contract suite for the in-memory Valkey server, if a recorded exchange or local Valkey ever becomes available to run it against: a later step of #1113.
