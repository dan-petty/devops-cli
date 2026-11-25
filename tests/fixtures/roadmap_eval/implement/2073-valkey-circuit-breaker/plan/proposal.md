# Proposal

## Why

Issue #2073, the second of the three pull requests of #596: one Valkey error turned the Valkey tier of a cache off for the rest of the run. The embeddings engine set `self._valkey = None` after a failed read or write (two places in `src/devops_cli/ai/rag/embeddings.py`), and the threat-intel client did the same after a failed read or write and after a failed construction (three places in `src/devops_cli/security/vulnerability_lookup.py`). The engine also probed Valkey once when it started, and a Valkey that did not answer the probe stayed off for the life of the engine. The library symbol store did the opposite: it sent each command to Valkey during an outage, so each lookup paid a connection attempt. No cache had a cooldown or a half-open state. The RAG lookup pause had a circuit breaker of its own, written by hand in `src/devops_cli/ai/rag/investigator.py`.

## What Changes

- pybreaker, a maintained circuit breaker library, becomes a dependency (`pybreaker==1.4.1`).
- `devops_cli.valkey.cache.ValkeyCacheTier` is the one seam at the Valkey boundary of the caches. It sends each read and write through a pybreaker breaker. One failed command opens the breaker (`DEFAULT_VALKEY_CACHE_BREAKER_FAILURES`). For the cooldown (`DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS`, 60 s) the tier sends no command: a read is a miss and a write does not occur. After the cooldown, one trial command decides: a trial that succeeds closes the breaker, and a trial that fails opens it for one more cooldown. A reply error (`ValkeyCommandError`) does not open the breaker. The tier records each change of state in the debug log.
- `configured_cache_tier` builds the tier over the Valkey that `valkey.url` names, with no DNS lookup and no connection.
- The embeddings engine, the threat-intel client and the library symbol store read and write through the tier. Every `self._valkey = None` goes, and so do the start probe of the engine and its probe client with a timeout of at most 0.1 s. A Valkey that is down when a cache starts is now found by the first command, and the tier tries again after the cooldown.
- The RAG lookup pause uses a pybreaker breaker in place of the hand-written one. Three transient failures in a row pause the lookups for 60 s, as before. The first lookup after the pause is a probe, and the other lookups wait for its result, as before. A probe that fails pauses the lookups for 60 s more, with one more warning.
- `TieredCache` that the issue names was deleted by #1113, so no code in `src` builds it. The library symbol store is the cache that still sent each command during an outage, so it goes through the tier in its place.
- The change makes a cache come back after a Valkey outage, and it changes the requests that a cache sends during an outage, which a person can see. So it carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `valkey-cache-tier`: the Valkey tier of the caches: how a Valkey outage turns it off for a cooldown, and how a trial after the cooldown turns it on again.
- `rag-lookup-pause`: the pause of RAG lookups after transient failures, and the probe that resumes them.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/valkey/cache.py` (new), `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/security/vulnerability_lookup.py`, `src/devops_cli/ai/rag/library_store.py`, `src/devops_cli/ai/rag/investigator.py`, `src/devops_cli/config/defaults.py` (two new defaults, with their basis), `pyproject.toml` and `uv.lock`.
- Tests: `tests/test_valkey_cache_tier.py` (new), `tests/test_rag_embeddings.py`, `tests/test_security_threat_intel.py`, `tests/test_library_vector_tier.py`, `tests/test_rag_investigator.py`, `tests/test_qdrant_timeout_setting.py`, `tests/test_builtin_tools.py`, and the swallowed-failure ceilings in `tests/fixtures/swallowed_failures_ceilings.json`.
- The failover reset of the gateway is #1986, and the batch size of the engine is #2072. This change does not touch them.

## Feasibility

- On main at 1b257714, `grep -rn "self._valkey = None" src` found the five lines that the issue names: `src/devops_cli/ai/rag/embeddings.py:584` and `:599`, and `src/devops_cli/security/vulnerability_lookup.py:460`, `:481` and `:497`. `EmbeddingsEngine._init_valkey` probed Valkey with a timeout of at most 0.1 s and returned no client when the probe failed.
- `src/devops_cli/cache/` does not exist: #1113 deleted the package with `TieredCache`, and no code in `src` builds a `TieredCache` (owner's comment on #596, 2026-10-03). `LibraryVectorStore.lookup_symbol` and `_cache_symbol_in_valkey` in `src/devops_cli/ai/rag/library_store.py` sent each command to Valkey and logged each failure at debug level, which is the behavior that the issue gives for `TieredCache`.
- The hand-written breaker of the RAG lookup pause was `_circuit_breaker_opened_at`, `_consecutive_transient_failures`, `_record_success`, `_record_transient_failure`, `_is_breaker_active` and `_is_probe_required` in `src/devops_cli/ai/rag/investigator.py`.
- pybreaker 1.4.1 on CPython 3.14.7: a scratch probe drove a breaker from closed to open, kept it open in the cooldown, moved it to half-open and closed at the first call after the cooldown, and opened it again after a failed trial. time-machine moved the cooldown, because pybreaker reads `datetime.now(UTC)`. The probe also showed that `CircuitBreaker.calling()` runs its block outside the lock of the breaker, so the lookups of a closed breaker run at the same time, and that `call()` holds the lock while the command runs (pybreaker issue 55, open since 2021).
- The shared Valkey fake makes an outage: a fakeredis `FakeServer` with `connected = False` fails each command, and `ValkeyClient` raises `ValkeyConnectionError` for it.
- On the base, the 11 new and changed tests fail: the tier tests cannot import the tier, the cache tests do not get the value from Valkey after the cooldown, the two RAG pause tests stay paused after the cooldown because the base read `time.monotonic`, which the `clock` fixture does not move, and the two wiring tests find no `symbol_cache`.

## Existing Tool Considered

pybreaker is used. The three libraries that the issue asks to compare, checked on 2026-10-24 on PyPI and GitHub:

| Library | Last release | Last commit | Open issues and pull requests | Python 3.14 | Licence | Half-open and cooldown |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| pybreaker | 1.4.1, 2025-09-21 | 2026-09-25 | 17 issues, 11 pull requests; 698 stars | Pure Python, `requires-python >=3.9`, ships `py.typed`; runs on 3.14.7 here | BSD-3-Clause | Yes: `reset_timeout`, half-open with `success_threshold`, `exclude`, listeners, a lock |
| purgatory | 3.0.1, 2024-11-02 | 2024-11-07 | 0 issues, 3 pull requests; 5 stars | Pure Python, `requires-python >=3.9` | MIT | Yes: `ttl`, half-opened state |
| circuitbreaker | 2.1.3, 2025-03-31 | 2025-03-31 | 10 issues, 2 pull requests; 522 stars | Classifiers stop at Python 3.10 | BSD-3-Clause | Yes: `recovery_timeout`, half-open; no lock, and it reads `time.monotonic` by name, which time-machine does not move |

- pybreaker is the maintained one: it had a release in the last 13 months and commits in the last month, and it has the most users. Its breaker is thread-safe, and its listeners give the warning of the RAG pause and the debug record of the tier without code that copies its state.
- purgatory was rejected: it has almost no users and no commit for nearly two years.
- circuitbreaker was rejected: no commit for 19 months, classifiers that stop at Python 3.10, a failure count with no lock, and a cooldown that a test can move only by a patch of its module.
- A breaker written by hand was not considered: a maintained library covers the need.

`uv add pybreaker==1.4.1` adds the dependency, with no dependency of its own. pybreaker imports redis and tornado when they are installed, for storage and coroutine support that devops-cli does not use; the wheel of devops-cli installs neither. The two modules that import pybreaker load only when a cache or a RAG lookup runs, so no `--help` loads it.

The change deletes the five `self._valkey = None` lines, `EmbeddingsEngine._init_valkey` with its probe client, the hand-written breaker of the RAG pause (`_circuit_breaker_opened_at`, `_consecutive_transient_failures`, `_STATE_LOCK`, `_record_success`, `_record_transient_failure`, `_is_breaker_active`, `_is_probe_required`, and the `_CIRCUIT_BREAKER_FAILURES` and `_CIRCUIT_BREAKER_PAUSE_SECONDS` aliases), six blind `except Exception` blocks in the caches (two in each), and the tests that pinned the one-way switch: `test_cloudflare_radar_valkey_connection_error_disables_valkey`, `test_cloudflare_radar_valkey_offline_fallback`, `test_valkey_offline_does_not_stop_embedding`, `test_init_valkey_fast_probe_offline` and `test_init_valkey_probes_quickly_then_serves_with_the_configured_timeout`.
