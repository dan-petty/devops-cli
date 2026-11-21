# Tasks

## 1. Split a given list of test files into shards by recorded seconds

Kind: behavior. Reads: `src/devops_cli/core/test_selection.py`, `tests/commands/test_ci_shard.py`, `tests/ci/test_ci_durations.py`, `tests/commands/test_test_selection.py`. Changes: `src/devops_cli/core/test_selection.py`, `tests/commands/test_ci_shard.py`.
Adds: `shard_paths`

- [x] 1.1 Add the failing case `tests/commands/test_ci_shard.py::test_shard_paths_puts_each_given_file_in_one_shard` for the requirement `The test command runs one shard of the files it selects`: a small tree with a duration record, where each given file lands in one shard only and the heaviest given file goes to the lightest shard
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py` fails on the base
- [x] 1.2 Add `shard_paths(shard, shards, modules, root)` to `src/devops_cli/core/test_selection.py`: weigh each given module by its recorded seconds of `CONST_CI_TEST_DURATIONS_PATH`, weigh a module with no record by its lines at the recorded seconds per line, weigh a module that the tree does not hold at 0 seconds, give the heaviest module first to the shard with the least weight, and return the sorted paths of shard `shard`. Make `shard_test_files` call it with `directory_modules(CONST_TESTS_ROOT_DIR, root)`, so the split of the whole suite keeps its weights and each module stays in one shard
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py` passes

## 2. Take the shard options in the test command

Kind: behavior. Reads: `src/devops_cli/commands/ci.py`, `src/devops_cli/core/test_selection.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_ci_shard.py`, `tests/commands/test_ci_repeat.py`, `tests/ci/test_ci_cache.py`, `tests/ci/test_ci_gate_admission.py`, `tests/ci/test_ci_mutate.py`, `tests/ci/test_fail_to_pass.py`, `tests/ci/test_typecheck.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_ci.py`, `tests/commands/test_ci_build_index.py`, `tests/commands/test_ci_bwrap_row.py`, `tests/commands/test_ci_domain_row.py`, `tests/commands/test_ci_dry_run.py`, `tests/commands/test_ci_gate_rows.py`, `tests/commands/test_ci_maintain.py`, `tests/commands/test_ci_row_commands.py`, `tests/commands/test_cli_startup_imports.py`, `tests/commands/test_dependency_audit.py`, `tests/commands/test_net_construct_rules.py`, `tests/commands/test_ruff_complexity_cap.py`, `tests/commands/test_security_bandit.py`, `tests/commands/test_security_zizmor.py`, `tests/commands/test_test_selection.py`, `tests/docs/test_docs.py`, `tests/invariants/test_hermetic_floor.py`, `tests/invariants/test_workflow_contracts.py`, `tests/roadmap/implement/test_roadmap_implement_scoped_ci.py`, `tests/roadmap/implement/test_roadmap_implement_step_typecheck.py`, `tests/roadmap/test_roadmap_runner_tools.py`. Changes: `src/devops_cli/commands/ci.py`, `tests/commands/test_ci_shard.py`, `tests/commands/test_ci_repeat.py`.

- [ ] 2.1 Add the failing cases `tests/commands/test_ci_shard.py::test_a_sharded_test_run_passes_only_the_files_of_its_shard` and `tests/commands/test_ci_repeat.py::test_each_repeat_pass_runs_only_the_files_of_its_shard`, which cover the requirements `The test command runs one shard of the files it selects` and `Each repeat pass of a shard runs the files of that shard`
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py tests/commands/test_ci_repeat.py` fails on the base
- [ ] 2.2 Add the options `--shard` and `--shards` to `test()` in `src/devops_cli/commands/ci.py`, each a whole number of at least 1 with the default 1 and the help `HELP.ci.shard` and `HELP.ci.shards`. Refuse a shard above the total with `MESSAGES.ci.shard_above_total` and `typer.BadParameter`, as the gate does, before any pytest starts. After `_resolve_test_targets`, replace the targets with the files of the shard: `shard_test_files` when the run names no path, `shard_paths` when it names paths. Return when the shard holds no file, so pytest never starts with no target and the whole suite. The repeat branch then runs each pass over the shard's files, and the case in `tests/commands/test_ci_shard.py` covers an empty shard
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py tests/commands/test_ci_repeat.py` passes

## 3. Run the changed-test check as a matrix of shard jobs

Kind: other. Reads: `.github/workflows/ci.yml`, `tests/commands/test_ci.py`, `tests/invariants/test_workflow_contracts.py`. Changes: `.github/workflows/ci.yml`, `tests/commands/test_ci.py`.

- [ ] 3.1 In `.github/workflows/ci.yml`, make the job `changed-tests` a matrix over `shard: [1, 2, 3, 4, 5, 6, 7, 8]` with `fail-fast: false` and the name `Changed-Test Independence (shard ${{ matrix.shard }} of ${{ strategy.job-total }})`. Keep the release skip, the step `Detect Changed Test Files` and the toolchain step, and give the toolchain step the cache suffix `changed-tests-${{ matrix.shard }}` so eight jobs never save one key. Pass `SHARD` and `SHARDS` from the matrix to the step `Run Changed Tests in Shuffled Order`, which adds `--shard` and `--shards` beside `--repeat 3`. Give that step `timeout-minutes: 12` and keep the job limit at 15 minutes. Add the job `changed-tests-result`, named `Changed-Test Independence`, with `needs: [changed-tests]`, the same pull request condition and release skip, `!cancelled()` in its `if`, `timeout-minutes: 5`, `permissions: contents: read`, and one step `Require Passing Changed-Test Shards` that reads the matrix result through `env` and ends red unless it is `success`. Add the row `("changed-tests-result", "Require Passing Changed-Test Shards")` to the allowlist of `_validate_ci_workflow_parity` in `tests/commands/test_ci.py`, with the reason that the step reports the result of the shard matrix and runs no `devops ci` row. Rewrite the comment above the job to say that eight shards run the three passes over their own files
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py tests/invariants/test_workflow_contracts.py` passes

## 4. Regenerate the command page of the ci group

Kind: other. Reads: `docs/commands/ci.md`, `src/devops_cli/lang/en/help.py`. Changes: `docs/commands/ci.md`.

- [ ] 4.1 Run `uv run devops docs generate` so the option table of `devops ci test` in `docs/commands/ci.md` holds `--shard` and `--shards` with the help text of the gate. Change no other page, and leave the command matrix of `docs/CLI_REFERENCE.md` as it is
  - Verification: `$ uv run devops ci --check --only docs` passes
- [ ] 4.2 Regenerate `docs/commands/ci.md` with `uv run devops docs generate` so the option table of `devops ci test` holds `--shard` and `--shards`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
