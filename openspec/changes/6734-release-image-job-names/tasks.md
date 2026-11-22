# Tasks

## 1. Check the real release image job names

Kind: behavior. Reads: `.github/workflows/release.yml`, `.github/workflows/release-image.yml`, `tests/github/test_ci_job_time.py`. Changes: `src/devops_cli/ci/job_time.py`, `tests/github/test_ci_job_time.py`.

- [x] 1.1 In `tests/github/test_ci_job_time.py`, make `_route_release_runs` give the jobs of the live API: each release run holds `Release Please`, `Upload Release Assets`, the DevContainer jobs and `<Title> Image / Build`, `/ Verify` and `/ Attest & Tag` of the three images, and a run between two release runs holds only skipped jobs and `${{ matrix.title }} Image`. Write `test_the_command_reports_the_mean_of_each_release_image_job_of_the_api` and the census `test_the_default_checks_hold_the_test_job_and_the_six_release_image_jobs`. Both fail on the base, which asks for `MCP Server Image` and `Runner Image`
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py` fails on the base
- [x] 1.2 In `src/devops_cli/ci/job_time.py`, rename the release constants to `_RELEASE_WORKFLOW_FILE`, `_RELEASE_IMAGE_JOB_NAMES` and `_RELEASE_IMAGE_RUNS`, and make `_RELEASE_IMAGE_JOB_NAMES` the six names of the API. Move the release cases of the test module to the new names, add the case of a release image job at the 360 s limit with `--file-issue`, pass `--file-issue` in the short-read case, and remove the duplicate call of `test_no_issue_is_searched_or_filed_without_a_full_read_over_the_limit`
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py` passes

## 2. Share one read for the checks of one workflow

Kind: behavior. Reads: `src/devops_cli/ci/durations.py`, `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/github/client.py`, `src/devops_cli/ci/job_time.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `tests/github/test_ci_job_time.py`.
Adds: `get_run_times_of_jobs`, `check_job_times`, `job_time_reads`

- [x] 2.1 Write `test_the_checks_of_one_workflow_ask_for_the_jobs_of_each_run_one_time` in `tests/github/test_ci_job_time.py`: with no option, the command lists the runs of `release.yml` one time and asks for the jobs of each release run one time. Replace the dry-run case of three plans with `test_a_dry_run_lists_one_plan_for_each_read`. Both fail on the base, which reads each check on its own
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py` fails on the base
- [x] 2.2 In `src/devops_cli/github/client.py`, add `get_run_times_of_jobs`, which reads the jobs of each run one time and gives each job of a tuple its times, and make `get_job_run_times` read through it with one job. Keep the shard rule in `_job_run_time`. In `src/devops_cli/ci/job_time.py`, add `job_time_reads`, which groups the checks by workflow, branch and count, and `check_job_times`, which gives the report of each check from one read of each group. In `src/devops_cli/commands/ci.py`, read the reports with `check_job_times` and render one dry-run plan for each read, with the heading `job_time_dry_run_heading` that names the jobs
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py` passes

## 3. Stop a read after a fixed count of runs

Kind: behavior. Reads: `src/devops_cli/github/session.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/github/client.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `tests/github/test_ci_job_time.py`.
Adds: `DEFAULT_CI_JOB_TIME_MAX_RUNS`

- [x] 3.1 Write `test_a_read_that_finds_no_release_image_job_stops_after_a_fixed_count_of_runs` in `tests/github/test_ci_job_time.py`: the listing of `release.yml` holds 150 runs on two pages and no release image job, and the command asks for the jobs of the first 100 runs only, reads no second page, exits 1 and names the bound. It fails on the base, which reads every run
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py` fails on the base
- [x] 3.2 Add `DEFAULT_CI_JOB_TIME_MAX_RUNS` (100) beside `DEFAULT_CI_JOB_TIME_RUNS` in `src/devops_cli/config/defaults.py`, stop the loop of `get_run_times_of_jobs` after the jobs of that many runs, and name the bound in `job_time_short` and in the repeat line of the dry-run plan
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py` passes

## 4. State the checks in the help and the documents

Kind: other. Reads: `src/devops_cli/ci/job_time.py`. Changes: `src/devops_cli/lang/en/help.py`, `docs/commands/ci.md`, `docs/CLI_REFERENCE.md`, `docs/TESTING.md`, `.github/workflows/ci.yml`.

- [ ] 4.1 In `src/devops_cli/lang/en/help.py`, make `HELP.ci.job_time` name the six release image jobs and the bound of 100 runs, and put the shard and queue sentences back into `HELP.ci.job_time_job`. Run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 4.2 In the comment of the `Test Job Duration` job of `.github/workflows/ci.yml`, name the six release image jobs, and say that the job writes its report into the body of the open P0 issue of the check, or files one when none is open. In the Run time paragraph of `docs/TESTING.md`, name the six jobs, the shared read and the bound, and say that the alarm line of `src/devops_cli/ci/job_time.py` names the job, the workflow and the branch
  - Verification: `$ uv run devops ci --check --only actionlint,docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
