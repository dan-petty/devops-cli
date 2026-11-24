# Tasks

## 1. Write one line per swallowed-failures problem

Kind: other. Reads: `tests/gate/swallowed_failures.py`, `tests/invariants/test_swallowed_failures_check.py`. Changes: `tests/gate/swallowed_failures.py`.

- [ ] 1.1 Add a function to `tests/gate/swallowed_failures.py` that returns one line for each problem: one line for each site of a file over its ceiling, one line for the count of that file, and one line for each file under its ceiling, with no embedded newline. Print each of these lines to standard error with the prefix `swallowed failures: ` in `main`, and return 1 when it wrote one. Keep `format_over_ceiling_error` and `format_under_ceiling_error` as the multi-line detail that `lower_ceilings` and `tests/invariants/test_swallowed_failures_check.py` read
  - Verification: `$ uv run devops ci --check --only swallowed-failures` passes

## 2. Write one physical line per start-up import problem

Kind: other. Reads: `tests/gate/startup_imports.py`. Changes: `tests/gate/startup_imports.py`.

- [ ] 2.1 Replace each newline of a problem of `tests/gate/startup_imports.py` with a space in `main`, so every problem of a probe becomes one physical line on standard error with the prefix `startup imports: `. Keep the probe lines of standard output, the probes themselves and the exit status 1 as they are
  - Verification: `$ uv run devops ci --check --only startup-imports` passes

## 3. Make a changed module under tests/gate need a proof

Kind: behavior. Reads: `src/devops_cli/ci/fail_to_pass.py`, `tests/ci/test_fail_to_pass.py`, `tests/ci/test_ci_durations.py`, `tests/commands/test_ci.py`, `tests/commands/test_ci_shard.py`. Changes: `src/devops_cli/ci/fail_to_pass.py`, `tests/ci/test_fail_to_pass.py`.
Adds: `is_gate_module`

- [ ] 3.1 Add the failing test `test_a_change_of_only_a_module_under_tests_gate_needs_a_proof` in `tests/ci/test_fail_to_pass.py`: a fix that touches only `tests/gate/ruff_config.py` gives `report.needs_proof` True and `report.changed_gate_modules` of `tests/gate/ruff_config.py`, where the staged code returns `needs_proof=False` from `src/devops_cli/ci/fail_to_pass.py:1027:if not changed.source_files and not changed.gate_checks:`
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` fails on the base
- [ ] 3.2 Add `is_gate_module` to `src/devops_cli/ci/fail_to_pass.py` for a `.py` module directly under `tests/gate/` other than `__init__.py`, and list those modules in a `gate_modules` field of `ChangedTests` in `changed_tests`. Add a `changed_gate_modules` field to `FailToPassReport` and set it in `run_fail_to_pass`. Widen both early returns: `needs_proof=False` only when the diff holds no source code, no gate check and no gate module, and the no-tests return only when the diff holds no test file, no gate check and no gate module, so `src/devops_cli/ci/fail_to_pass.py:1036:if not changed.test_files and not changed.gate_checks:` no longer stops a module-only change. Update `_replay_report` and the no-source cases of `tests/ci/test_fail_to_pass.py` for the new field
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` passes

## 4. Replay a changed gate module on the base and head trees

