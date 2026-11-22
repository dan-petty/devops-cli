# Proposal

## Why

The release image jobs of the release workflow average over the 6 min bound of AGENTS.md rule 5: the study of 2026-11-20 gives 380 s for `MCP Server Image` and 364 s for `Runner Image` over 18 release runs, while `devops ci job-time` reads the test job only (#6522). #6262 covers only the test job. No check holds the bound on the two image jobs after the three cause fixes, so the same regression would return with no alarm.

## What Changes

- `devops ci job-time` gains a default list of three checks: `Tests & Coverage` of `ci.yml` on `main` over 20 runs, and `MCP Server Image` and `Runner Image` of `release.yml` on `main` over 10 runs, each at the 360 s limit that the staged tree defines.
- The command reads every check of the list, prints one table and one mean for each check, files one P0 issue for each job whose mean is over the limit, and exits 1 when a mean is over the limit or a read is short.
- A run that names `--job`, `--workflow`, `--branch`, `--runs` or `--limit` reads that one check, so the single-job use and its cases stay.
- `HELP.ci.job_time` and `HELP.ci.job_time_job` name the three checks, and `docs/commands/ci.md` and `docs/CLI_REFERENCE.md` are regenerated from them.
- `docs/TESTING.md` and the `Test Job Duration` step of `ci.yml` say that the daily check reads the test job and the two release image jobs.
- The spec delta adds one requirement to `ci-job-time`; no base requirement becomes false, because the test job stays a default check.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-job-time`: The release image jobs of the release workflow are checked

## Impact

- Code: `src/devops_cli/ci/job_time.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/help.py`, `.github/workflows/ci.yml`
- Documents: `docs/commands/ci.md`, `docs/CLI_REFERENCE.md`, `docs/TESTING.md`
- Tests: `tests/github/test_ci_job_time.py`, `tests/commands/test_ci.py`

## Feasibility

- The probe answers "The path `release.yml` is no file at the root of the staging commit. These files of the commit are candidates: `.github/workflows/release.yml`. No commit in the history deleted or renamed it.", so the plan names `.github/workflows/release.yml` and not the short name of the issue.
- The probe answers "The path `.github/workflows/release.yml` is a file of the staging commit.", "The path `AGENTS.md` is a file of the staging commit." and "The path `openspec/specs/ci-job-time/spec.md` is a file of the staging commit.", so the two files of the premise and the capability to extend exist at the staged commit.
- `search_code` for `A check that averages over 5 min` answered `AGENTS.md:11:A check that averages over 5 min + 1 min tolerance is a P0 bug.`, the rule that the issue cites for the bound.
- `search_code` for `matrix.title }} Image` answered `.github/workflows/release.yml:297: name: ${{ matrix.title }} Image`; `search_code` for `title: Runner` answered `.github/workflows/release.yml:316: title: Runner` and for `title: MCP Server` answered `.github/workflows/release.yml:322: title: MCP Server`, so the two jobs that the issue names are the jobs that the workflow defines.
- `read_file` of `src/devops_cli/config/constants.py:700-790` showed `src/devops_cli/config/constants.py:741:CONST_CI_TEST_BUDGET_SECONDS: Final[float] = 300.0`, `src/devops_cli/config/constants.py:745:CONST_CI_TEST_BUDGET_TOLERANCE_SECONDS: Final[float] = 60.0`, `src/devops_cli/config/constants.py:746:CONST_CI_JOB_TIME_LIMIT_SECONDS: Final[float] = (` and `src/devops_cli/config/constants.py:762:CONST_CI_TEST_JOB_NAME: Final[str] = "Tests & Coverage"`, so the limit of the plan is the 360 s sum that the staged tree defines and the plan gives that bound no new name.
- `search_code` for `DEFAULT_CI_JOB_TIME_RUNS` answered `src/devops_cli/config/defaults.py:532:DEFAULT_CI_JOB_TIME_RUNS: Final[int] = 20`, the window of the test job, and `search_code` for `CONST_CI_WORKFLOW_FILE` answered `src/devops_cli/config/constants.py:1638:CONST_CI_WORKFLOW_FILE = "ci.yml"`; the plan keeps both and adds a 10-run window for the release image jobs.
- `read_file` of `src/devops_cli/commands/ci.py:2740-2960` showed the command at `src/devops_cli/commands/ci.py:2820:@app.command(name="job-time", help=HELP.ci.job_time)` with one check per run from the options, as `src/devops_cli/commands/ci.py:2824: job: Annotated[str, typer.Option("--job", help=HELP.ci.job_time_job)] = CONST_CI_TEST_JOB_NAME,` shows, so the change extends this command and adds no command.
- `read_file` of `src/devops_cli/ci/job_time.py:70-167` showed `src/devops_cli/ci/job_time.py:70:def check_job_time(` and `src/devops_cli/ci/job_time.py:136:def raise_alarm(`, each taking a job, a workflow, a branch, a count and a limit, so the command reads three checks with them and neither function changes.
- `read_file` of `tests/github/test_ci_job_time.py` showed `tests/github/test_ci_job_time.py:37:_JOB = "Tests & Coverage"` and the cases that drive the command over the `github_api` fake, so the new cases go in that module and reach no network.
- `search_code` for `Check the duration of Tests & Coverage` answered `.github/workflows/ci.yml:425: - name: Check the duration of Tests & Coverage` and `tests/commands/test_ci.py:1821: "Check the duration of Tests & Coverage",`, so a renamed step needs the allowlist key of the parity test in the same change.
- `search_code` for `job-time` answered `docs/TESTING.md:204:The owner allows 60 s of tolerance for the variation of the runners`, a paragraph that describes the check as reading the test job only, so the testing guide changes with the code.
- The means of the issue, 380 s for `MCP Server Image` and 364 s for `Runner Image` over 18 release runs, are not checked by any tool of this run: the study of 2026-11-20 is not in the staged tree. The premise is confirmed for the rule, the bound and the two job names, and the numbers are not checked.
- The first checks against the real system, before any code: `uv run devops ci job-time --repo <owner>/devops-cli --workflow release.yml --job "MCP Server Image" --runs 10` and `uv run devops ci job-time --repo <owner>/devops-cli --workflow release.yml --job "Runner Image" --runs 10` print each run time and the mean, and the step stops with that evidence when a mean is not over 360 s.
- `src/devops_cli/ci/job_time.py:def check_job_time` needs a client of the GitHub Actions API and a network as a precondition of the call; the plan's tests pass the fake client of the `github_api` fixture, so no test reaches the network.
- `src/devops_cli/ci/job_time.py:def raise_alarm` needs a client of the GitHub issues API and a network as a precondition of the call; its cases double the search, the read of the body and the write with the `github_api` fixture.
- `devops_cli.github.session.get_github_session` needs a token and a network as a precondition of the call; the command calls it after the dry-run return, and no test calls it.
- The plan introduces no command and no verify program: every `verify` runs the existing `uv run devops ci test` row or the existing `uv run devops ci docs` row, so no failure class and no runner capability is new; `uv`, `python`, `pytest` and `devops` are runner tools, and the pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and drops every capability.
- `JOB_TIME_CHECKS` holds three checks; the case `test_the_default_checks_hold_the_test_job_and_the_two_release_image_jobs` of the first group is the census of that list, and the step stops when the count differs from three.

## Existing Tool Considered

The repository already runs its own `devops ci job-time` check: it reads the job times from the Actions API, files one P0 issue on a mean over the limit, holds the report in one alarm issue and makes no request on `--dry-run`. The change extends that check with two entries, about 40 lines and about 10k tokens to build and about 2 hours of work, and adopts no other tool.

## Dependencies

- #4361: The runner image build FROM devtools is the first of the three fixes that brings the Runner Image job under the bound, so it comes first.
- #6404: The registry cache is the second fix; the study blames the gha cache export for most of the image time, so it comes before the check can hold the bound.
- #6407: Closed and completed, and the one-build-per-image flow it asked for is in the staged release workflow, so nothing is outstanding from it.
