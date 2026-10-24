# Tasks

## 1. One circuit breaker guards the Valkey cache tier

- [x] 1.1 Write `test_a_valkey_outage_turns_the_cache_tier_off_until_a_trial_after_the_cooldown`, `test_a_failed_trial_turns_the_cache_tier_off_for_one_more_cooldown` and `test_a_reply_error_leaves_the_cache_tier_on` in the new `tests/test_valkey_cache_tier.py`, through the shared Valkey fake and the `clock` fixture, and verify that `uv run devops ci test tests/test_valkey_cache_tier.py` fails on the base
- [x] 1.2 Add `pybreaker==1.4.1` with `uv add`, add `DEFAULT_VALKEY_CACHE_BREAKER_FAILURES` and `DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS` to `src/devops_cli/config/defaults.py` with the basis of each value, add `ValkeyCacheTier` and `configured_cache_tier` in `src/devops_cli/valkey/cache.py`, and verify that `uv run devops ci test tests/test_valkey_cache_tier.py` passes

## 2. The caches read and write through the tier

- [x] 2.1 Write `test_a_valkey_outage_turns_the_embedding_l2_cache_off_for_a_cooldown` and `test_an_engine_whose_valkey_refuses_embeds_and_dials_it_once_in_each_cooldown` in `tests/test_rag_embeddings.py`, `test_a_valkey_outage_turns_the_threat_intel_l2_cache_off_for_a_cooldown` and `test_a_corrupt_threat_intel_entry_is_a_miss_and_keeps_the_l2_cache_on` in `tests/test_security_threat_intel.py`, and `test_a_valkey_outage_turns_the_symbol_cache_off_for_a_cooldown` in `tests/test_library_vector_tier.py`, and verify that `uv run devops ci test tests/test_rag_embeddings.py tests/test_security_threat_intel.py tests/test_library_vector_tier.py` fails on the base
- [x] 2.2 Route `EmbeddingsEngine`, `CloudflareRadarClient` and `LibraryVectorStore` through `ValkeyCacheTier`, delete every `self._valkey = None`, and verify that `uv run devops ci test tests/test_rag_embeddings.py tests/test_security_threat_intel.py tests/test_library_vector_tier.py` passes
- [x] 2.3 Delete `EmbeddingsEngine._init_valkey` with its start probe, delete the tests that pinned the one-way switch and the probe (`test_cloudflare_radar_valkey_connection_error_disables_valkey`, `test_cloudflare_radar_valkey_offline_fallback`, `test_valkey_offline_does_not_stop_embedding`, `test_init_valkey_fast_probe_offline`, `test_init_valkey_probes_quickly_then_serves_with_the_configured_timeout`), remove the patches of `_init_valkey` from `tests/test_qdrant_timeout_setting.py` and `tests/test_builtin_tools.py`, and verify that `uv run devops ci test tests/test_qdrant_timeout_setting.py tests/test_builtin_tools.py` passes

## 3. The RAG lookup pause uses the same library

- [x] 3.1 Move `test_circuit_breaker_pause_and_resume` in `tests/test_rag_investigator.py` from a patched `time.monotonic` to the `clock` fixture, write `test_a_failed_probe_pauses_rag_lookups_for_60_seconds_more`, and verify that `uv run devops ci test tests/test_rag_investigator.py` fails on the base
- [x] 3.2 Replace the hand-written breaker of `src/devops_cli/ai/rag/investigator.py` with a pybreaker breaker, its storage and a listener for the pause warning, and verify that `uv run devops ci test tests/test_rag_investigator.py` passes

## 4. Checks and documents

- [x] 4.1 Lower the swallowed-failure ceilings with `uv run python -m tests.test_swallowed_failures_ratchet --lower`, and verify that `uv run devops ci test tests/test_swallowed_failures_ratchet.py tests/test_architectural_invariants.py tests/test_cli_startup_imports.py` passes
- [x] 4.2 Say in `src/devops_cli/ai/knowledge_base/devops_cli/tasks/rag_context_indexing.md` that a probe that fails pauses the lookups again, verify that `uv run ruff check`, `uv run ruff format --check` and `uv run mypy` pass on the changed files, regenerate the docs with `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- One Valkey client and one breaker for each process, with a short connect timeout, stay with #1992. This change removes the start probe of the engine and its literal 0.1 s timeout, which #1992 also names.
- Pending a person: stop the Valkey of the cluster during `devops ai rag index` on a repository, start it again, and read the debug log: the tier changes from closed to open, and after 60 s from half-open to closed, and the hits of `devops_cli_embedding_valkey_hits_total` come back.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
