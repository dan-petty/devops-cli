# Tasks

## 1. Product code keeps no accommodation for these tests (refactor)

- [x] 1.1 Delete the two reads of `PYTEST_CURRENT_TEST`, `_current_run_subprocess`, `_ORIG_RUN_SUBPROCESS`, the `force` argument of `_clean_coverage_artifacts` and `_run_all_checks` from `commands/ci.py`
  - Verification: `! git grep -n -e PYTEST_CURRENT_TEST -e _current_run_subprocess -e _ORIG_RUN_SUBPROCESS -e 'def _run_all_checks(' -- src/`
- [x] 1.2 Time a check with the clock seam, add `gate_root_warnings` to `ci/diagnostics.py`, and move `directory_modules` and `shard_test_files` to `core/test_selection.py`
  - Verification: `uv run devops ci test tests/ci/test_ci_diagnostics.py tests/commands/test_ci_shard.py`

## 2. The tests of `devops ci` double only edges (refactor)

- [x] 2.1 Add `tests/support/ci_root.py` with `ci_root`, `ci_head` and `tracked_blobs`, and move the tests of `test_ci.py`, `test_ci_dry_run.py` and `test_ci_gate_admission.py` that start the gate into a root of their own
  - Verification: `uv run devops ci test tests/commands/test_ci.py tests/commands/test_ci_dry_run.py tests/ci/test_ci_gate_admission.py`
- [x] 2.2 Move `test_ci_shard.py` and `test_ci_build_index.py` to the process fake and the public shard functions
  - Verification: `uv run devops ci test tests/commands/test_ci_shard.py tests/commands/test_ci_build_index.py`
- [x] 2.3 Move `test_test_selection.py` to the process fake and `tracked_blobs`
  - Verification: `uv run devops ci test tests/commands/test_test_selection.py`
- [x] 2.4 Check that no patch of a `devops_cli` name is left in the five files
  - Verification: `! git grep -n -e 'setattr("devops_cli' -e 'patch("devops_cli' -e 'setattr(ci_module' -e 'patch.object(ci_module' -- tests/commands/test_ci.py tests/commands/test_ci_build_index.py tests/commands/test_ci_dry_run.py tests/commands/test_ci_shard.py tests/commands/test_test_selection.py`

## 3. The invariant bans the read, and the documents agree (refactor)

- [x] 3.1 Replace the ceiling of 2 on the reads of `PYTEST_CURRENT_TEST` with a ban, and say so in `docs/TESTING.md`
  - Verification: `uv run devops ci test tests/invariants/test_source_tree.py`
- [x] 3.2 Remove the stale change folder `1325-ci-commands-edge-fakes`
  - Verification: `uv run devops openspec check`

## 4. Archive

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 4087-ci-and-test-selection-command-tests-on-edge-fakes`