Kind: behavior. Reads: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/commands/ci.py`, `tests/ci/test_fail_to_pass.py`, `tests/ci/test_ci_durations.py`, `tests/commands/test_ci.py`, `tests/commands/test_ci_shard.py`. Changes: `src/devops_cli/ci/fail_to_pass.py`, `tests/ci/test_fail_to_pass.py`.
Adds: `gate_module_argv`, `gate_row_of_module`, `GateModuleRun`, `GateModuleReplay`, `_run_gate_module`, `_replay_gate_modules`

- [ ] 4.1 Add the failing test `test_a_base_only_problem_line_of_a_changed_gate_module_proves_the_fix` in `tests/ci/test_fail_to_pass.py`: for a fix that touches only `tests/gate/ruff_config.py`, the fake answers the run in the `gate_base` worktree with exit 1 and the line `ruff configuration: linter.mccabe.max_complexity: 5, not 10` on standard error and the run in the head worktree with exit 0 and no line, so `report.satisfied` is True; for a fix that touches only `tests/gate/runner.py`, the `refused` field of the module replay is True and `report.satisfied` is False
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` fails on the base
- [ ] 4.2 Add `gate_module_argv`, `gate_row_of_module`, `GateModuleRun`, `GateModuleReplay`, `_run_gate_module` and `_replay_gate_modules` to `src/devops_cli/ci/fail_to_pass.py`. `gate_row_of_module` imports `get_check_specs` inside the call and returns the row whose commands hold `CONST_GATE_ROW_SCRIPT` of the module, or `None`. `gate_module_argv` reuses `CONST_FAIL_TO_PASS_GATE_ROW_SCRIPT`. `_replay_gate_modules` runs each changed module in a `_plain_base_tree` worktree named `gate_base`, which keeps the base's own copy of the module, and in a `_head_tree` worktree named `gate_head`. The `proved` field of `GateModuleReplay` holds the base problem lines that no head line holds, and its `refused` field holds a module that no row runs, a run outside `CONST_FAIL_TO_PASS_GATE_ROW_EXIT_STATUSES` and a base run with no problem line. Add a `gate_modules` field to `FailToPassReport`, count a proved module and refuse a refused one in `satisfied`, and record the `gate_base` worktree in the fake of `tests/ci/test_fail_to_pass.py` beside `tests/ci/test_fail_to_pass.py:180:if dest.name == "tree":`
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` passes

## 5. Report the gate module line and update the plan cases

Kind: behavior. Reads: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/messages.py`, `tests/ci/test_fail_to_pass.py`, `tests/ci/test_ci_durations.py`, `tests/commands/test_ci.py`, `tests/commands/test_ci_shard.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_trace_subject.py`. Changes: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/messages.py`, `tests/ci/test_fail_to_pass.py`.
Adds: `_gate_module_lines`, `_gate_module_refusals`, `GATE_MODULE_REPLAY`, `EACH_GATE_MODULE_ROW`

- [ ] 5.1 Add the failing test `test_the_report_of_a_proved_gate_module_names_the_module_and_its_problem_line` in `tests/ci/test_fail_to_pass.py`: `format_fail_to_pass_report` names `tests/gate/ruff_config.py` and the exact problem line, and `plan_fail_to_pass` lists one module run for the merge base and one for the head
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` fails on the base
- [ ] 5.2 Add the messages of a proved module line, a problem line that only the head run writes, a base run with no problem line, a module that no row runs and a module run that could not run to `src/devops_cli/lang/en/messages.py`, and widen `fail_to_pass_no_source`, `fail_to_pass_deleted_checks` and `fail_to_pass_no_tests` from `tests/gate/*_checks/` to `tests/gate/`. Add `_gate_module_lines` and `_gate_module_refusals` to `src/devops_cli/ci/fail_to_pass.py`, use them in `format_fail_to_pass_report` and in `_unsatisfied_reasons`, whose first condition at `src/devops_cli/ci/fail_to_pass.py:1181:if not report.changed_test_files and not report.changed_gate_checks:` takes the changed gate modules too. Add `GATE_MODULE_REPLAY` and `EACH_GATE_MODULE_ROW` and one module run for each changed module to `plan_fail_to_pass` in `src/devops_cli/ci/fail_to_pass.py`, after the reads of a changed gate check module and before the worktree add, with the condition `a module of tests/gate/ changes`. Update the cases of `tests/ci/test_fail_to_pass.py` in this group: `test_fail_to_pass_dry_run_lists_the_replay_and_starts_nothing` and `test_fail_to_pass_dry_run_of_a_head_lists_the_fallback_diff` for the new plan lines, indices and conditions, `test_fail_to_pass_runs_the_processes_of_its_plan` for the new condition in its skip tuple, `test_fail_to_pass_dry_run_and_no_changed_tests` and `test_a_deleted_gate_check_in_a_fix_of_source_code_still_needs_proof` for the widened `fail_to_pass_no_tests` text, and `test_the_report_of_a_fix_that_only_deletes_gate_checks_names_each_check` for the widened `fail_to_pass_deleted_checks` text
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` passes

## 6. Widen the fail-to-pass path filter

Kind: other. Reads: `.github/workflows/fail-to-pass.yml`. Changes: `.github/workflows/fail-to-pass.yml`.

- [ ] 6.1 Replace the `tests/gate/*_checks/**` entry of the `paths` list of `.github/workflows/fail-to-pass.yml` with `tests/gate/**`, and correct the comment above the job so it says that a changed module under `tests/gate/` writes a problem line that can fail on the base
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor` passes

## 7. Describe the gate module replay in the help and the guide

Kind: other. Reads: `src/devops_cli/lang/en/help.py`, `CONTRIBUTING.md`, `tests/lang/test_language_catalogs.py`. Changes: `src/devops_cli/lang/en/help.py`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`, `CONTRIBUTING.md`.

- [ ] 7.1 Change the `fail_to_pass` help of `src/devops_cli/lang/en/help.py`: a changed module under `tests/gate/` runs its gate row or its own `main` on the base and head trees, a case of a check module or a problem line of a module directly under `tests/gate/` that fails on base and is gone on head proves the fix, and a fix that changes no source code and no module under `tests/gate/` needs no proof. Regenerate `docs/CLI_REFERENCE.md` and `docs/commands/ci.md` from the help. Change the Fail-to-Pass Evidence item of `CONTRIBUTING.md`: the check runs for a pull request that changes `src/` outside the knowledge base or a path under `tests/gate/`, and a changed module directly under `tests/gate/` is replayed with the row whose command runs it, on the base's own copy and on the head tree
  - Verification: `$ uv run devops ci docs` passes
- [ ] 7.2 Edit the `fail_to_pass` help of `src/devops_cli/lang/en/help.py`, regenerate `docs/CLI_REFERENCE.md` and `docs/commands/ci.md`, and edit the Fail-to-Pass Evidence item of `CONTRIBUTING.md`, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
