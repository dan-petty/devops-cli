# Proposal

## Why

Issue #1313: The devops-cli test suite has 553 test files sitting directly in `tests/`. The layout is flat and does not mirror the package hierarchy under `src/devops_cli/`. Tests are difficult to locate, and the root `tests/conftest.py` has accumulated domain-specific fixtures beyond the hermetic floor. A layout ratchet in `tests/invariants/test_source_tree.py` prevents new flat test files from regressing the organization.

## What Changes

- Move test files from `tests/` into mirror directories matching `src/devops_cli/` packages at full depth or into `tests/invariants/` for tests of committed repo files, with no edits to test file bodies (`R100` renames).
- Ensure each test directory contains an empty `__init__.py`.
- Split non-floor domain fixtures from the root `tests/conftest.py` into `tests/support/` modules (`cli`, `config`, `model_fake`, `process_fake`, `docker_engine`, `valkey`, `qdrant`, `embedder`, `git`, `spend_ledger`, `tracer`, `review_sessions`, `roadmap`, `web`), keeping only the hermetic floor in `tests/conftest.py`.
- Add a layout ratchet in `tests/invariants/test_source_tree.py` enforcing that every `test_*.py` resides in a mirror package directory or under `tests/invariants/`, with ceilings set to 0.
- Update `detect-private-key` in `.pre-commit-config.yaml` to point to the new paths of `test_review_prompt_guardrails.py` and `test_security_gitleaks.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Structure: `tests/` reorganized to mirror `src/devops_cli/` packages.
- Root test fixtures: `tests/conftest.py` holds only hermetic floor.
- Configuration: `.pre-commit-config.yaml` hook exclusions updated.

## Feasibility

- The premise is confirmed: #1312 has closed and enabled tests to resolve repository root and fixtures from any depth without `__file__` path depth navigation.
- `tests.support.bootstrap` automatically registers modules under `tests.support` as pytest plugins, enabling moved fixtures in `tests/support/` to be globally accessible.
- Moving files with `git mv` preserves complete git history and produces clean `R100` renames.
- The test collection set remains identical before and after the move when paths are normalized.

## Existing Tool Considered

Git rename tracking (`git mv`) and pytest's standard plugin registration mechanism are used. No external tool is required.
