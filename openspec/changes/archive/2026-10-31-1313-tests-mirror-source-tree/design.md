# Design

## Decisions

- **Pure rename without content changes**: Every test file keeps its content unchanged during the move, ensuring git tracks 100% pure renames (`R100`) and preserves `git log --follow` history.
- **Mirror directory structure at full depth**: Test files move to mirror directories of `src/devops_cli` based on AST import and patch ownership, matching the Phase E child issue specifications. Invariant tests move to `tests/invariants/`.
- **Hermetic floor in root conftest**: Root `tests/conftest.py` retains only process, network, and environment isolation fixtures and resets. Shared domain fixtures move to `tests/support/` where `tests.support.bootstrap` registers them.
- **Layout ratchet**: An invariant check in `tests/invariants/test_source_tree.py` counts non-mirror test files and test files in root `tests/`, bounded by a ceiling of 0.

## Rejected alternatives

- **Move test files package by package across separate PRs**: Rejected by owner decision (2026-10-07) because mixed moves and design changes make rebasing difficult and increase review complexity.
- **Edit test files during move**: Rejected by owner decision because changing contents breaks git rename detection (`R100`).
- **Store per-file ceiling tables for layout**: Rejected because placement is binary (mirror or invariants) and a single ceiling of 0 prevents merge conflicts.
