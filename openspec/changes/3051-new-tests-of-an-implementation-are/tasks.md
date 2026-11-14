# Tasks

## 1. Scan the new test files for a missing assertion

Kind: behavior. Reads: `.ast-grep/rules/test-function-has-assertion.yml`, `src/devops_cli/roadmap/implement/implement_scoped_ci.py`, `tests/roadmap/implement/test_roadmap_implement_scoped_ci.py`. Changes: `src/devops_cli/roadmap/implement/implement_strength.py` (new), `tests/roadmap/implement/test_roadmap_implement_strength.py` (new).

- [ ] 1.1 `test_a_new_test_file_that_asserts_nothing_is_flagged` in `tests/roadmap/implement/test_roadmap_implement_strength.py`: the sample file `test_sample.py` holds a `test_` function with no assertion, and the fake answers `uv run ast-grep scan` with one JSON match for it
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py` fails on the base
- [ ] 1.2 Create `src/devops_cli/roadmap/implement/implement_strength.py` with `AssertionFinding`, `new_test_files` and `assertion_failures`. `new_test_files` keeps the changed paths under `tests/` whose name starts with `test_`. `assertion_failures` runs `uv run ast-grep scan --rule .ast-grep/rules/test-function-has-assertion.yml --json` over those files, the rule that `.ast-grep/rules/test-function-has-assertion.yml` holds and the `constructs` row runs, and reads the file, the start line and the message of each match of the JSON list
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py` passes

## 2. Bound the mutation run and read its survivors

Kind: behavior. Reads: `src/devops_cli/ci/mutate.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/implement/implement_strength.py`, `tests/roadmap/implement/test_roadmap_implement_strength.py`, `tests/roadmap/test_roadmap_limit_classes.py`. Changes: `src/devops_cli/roadmap/implement/implement_strength.py`, `tests/roadmap/implement/test_roadmap_implement_strength.py`.

- [ ] 2.1 `test_the_mutation_run_stops_at_command_timeout_seconds_and_keeps_its_survivors` and `test_more_changed_files_than_CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES_are_named` in `tests/roadmap/implement/test_roadmap_implement_strength.py`, whose fake answers the mutmut commands of `src/devops_cli/ci/mutate.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py` fails on the base
- [ ] 2.2 Add `mutation_targets`, `run_mutation` and `MutationOutcome` to `src/devops_cli/roadmap/implement/implement_strength.py`. `mutation_targets` takes the targets of `select_targets` of `src/devops_cli/ci/mutate.py` for the changed files, keeps the targets of the first `CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES` source files, the constant of `src/devops_cli/config/constants.py`, and names the rest. That constant is the existing one whose row `tests/roadmap/test_roadmap_limit_classes.py` registers under the `CONST_ROADMAP_` prefix, so the registry test keeps holding it and no row changes. `run_mutation` runs `uv run mutmut run` with the globs of those targets under `roadmap.implement.command_timeout_seconds`, then reads `uv run mutmut results --all true` through `tally` of `src/devops_cli/ci/mutate.py`; a run that reaches the bound keeps the survivors it reads and reports the bound
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py` passes

## 3. Measure the coverage of the scoped test modules

Kind: behavior. Reads: `.github/workflows/ci.yml`, `pyproject.toml`, `src/devops_cli/commands/ci.py`, `src/devops_cli/roadmap/implement/implement_strength.py`, `tests/roadmap/implement/test_roadmap_implement_strength.py`. Changes: `src/devops_cli/roadmap/implement/implement_strength.py`, `tests/roadmap/implement/test_roadmap_implement_strength.py`.

- [ ] 3.1 `test_the_coverage_run_measures_the_scoped_test_modules`, `test_an_uncovered_changed_line_is_in_the_coverage_report` and `test_each_test_module_path_is_one_argument_of_the_coverage_run` in `tests/roadmap/implement/test_roadmap_implement_strength.py`: the fake records the three commands of `.github/workflows/ci.yml`, answers the coverage run and `uv run coverage xml -q` with exit 0, and answers diff-cover with the markdown report of one file with one missing line and exit 1
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py` fails on the base
- [ ] 3.2 Add `CoverageDelta` and `coverage_delta` to `src/devops_cli/roadmap/implement/implement_strength.py`. `coverage_delta(source, default_branch, tests)` runs `uv run pytest --cov=src --cov-report= --cov-fail-under=0 <tests>` in `source`, because `devops ci test` builds its argv in `src/devops_cli/commands/ci.py` with no coverage option and so writes no data, and because `pyproject.toml` adds no `--cov` to `addopts`; the empty report and the zero floor are those of a shard of the test row. Each test module path is one element of the argv, so no shell reads it. It then runs `uv run coverage xml -q` and `uv run diff-cover .data/coverage.xml --compare-branch=origin/<default_branch> --fail-under 100 --format markdown:<path>`, and keeps the text of the markdown report and whether the command passed. CI runs the same two commands from `.github/workflows/ci.yml` with `--fail-under 90`; the strength check requires 100 because one uncovered changed line must fail it. A failed coverage run or a failed diff-cover is a failed strength check with its log
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py` passes

## 4. Report the strength and skip a group of kind other

Kind: behavior. Reads: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement/implement_strength.py`, `tests/roadmap/implement/test_roadmap_implement_strength.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/implement/implement_strength.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_strength.py`.

