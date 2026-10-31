# Proposal

## Why

Issue #1328 delivers Phase E review package test refactoring for `ai/review/` and `review/` under parent issue #1307. Product code in `src/devops_cli/ai/review/pipeline.py` currently contains mock-detection code (`NonCallableMock`), which violates architectural test-isolation standards and AGENTS.md rule 2. Furthermore, `src/devops_cli/ai/review/runner.py` exports and uses an internal alias `_run_subprocess` that test suites monkeypatch directly rather than testing through process edge seams.

## What Changes

- Remove `NonCallableMock` check in `_is_scannable_manifest` in `src/devops_cli/ai/review/pipeline.py`.
- Add an architectural invariant in `tests/invariants/test_source_tree.py` preventing any import of `unittest.mock` within `src/`.
- Replace `_run_subprocess` with canonical `run_subprocess` in `src/devops_cli/ai/review/runner.py`.
- Refactor `tests/ai/review/test_review_runner.py` and `tests/ai/review/test_review_symbol_delta.py` to route git subprocess execution through `process_fake: ProcessFake` instead of monkeypatching `_run_subprocess`.
- Remove mock detection assertions from `tests/ai/review/test_review_static_analyzers.py`.
- This change alters test and internal plumbing without changing consumer-facing CLI syntax or commands, so it sets `skip_specs: true`.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/ai/review/pipeline.py`: `_is_scannable_manifest` checks manifest file existence and validity without mock inspections.
- `src/devops_cli/ai/review/runner.py`: uses canonical `run_subprocess` directly.
- `tests/invariants/test_source_tree.py`: enforces that `src/` never imports `unittest.mock`.
- `tests/ai/review/`: tests use `process_fake` for subprocess execution and avoid internal monkeypatching of `_run_subprocess`.

## Feasibility

- The `ProcessFake` fixture (`tests/support/fakes/process.py`) intercepts `run_subprocess` calls across the process runner seam.
- Running `uv run pytest tests/ai/review/test_review_runner.py tests/ai/review/test_review_symbol_delta.py` confirms that git commands route cleanly to `process_fake`.
- `uv run pytest tests/invariants/test_source_tree.py -k test_no_mock_imports_in_src` confirms zero mock imports remain in `src/`.

## Existing Tool Considered

`ProcessFake` provides deterministic subprocess answers for git commands. No new double or custom monkeypatch helper is needed.
