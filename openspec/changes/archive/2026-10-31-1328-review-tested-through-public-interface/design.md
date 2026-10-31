# Design

## Context

See proposal.md for motivation and scope (#1328).
The review pipeline (`src/devops_cli/ai/review/pipeline.py`) contains a `NonCallableMock` inspection inside `_is_scannable_manifest`.
The review runner (`src/devops_cli/ai/review/runner.py`) exports `run_subprocess as _run_subprocess`, which tests patch instead of using `process_fake`.

## Technical Design

### 1. Remove Mock Inspection from `_is_scannable_manifest`
- Update `_is_scannable_manifest(path: Path)` to return `False` when `not path.exists()`.
- Add invariant test in `tests/invariants/test_source_tree.py` ensuring `unittest.mock` is never imported under `src/`.
- Remove the mock patch test assertion in `tests/ai/review/test_review_static_analyzers.py`.

### 2. Route Review Runner Subprocesses to Canonical `run_subprocess`
- In `src/devops_cli/ai/review/runner.py`, import and call `run_subprocess` directly.
- In `tests/ai/review/test_review_runner.py` and `tests/ai/review/test_review_symbol_delta.py`, use the `process_fake` fixture to script process results.

## Rejected Alternatives

### 1. Keep `NonCallableMock` check for missing test fixtures
- **Evidence**: AGENTS.md rule 2 and ADR 0005 strictly forbid product code detecting tests or inspecting mock objects.

### 2. Retain `_run_subprocess` alias in `runner.py`
- **Evidence**: AGENTS.md rule 1 and issue #1307 require tests to double external edges via shared seams rather than patching internal aliases.