- [ ] 4.1 `test_a_group_of_kind_other_is_left_out_with_its_reason` and `test_a_surviving_mutant_fails_the_strength_check` in `tests/roadmap/implement/test_roadmap_implement_strength.py`; the plan text holds a group with `Kind: other.` that names `docs/TESTING.md`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py` fails on the base
- [ ] 4.2 Add `strength_scope`, `StrengthReport` and `strength_report` to `src/devops_cli/roadmap/implement/implement_strength.py`, and their texts to `src/devops_cli/lang/en/messages.py`. `strength_scope` reads the `Kind:` line of each group with `KIND_LINE` of `src/devops_cli/roadmap/step_files.py` and leaves the changed files of a group of kind `other` out of the scan, the mutation run and the coverage delta, with the group number as the reason. `strength_report` runs the assertion scan, the mutation run and the coverage run of the scoped test modules in order, fails on an assertion finding, a surviving mutant or an uncovered changed line, and passes with the bound named when the mutation run reached one. It names the reason and runs no coverage part when no test module covers the change
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py` passes

## 5. Run the strength check and show it in the comment

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_strength.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_strength.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement/implement_strength.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_strength.py`.

- [ ] 5.1 `test_the_comment_shows_the_strength_report_and_the_skip_reason` and `test_a_failed_strength_report_is_a_failed_scoped_result` in `tests/roadmap/implement/test_roadmap_implement_strength.py`, with the run built by `_ItemRun` of `src/devops_cli/roadmap/implement/implement_run.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py` fails on the base
- [ ] 5.2 Add `report_lines` and `scoped_result` to `src/devops_cli/roadmap/implement/implement_strength.py`. In `src/devops_cli/roadmap/implement/implement_run.py`, add the field `strength` to `_ItemRun`, run `strength_report` in `_scoped_run` with the changed paths and the test modules it already computes after every scoped check passed, keep its report, and show `report_lines` in `_comment`. A failed report becomes a `ScopedResult` named `strength` whose log is the report, so the repair loop of `_scoped_rounds`, bounded by `roadmap.implement.repair_rounds`, gives it to a repair step
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py` passes

## 6. Document the strength check

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`.

- [ ] 6.1 Describe the strength check in the scoped checks of the implement job in `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md`: the assertion scan, the mutation run and its two bounds, the coverage run of the scoped test modules and its delta, the skip of a group of kind `other`, and the lines that the comment shows
  - Verification: `$ uv run devops ci --check --only docs` passes
- [ ] 6.2 Edit `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md` with the strength check, its two bounds, its coverage run, the skip of a group of kind `other` and the lines that the comment shows
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test file that asserts nothing is flagged in a replay test.
- Group 5: The mutation run has a time bound and the report is in the PR comment.
- Group 5: The coverage delta of the changed files is in the PR comment.
- Group 4: The check is skipped, with the reason shown, for groups of kind `other`.
- Pending person: Live proof: after the merge and the release, the next implement Job runs the check as the App. A comment gives the strength value of each new test., Only a person can merge, release and read the comment of the next implement Job of the App; no test of this change reaches GitHub.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
