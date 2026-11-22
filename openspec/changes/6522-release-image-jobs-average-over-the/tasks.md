# Tasks

## 1. Add the release image jobs to the job-time list

Kind: behavior. Reads: `src/devops_cli/ci/job_time.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `tests/github/test_ci_job_time.py`, `tests/commands/test_ci.py`, `tests/roadmap/stage/test_roadmap_stage_time.py`. Changes: `src/devops_cli/ci/job_time.py`, `tests/github/test_ci_job_time.py`.
Adds: `JobTimeCheck`, `JOB_TIME_CHECKS`, `job_time_checks`, `RELEASE_WORKFLOW_FILE`, `RELEASE_IMAGE_JOB_NAMES`, `RELEASE_IMAGE_RUNS`

- [x] 1.1 `test_the_default_checks_hold_the_test_job_and_the_two_release_image_jobs` in `tests/github/test_ci_job_time.py` fails on the base: `JOB_TIME_CHECKS` holds three checks, and `job_time_checks` narrows to one check when an option is given
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py` fails on the base
- [x] 1.2 Add `JobTimeCheck` and the module constants `RELEASE_WORKFLOW_FILE`, `RELEASE_IMAGE_JOB_NAMES` and `RELEASE_IMAGE_RUNS` to `src/devops_cli/ci/job_time.py`, and build `JOB_TIME_CHECKS` from them and from `CONST_CI_TEST_JOB_NAME`, `CONST_CI_WORKFLOW_FILE`, `CONST_GIT_MAIN_BRANCH`, `DEFAULT_CI_JOB_TIME_RUNS` and `CONST_CI_JOB_TIME_LIMIT_SECONDS`. Add `job_time_checks`, which returns `JOB_TIME_CHECKS` when no option is given and one check from the options otherwise. Write the two cases in `tests/github/test_ci_job_time.py`: the list of three checks, and one check when an option is given. Keep `check_job_time` and `raise_alarm` as they are
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py` passes

## 2. Read every check of the list in the job-time command

Kind: behavior. Reads: `src/devops_cli/commands/ci.py`, `src/devops_cli/ci/job_time.py`, `src/devops_cli/lang/en/messages.py`, `tests/github/test_ci_job_time.py`, `tests/commands/test_ci.py`, `tests/ci/test_ci_cache.py`, `tests/ci/test_ci_gate_admission.py`, `tests/ci/test_ci_mutate.py`, `tests/ci/test_fail_to_pass.py`, `tests/ci/test_typecheck.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_ci_build_index.py`, `tests/commands/test_ci_bwrap_row.py`, `tests/commands/test_ci_domain_row.py`, `tests/commands/test_ci_dry_run.py`, `tests/commands/test_ci_gate_rows.py`, `tests/commands/test_ci_maintain.py`, `tests/commands/test_ci_repeat.py`, `tests/commands/test_ci_row_commands.py`, `tests/commands/test_ci_shard.py`, `tests/commands/test_cli_startup_imports.py`, `tests/commands/test_dependency_audit.py`, `tests/commands/test_net_construct_rules.py`, `tests/commands/test_ruff_complexity_cap.py`, `tests/commands/test_security_bandit.py`, `tests/commands/test_security_zizmor.py`, `tests/commands/test_test_selection.py`, `tests/docs/test_docs.py`, `tests/invariants/test_hermetic_floor.py`, `tests/invariants/test_workflow_contracts.py`, `tests/roadmap/implement/test_roadmap_implement_scoped_ci.py`, `tests/roadmap/implement/test_roadmap_implement_step_typecheck.py`, `tests/roadmap/test_roadmap_runner_tools.py`. Changes: `src/devops_cli/commands/ci.py`, `tests/github/test_ci_job_time.py`.

- [x] 2.1 `test_the_command_reads_the_test_job_and_the_two_release_image_jobs` in `tests/github/test_ci_job_time.py` fails on the base: three tables and three means, and exit 0. The case `test_the_command_files_one_p0_issue_for_a_release_image_job_over_the_limit` asserts the title `fix(ci): MCP Server Image averages 380 s, over the 360 s limit` and the four labels
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py` fails on the base
- [x] 2.2 In `src/devops_cli/commands/ci.py`, let the five options of `job_time` take no default, build the checks with `job_time_checks`, and loop: read each check with `check_job_time`, print it with `_print_job_time_report`, raise its alarm when `--file-issue` is given and the read is full and over the limit, and exit 1 when any check does not pass. Let `_render_job_time_plan` take one `JobTimeCheck` and call it once for each check in a dry run. In `tests/github/test_ci_job_time.py`, route 10 runs of the release workflow with both image jobs inside the limit in the cases that drive the command with no option, and add the cases of the three checks, the alarm of a release image job, the short release read, the one-check run and the dry run of three plans. `tests/commands/test_ci.py` is the existing test module of the command and keeps passing
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py` passes

## 3. State the three checks in the job-time help and regenerate the pages

Kind: other. Reads: `src/devops_cli/lang/en/help.py`, `docs/commands/ci.md`, `docs/CLI_REFERENCE.md`, `tests/lang/test_language_catalogs.py`. Changes: `src/devops_cli/lang/en/help.py`, `docs/commands/ci.md`, `docs/CLI_REFERENCE.md`.

- [x] 3.1 Rewrite `HELP.ci.job_time` and `HELP.ci.job_time_job` in `src/devops_cli/lang/en/help.py`: the default reads the test job of `ci.yml` over 20 runs and the two release image jobs of `release.yml` over 10 runs, each at the 360 s limit, and an option narrows the run to one check. Run `uv run devops docs generate` to rewrite `docs/commands/ci.md` and `docs/CLI_REFERENCE.md` from the new help, and run `uv run devops ci docs` until it reports every page current
  - Verification: `$ uv run devops ci docs` passes
- [x] 3.2 Edit `src/devops_cli/lang/en/help.py` and regenerate `docs/commands/ci.md` and `docs/CLI_REFERENCE.md` with `uv run devops docs generate`, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 4. State the three checks in the testing guide

Kind: other. Reads: `docs/TESTING.md`, `.github/workflows/ci.yml`. Changes: `docs/TESTING.md`.

- [x] 4.1 Rewrite the Run time paragraph of `docs/TESTING.md` from the sentence that allows 60 s of tolerance: the daily job reads the test job of `ci.yml` over 20 runs and the two release image jobs of `release.yml` over 10 runs, each at the 360 s limit, files one P0 issue for each job over the limit, and fails when a read is short. Say that the alarm line of each job holds its own issue, as `.github/workflows/ci.yml` shows for the `Test Job Duration` job
  - Verification: `$ uv run devops ci docs` passes
- [x] 4.2 Edit `docs/TESTING.md` so that the Run time section names the test job, `MCP Server Image` and `Runner Image` and their windows
  - Verification: `$ uv run devops ci docs` passes

## 5. Name the release image jobs in the job-time workflow step

Kind: other. Reads: `.github/workflows/ci.yml`, `tests/commands/test_ci.py`. Changes: `.github/workflows/ci.yml`, `tests/commands/test_ci.py`.

- [x] 5.1 Rename the step `Check the duration of Tests & Coverage` of the `Test Job Duration` job in `.github/workflows/ci.yml` to `Check the duration of the test and release image jobs`, and extend the comment above the job so that it names the two release image jobs and their 10-run window. Update the allowlist key of the parity test in `tests/commands/test_ci.py` to the new step name, so that the job-time step stays a named exception and no gate row is lost
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py` passes
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
