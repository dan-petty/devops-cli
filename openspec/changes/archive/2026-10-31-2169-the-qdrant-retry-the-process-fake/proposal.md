# Proposal

## Why

Issue #2169 identifies that 24 test bodies, the Qdrant retry, and the process fake wait in real wall-clock time, making tests slow and load-dependent. docs/TESTING.md requires that waiting goes through the clock fixture or an event, and that no test bounds or spends wall-clock time it does not need.

## What Changes

- The Qdrant retry in src/devops_cli/ai/rag/qdrant.py uses tenacity's sleep parameter supplied by the clock seam instead of time.sleep.
- The process fake's delay in tests/support/fakes/process.py advances the clock fixture's time instead of calling time.sleep or asyncio.sleep.
- Twenty-four test bodies replace time.sleep and asyncio.sleep calls with event waits or the clock fixture.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rag-lookup-pause`: qdrant-retry-wait-uses-clock-seam

## Impact

- Code: `src/devops_cli/ai/rag/qdrant.py`
- Tests: `tests/test_rag_multi_project_indexer.py`, `tests/support/fakes/process.py`, `tests/test_ai_client_network.py`, `tests/test_ai_client_security.py`, `tests/test_ai_review_pool.py`, `tests/test_argo_gitops.py`, `tests/test_devcontainer.py`, `tests/test_github_session.py`, `tests/test_http_egress.py`, `tests/test_k8s_service.py`, `tests/test_ollama_dynamic_leasing.py`, `tests/test_pydantic_agent.py`, `tests/test_rag_investigator.py`, `tests/test_rag_query_telemetry.py`, `tests/test_response_cache.py`, `tests/test_review_adjudication.py`, `tests/test_telemetry.py`, `tests/test_telemetry_collector_export.py`, `tests/test_watchers.py`, `tests/test_memory_profiler.py`, `tests/test_server_service.py`

## Feasibility

- The context confirms _record_retry exists at src/devops_cli/ai/rag/qdrant.py:128, called at line 339. The issue cites line 157 at commit b170358e; the function is present in both.
- The context shows tests/support/fakes/clock.py is referenced by .ast-grep/rules/test-elapsed-upper-bound.yml and its rule test, confirming the clock fixture exists.
- The context shows tests/support/waits.py is referenced in docs/TESTING.md for thread handoff waits.
- First checks: run `rg -n 'time\.sleep' src/devops_cli/ai/rag/qdrant.py tests/support/fakes/process.py` to confirm the current state, then `uv run devops ci test tests/test_rag_multi_project_indexer.py` to confirm the test passes before the change.

## Existing Tool Considered

tenacity (already in the project) provides the retry with a sleep parameter. tests/support/fakes/clock.py provides the clock fixture. tests/support/waits.py provides THREAD_HANDOFF_BOUND_SECONDS and wait_until for event-based waits.
