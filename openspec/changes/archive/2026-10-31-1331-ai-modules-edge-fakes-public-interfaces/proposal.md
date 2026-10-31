# Proposal

## Why

Issue #1331 delivers Phase E test migration for AI modules under parent issue #1307. Several AI modules contain legacy mock fallbacks in production code, including `backend_type` in `src/devops_cli/ai/client/unified.py` returning `"mock"`. Domain logic such as gateway probe checks, benchmark execution, and baseline lookups reside in command modules instead of domain packages. Furthermore, duplicate test files exist (`tests/ai/test_ai_repomap.py` and `tests/ai/test_repomap.py`), and test suites contain monkeypatches of internal functions and private imports.

## What Changes

- Remove the `"mock"` fallback in `backend_type` in `src/devops_cli/ai/client/unified.py`.
- Move gateway health probe logic from `src/devops_cli/commands/ai_gateway.py` to `src/devops_cli/ai/gateway.py` behind a public function `probe_gateway_liveliness_and_models`.
- Move baseline run lookup logic from `src/devops_cli/commands/ai_runs.py` to `src/devops_cli/ai/run_store.py` behind a public function `find_baseline_run`.
- Move benchmark runner execution from `src/devops_cli/commands/benchmark.py` to `src/devops_cli/ai/benchmark/` behind public functions.
- Merge `tests/ai/test_ai_repomap.py` into `tests/ai/test_repomap.py` and delete the redundant file.
- Clean review and gateway benchmark test cases from `tests/ai/test_run_store.py` so it tests only run-store behavior.
- Clean monkeypatches and private imports across migrated AI test suites.
- This change alters test and internal plumbing without changing consumer-facing CLI syntax or commands, so it sets `skip_specs: true`.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/ai/client/unified.py`: `backend_type` resolves the configured provider name without falling back to `"mock"`.
- `src/devops_cli/ai/gateway.py`: exports `probe_gateway_liveliness_and_models`.
- `src/devops_cli/ai/run_store.py`: exports `find_baseline_run`.
- `src/devops_cli/ai/benchmark/`: exports benchmark runner functions.
- `tests/ai/`: repomap and run store tests test public interfaces and avoid internal patches.

## Feasibility

- Running `uv run pytest tests/ai/client/test_ai_client_providers_and_embeddings.py` verifies the updated `backend_type` behavior.
- Running `uv run pytest tests/ai/test_repomap.py` verifies combined repomap functionality without `test_ai_repomap.py`.
- Running `uv run pytest tests/ai/test_run_store.py` verifies run-store isolation.

## Existing Tool Considered

Standard fixtures (`cli`, `process_fake`, `model_fake`) and existing domain modules cover the requirements. No new double is required.
