# Proposal: #1329

## Why

Issue #1329 migrates the `ai/rag/` and `ai/library/` tests onto shared edge fakes and moves RAG wiring into `ai/rag/`.
Earlier changes #3850, #3862 and #4002 delivered the RAG component wiring, migrated 25 test files to edge fakes, and moved library and command tests to CLI fixtures.
This change completes the remaining acceptance criteria of #1329: it makes the internal ingest functions public, removes private imports from `test_rag_ingest.py`, and replaces monkeypatch calls with edge fakes and runners.

## What Changes

- In `src/devops_cli/ai/rag/ingest.py`, expose repository ingest helpers as public functions: `resolve_repo_paths`, `read_repo_visibility`, `load_repo_state`, `cleanup_removed_repos` and `update_points_visibility`.
- In `tests/ai/rag/test_rag_ingest.py`:
  - Replace imports of private names with their public counterparts.
  - Remove monkeypatch calls that replace `ingest_repository` and `emit`. Use a failing `git_runner` and the `otlp` collector fixture instead.
  - Replace `MagicMock` instances with simple callable objects and fake Qdrant instances.

## Capabilities

No new capability is introduced. This change refactors tests and exposes helper functions.

## Impact

- `src/devops_cli/ai/rag/ingest.py`
- `tests/ai/rag/test_rag_ingest.py`
- No user-visible behavior or CLI contracts change.

## Feasibility

All 29 tests in `tests/ai/library/` and 347 tests in `tests/ai/rag/` pass on the current branch.
The `otlp` fake collector fixture records metric points for `RAG_INGEST_LAST_SUCCESS_TIMESTAMP`.
The `run_ingest_pass` function accepts `git_runner` and `gh_runner` parameters, allowing edge-level failure testing without monkeypatching product functions.

## Existing Tool Considered

The repository already provides `tests/support/fakes/otlp.py` and `tests/support/fakes/qdrant.py`.
No new third-party tool or library is required.
