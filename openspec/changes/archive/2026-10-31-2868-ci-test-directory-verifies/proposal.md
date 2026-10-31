# Proposal

## Why

#2868 reports that `devops ci test <directory>` verifies nothing and exits 0. `uv run devops ci test tests/invariants` prints `No source or test files supplied; nothing to verify.` and exits 0, while the 416 tests of that directory never run. A green exit must mean that a test ran. The plan-only run of `ci.yml` (#2860) hit this and runs `uv run pytest tests/invariants` instead.

## What Changes

- `devops ci test` expands a directory argument before it selects tests. A directory under `tests/` gives the test modules (`test_*.py`) inside it, at any depth. A directory under `src/` gives the Python modules inside it, which the command maps to tests as it maps a file.
- `devops ci test` refuses a directory that gives no module, and a directory outside `src/` and `tests/`. It exits 1 with an error that names the directory, and starts no pytest.
- `devops ci test` refuses a path that does not exist. It exits 1 with an error that names the path, and starts no pytest, whatever `--fallback` says. A mistyped or renamed directory must not give a green exit. A trigger file that is gone, such as a deleted `conftest.py`, still forces the full run, as before.
- A file argument that exists keeps its behavior. A file that maps to no test, such as `README.md`, still exits 0 with the note that nothing is to verify: `test_cli_exits_cleanly_for_documentation_only_changes` requires it.
- The step `Plan-Only Invariant Tests` of `.github/workflows/ci.yml` runs `uv run devops ci test tests/invariants`, and the comment that cites #2868 goes.
- The help text of the `paths` argument, `docs/TESTING.md` and `docs/SDLC.md` name the directory rule.
- The command and its error are observable, so the change carries a spec delta in the new capability `ci-test-selection`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ci-test-selection`: How `devops ci test` turns its path arguments into the test modules that pytest runs, and when it refuses a path.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Tests: `tests/commands/test_test_selection.py`, `tests/invariants/test_workflow_contracts.py`.
- Workflow: `.github/workflows/ci.yml`.
- Documents: `docs/TESTING.md`, `docs/SDLC.md`, and the generated command reference.

## Feasibility

Checked on 2026-10-31 on the base `origin/main` (00796a4a) with the real command.

- `uv run devops ci test tests/invariants` and `uv run devops ci test tests/invariants/` print `No source or test files supplied; nothing to verify.` and exit 0. `uv run pytest tests/invariants -n 0 -q` runs 416 tests in 72 s and passes. So the directory holds tests that the command skips.
- The cause is in `_resolve_test_targets` and `_map_changed_paths` of `src/devops_cli/commands/ci.py`. `_map_test_tree_path` accepts a path only when `is_test_module(path)` is true and the path is a file. A directory is neither, so it maps to no test and no unmapped source. Then `if not unmapped_sources and not mapped_sources` prints `no_testable_files` and returns `[]`, and `test` returns with exit 0.
- Pytest is not the cause. `_run` returns `code == 0`, so pytest exit status 5 (no test collected) already fails the command. No run starts here, so no status exists to read.
- The failure is not specific to `tests/invariants`. Any directory, a missing path or a file of another kind takes the same branch. A file that maps to no test must keep it: `test_cli_exits_cleanly_for_documentation_only_changes` needs exit 0 for `README.md`. On review, `uv run devops ci test tests/invariantz` also exited 0 with nothing run, so a missing path is refused too.
- `ci.yml` at base runs `uv run pytest tests/invariants` for the plan-only path. That run executes the tests: the step has no `|| true` and takes the exit status of pytest. The comment on that step cites #2868 as the reason it does not use `devops ci test`.

## Existing Tool Considered

Pytest accepts a directory and collects it, but `devops ci test` must map source files to test modules, count modules to choose the worker count (`_narrowed_workers`) and shuffle them for `--repeat`. A directory handed to pytest as one target would count as one module and run serially, which took 72 s for `tests/invariants`. So the command expands the directory itself with `Path.rglob` from the standard library. No library covers the mapping of a directory to the modules of this repository. The change adds one small function to the existing selection code and deletes no internal code except the workaround in `ci.yml`.
