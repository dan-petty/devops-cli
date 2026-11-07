# Proposal

## Why

Issue #3901 is item 3 of the Fit note of #1333, which is a part of #1307. The tests of `main.py`, `entry.py` and `dry_run/` reach into the code under test. They patch `devops_cli.main._delegate` 7 times, `devops_cli.main.app` 4 times, `devops_cli.entry.main` 1 time and `devops_cli.dry_run.decorator.render_dry_run_result` 4 times. They call the private `main._delegate` and `core.cli._handle_lazy_proxy_dry_run`, and they import the private `_MAX_DRY_RUN_*` constants. ADR 0007 and `docs/TESTING.md` say that a test patches no `devops_cli` name and imports no private name. The `cli` fixture, the process fake and the hermetic floor already exist, but these tests do not use them. Three of the files are named after a refactor or after an implementation detail (`test_consolidation_dry_run_decorator`, `test_fast_dispatch`, `test_main_dry_run` in `tests/core/`), and one test, `test_main_helpers_and_entrypoint`, is a catch-all.

## What Changes

- `tests/core/test_main_dry_run.py` becomes `tests/commands/test_global_dry_run.py` and `tests/commands/test_passthrough_arguments.py`. A CLI test sits in `tests/commands/`.
  - Every case runs a real command through the `cli` fixture: `tf apply`, `tf destroy`, `uv`, `ci`, `k8s configure-urls` and `sandbox deploy`. The process fake shows that a dry run starts no program and that a run without the flag starts `tofu apply`.
  - The cases that need a command with no dry-run class use the stub module `tests/support/dry_run_stub.py`. A fixture registers it on the root app as `stub` with the public `add_typer`, and removes it after the test.
  - The stub commands print a line when they run, so a test sees that a dry run prints only the preview.
  - The module-level `CliRunner()` and the 7 patches of `_delegate` go. The test of the help flag after `--` runs `devops uv run -- pytest --help` with the process fake answering exit code 3, in place of the call of `_delegate` with a module put in `sys.modules`.
- `tests/dry_run/test_fast_dispatch.py` is split by behavior:
  - `tests/commands/test_entry_point.py`: version, help, the process arguments, the leading `devops` word of an argv, shell completion, and the dry-run state after a run. The tests call `entry.main` and `main.main_entry` and run the real app. They read the exit code, the output and the state of the process fake.
  - `tests/dry_run/test_dry_run_state.py`: the dry-run flag in an argv, the state, `format_command`, and the printed result as a syrupy snapshot.
  - The catch-all `test_main_helpers_and_entrypoint` and the 4 patches of `main.app` go.
  - `test_dry_run_getattr` and `test_core_dry_run_exports` go. The package has no `__getattr__` now, so the first one checked nothing, and `tests/core/test_public_export_surface.py` holds every name of `__all__` of every package to a definition.
- `tests/dry_run/test_consolidation_dry_run_decorator.py` becomes `tests/dry_run/test_dry_run_command_decorator.py` and `tests/dry_run/test_dry_run_result_bounds.py`.
  - The decorator tests read the JSON that the decorator prints. They no longer patch `render_dry_run_result`.
  - A detail value that cannot be serialized makes the print fail, so the test of the restored state needs no patch. A detail value that records the state during its serialization shows that the state is on while the result prints.
  - The bounds of the details are literal numbers in the test, and no private constant is imported.
- `tests/invariants/test_hermetic_floor.py` names the new file of the decorator tests in its list of floor-reset fixtures.
- Not changed: `tests/invariants/test_dry_run_class_ratchet.py` (it patches `_delegate` too, and belongs to the dry-run class item), and every file of `src/`. This change alters no behavior a consumer observes. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request.

## Impact

- Removed: `tests/core/test_main_dry_run.py`, `tests/dry_run/test_fast_dispatch.py`, `tests/dry_run/test_consolidation_dry_run_decorator.py`.
- Added: `tests/commands/test_global_dry_run.py`, `tests/commands/test_passthrough_arguments.py`, `tests/commands/test_entry_point.py`, `tests/dry_run/test_dry_run_state.py`, `tests/dry_run/test_dry_run_command_decorator.py`, `tests/dry_run/test_dry_run_result_bounds.py` and one snapshot file.
- Changed: `tests/support/dry_run_stub.py` (each command prints a line) and `tests/invariants/test_hermetic_floor.py` (one file name).

## Feasibility

Checked on `origin/main` 6d105c20, 2026-11-07. The premise of the item holds, with counts that differ from the Fit note, so each claim was counted again.

- `git grep -n -F "_delegate" -- tests/core/test_main_dry_run.py` found 7 patches of `main._delegate` and one private import of `_handle_lazy_proxy_dry_run`. `tests/dry_run/test_fast_dispatch.py` patches `main.app` 4 times and `entry.main` 1 time. The decorator tests patch `render_dry_run_result` 4 times. The Fit note counted 9 and 4 on an older tree.
- The item needs no new fake. Real commands run in process through the `cli` fixture, and every program they would start goes through the process runner, which `process_fake` answers. A probe on the base showed this for the cases of the old tests: `tf apply` starts `tofu apply` and a dry run starts nothing, `uv run -- pytest --help` starts `uv` and keeps the exit code of the child, `sandbox deploy --dry-run` prints the plan with no Docker engine, and `k8s push-secrets --dry-run` and `uv run -- pytest --dry-run` give the two states that the old test of the root callback expected, `(False, True)` and `(False, False)`.
- The test that checks the state during the print needs a hook inside the render. No patch is needed: a Pydantic model as a detail value runs its serializer during `model_dump_json`, and the serializer reads `is_dry_run()`. An object that Pydantic cannot serialize raises `PydanticSerializationError` there, which tests the restored state.
- Shell completion is tested with `_DEVOPS_COMPLETE=source_zsh`, which prints the zsh completion script. The old test only checked that a mocked app was called.
- Mutation check: 14 changes of the product code were tried one by one in `main.py`, `entry.py`, `dry_run/decorator.py`, `dry_run/models.py`, `dry_run/state.py` and `core/command_resolver.py`, and the migrated tests failed for 13 of them: the environment variable ignored, a help flag after `--` counted as a help query, the flag latched for later commands, the invocation never marked, the absolute `devops` word kept in the argv, the Typer completion variable not detected, the decorator not turning the state on, not restoring it, and running the command, a changed string bound and a changed depth bound, the separator ignored in the argv scan, the class `no-external-request` not run, and the flag appended after `--`.
- One mutant survives: removing `if requested: set_dry_run(True)` in `entry.main`. The root callback of `main.py` sets the same state again before any command runs, so no run that reaches a command shows the difference. The old test saw it only because it replaced the app with a mock. The line stays: this change writes no compensating test and changes no code of `src/`.
- Not built as written: the item 3 of the earlier numbering (git on real git) is stale. ADR 0007 fakes git, and #1333 holds the evidence.

## Existing Tool Considered

Not applicable: this change builds nothing. It uses pytest, Typer's `CliRunner` through the shared `cli` fixture, syrupy, Pydantic and the shared `process_fake`. It deletes 3 test files and 16 patches of `devops_cli` names from the tests.
