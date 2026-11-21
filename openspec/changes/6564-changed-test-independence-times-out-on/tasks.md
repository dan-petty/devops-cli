# Tasks

## 1. Run each repeat run on the workers of a narrowed run, and start one run alone

Kind: behavior. Reads: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_ci_repeat.py`, `tests/commands/test_test_selection.py`. Changes: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_ci_repeat.py`, `tests/commands/test_test_selection.py`, `docs/commands/ci.md`, `docs/TESTING.md`.
Adds: `run_above_repeat`, `repeat_run`

- [x] 1.1 Add the failing cases `tests/commands/test_ci_repeat.py::test_the_repeat_runs_take_the_workers_of_a_narrowed_run_from_one_collection`, `tests/commands/test_ci_repeat.py::test_a_named_run_starts_only_that_run_with_its_own_seed` and `tests/commands/test_ci_repeat.py::test_a_run_above_the_repeat_count_is_refused_before_any_process`. Change `test_each_repeat_runs_the_targets_serially_with_the_next_seed` to `test_each_repeat_runs_the_targets_on_the_given_workers_with_the_next_seed`, which expects the given `-n 4`. In `tests/commands/test_test_selection.py`, give the repeat case of `test_a_run_that_chooses_its_workers_by_other_means_makes_no_collection` the option `-n 2`
  - Verification: `$ uv run devops ci test tests/commands/test_ci_repeat.py tests/commands/test_test_selection.py` fails on the base
- [x] 1.2 In `test()` of `src/devops_cli/commands/ci.py`, choose the workers before the repeat branch, with `-n` or `_narrowed_workers`, and build the command of each run with them. Add the option `--run` (help `HELP.ci.repeat_run`), refuse a run above `--repeat` with `MESSAGES.ci.run_above_repeat` and `typer.BadParameter` before any process starts, and give the run to `_run_shuffled_repeats`, which starts only that run with its seed. Change the help `HELP.ci.repeat`, which said that a repeat run ignores `-n`
  - Verification: `$ uv run devops ci test tests/commands/test_ci_repeat.py tests/commands/test_test_selection.py` passes
- [x] 1.3 Run `uv run devops docs generate` so that `docs/commands/ci.md` holds `--run` and the new help of `--repeat`, and state the worker rule of a repeat run and the option `--run` in `docs/TESTING.md`
  - Verification: `$ uv run devops ci --check --only docs` passes

## 2. Run the changed-test check as three runs with one aggregate job

Kind: other. Reads: `.github/workflows/ci.yml`, `tests/commands/test_ci.py`, `tests/invariants/test_workflow_contracts.py`. Changes: `.github/workflows/ci.yml`, `tests/commands/test_ci.py`.

- [x] 2.1 In `.github/workflows/ci.yml`, make the job `changed-tests` a matrix over `run: [1, 2, 3]` with `fail-fast: false` and the name `Changed-Test Independence (run ${{ matrix.run }} of ${{ strategy.job-total }})`. Give the toolchain step the cache suffix `changed-tests-${{ matrix.run }}`. Pass `RUN` and `RUNS` from the matrix to the step `Run Changed Tests in Shuffled Order`, which runs `devops ci test --repeat "$RUNS" --run "$RUN"`, and give that step `timeout-minutes: 12` under the job limit of 15 minutes. Add the job `changed-tests-result`, named `Changed-Test Independence`, with `needs: [changed-tests]`, `!cancelled()`, the pull request condition and the release skip in its `if`, `timeout-minutes: 5`, `permissions: {}`, and the step `Require Passing Changed-Test Runs`, which ends red unless the matrix result is `success`. Add the row `("changed-tests-result", "Require Passing Changed-Test Runs")` to the allowlist of `_validate_ci_workflow_parity` in `tests/commands/test_ci.py`
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
