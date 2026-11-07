# Tasks

## 1. The tests of the global dry-run flag run real commands (test-only edits)

- [x] 1.1 Replace `tests/core/test_main_dry_run.py` with `tests/commands/test_global_dry_run.py` and `tests/commands/test_passthrough_arguments.py`: real commands through the `cli` fixture, the calls of `process_fake`, and the stub module registered on the root app by a fixture
  - Verification: `uv run devops ci test tests/commands/test_global_dry_run.py tests/commands/test_passthrough_arguments.py`
- [x] 1.2 Make each command of `tests/support/dry_run_stub.py` print a line when it runs, so a test sees that a dry run only prints the preview
  - Verification: `uv run devops ci test tests/commands/test_global_dry_run.py tests/invariants/test_dry_run_class_ratchet.py`

## 2. The tests of the entry point run the real app (test-only edits)

- [x] 2.1 Replace the entry-point tests of `tests/dry_run/test_fast_dispatch.py` with `tests/commands/test_entry_point.py`: version, help, the process arguments, the argv with and without the `devops` word, shell completion, and the dry-run state after a run
  - Verification: `uv run devops ci test tests/commands/test_entry_point.py`

## 3. The tests of the dry-run package use the public interface (test-only edits)

- [x] 3.1 Replace the state tests of `tests/dry_run/test_fast_dispatch.py` with `tests/dry_run/test_dry_run_state.py`, and make the printed result a syrupy snapshot
  - Verification: `uv run devops ci test tests/dry_run/test_dry_run_state.py`
- [x] 3.2 Replace `tests/dry_run/test_consolidation_dry_run_decorator.py` with `tests/dry_run/test_dry_run_command_decorator.py` and `tests/dry_run/test_dry_run_result_bounds.py`, with no patch and no private constant
  - Verification: `uv run devops ci test tests/dry_run`
- [x] 3.3 Name the new file of the decorator tests in the list of floor-reset fixtures of `tests/invariants/test_hermetic_floor.py`
  - Verification: `uv run devops ci test tests/invariants/test_hermetic_floor.py`

## 4. No patch and no old name remain (test-only edits)

- [x] 4.1 No test of this item patches a `devops_cli` name
  - Verification: `! git grep -n -F -e _delegate -e unittest.mock -e devops_cli.main.app -e devops_cli.entry.main -e devops_cli.dry_run.decorator.render_dry_run_result -- tests/commands/test_global_dry_run.py tests/commands/test_passthrough_arguments.py tests/commands/test_entry_point.py tests/dry_run`
- [x] 4.2 No file names the three old test files
  - Verification: `! git grep -n -F -e test_fast_dispatch -e test_main_dry_run -e test_consolidation_dry_run_decorator -- src tests docs README.md ARCHITECTURE.md SECURITY.md CONTRIBUTING.md .github k8s openspec/specs`

## 5. Archive

- [x] 5.1 Archive the change
  - Verification: `uv run devops openspec archive 3901-root-and-dry-run-tests-on-edge-fakes`

## Workflow follow-up

- The other items of #1333 move the tests of core, config, http, and exceptions, lang and models, remove the accommodations of `src/`, and delete dead code. `tests/invariants/test_dry_run_class_ratchet.py` still patches `main._delegate`. It belongs to the dry-run class item and to the reorganization item of #1333.
- The call `set_dry_run(True)` in `entry.main` has no effect that a run shows, since the root callback sets the state again. It is follow-up #3910.
