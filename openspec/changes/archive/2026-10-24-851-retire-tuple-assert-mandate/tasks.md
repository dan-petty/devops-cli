# Tasks

## 1. Presence Constants and Invariant Specification

- [x] Write failing test `test_opaque_and_presence_assertions_fixtures` asserting file and line for each acceptance fixture in `tests/test_architectural_invariants.py`. `uv run pytest tests/test_architectural_invariants.py -k "test_opaque_and_presence_assertions_fixtures"`.
- [x] Define `CONST_PRESENCE_CHECK_NAMES` in `src/devops_cli/config/constants.py` and implement `_opaque_or_presence_assertions` in `tests/test_architectural_invariants.py`. `uv run pytest tests/test_architectural_invariants.py -k "test_opaque_and_presence_assertions_fixtures"`.
- [x] Connect `_opaque_or_presence_assertions` into `test_no_test_certifies_a_failure_without_checking_it`. `uv run pytest tests/test_architectural_invariants.py -k "test_no_test_certifies_a_failure_without_checking_it"`.
- [x] Sync CLI documentation. `uv run devops docs generate --sync-readme`.

## 2. Ruff PT018 Rule and Composite Assertions

- [x] Select `PT018` in `pyproject.toml` and add `PT018` to `CONST_TEST_ASSERTION_LINT_RULES` in `src/devops_cli/config/constants.py`. `uv run pytest tests/test_architectural_invariants.py -k "test_no_test_certifies_a_failure_without_checking_it"`.
- [x] Rewrite compound assertions across `tests/` flagged by `PT018` into individual assertions. `uv run ruff check --select PT018`.
- [x] Sync CLI documentation. `uv run devops docs generate --sync-readme`.

## 3. Re-export and Presence-Only Test Rewrites

- [x] Rewrite re-export tests to assert identity with defining objects using `is`. `uv run pytest tests/test_fast_dispatch.py tests/test_docker_cosign.py tests/test_pydantic_ai_ollama.py tests/test_ai_init.py`.
- [x] Rewrite remaining presence-only test functions and bare truthiness assertions to assert concrete values. `uv run pytest tests/test_ci.py tests/test_coverage_index.py tests/test_language_catalogs.py tests/test_trace_propagation.py`.
- [x] Sync CLI documentation. `uv run devops docs generate --sync-readme`.

## 4. Opaque Tuple Assert Rewrites and Invariant Verification

- [x] Rewrite opaque tuple assertions across `tests/` to eliminate presence checks compared with boolean literals. `uv run pytest tests/test_architectural_invariants.py -k "test_no_test_certifies_a_failure_without_checking_it"`.
- [x] Run full architectural invariant test suite and verify duration overhead is under one second. `uv run pytest tests/test_architectural_invariants.py --durations=10`.
- [x] Run the complete CI gate. `uv run devops ci`.
- [x] Sync CLI documentation. `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
