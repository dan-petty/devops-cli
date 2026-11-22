# Proposal

## Why

The release image check of `devops ci job-time` (#6522) matches no real job, so it never reports a release image time, and the daily job does not end inside its 5 min timeout (#6734). Since #6571, `release.yml` calls `release-image.yml` one time for each image, and the Actions API names the jobs `<Title> Image / Build`, `<Title> Image / Verify` and `<Title> Image / Attest & Tag`. A run with no release holds one skipped job `${{ matrix.title }} Image`. The check asks for `MCP Server Image` and `Runner Image`, which no run holds, so the reader reads the jobs of every completed run of `release.yml`: 2,385 runs on 2026-11-22, one request for each. The test fake uses the bare names, so the tests pass while the real check matches nothing.

## What Changes

- The default list of `devops ci job-time` holds one check for each of the six real jobs of the two images of #6522: `MCP Server Image / Build`, `MCP Server Image / Verify`, `MCP Server Image / Attest & Tag`, `Runner Image / Build`, `Runner Image / Verify` and `Runner Image / Attest & Tag`, each over 10 runs at the 360 s limit.
- The checks of one workflow, branch and count share one read: the client asks for the jobs of each run one time and gives each job its time. The dry run lists one plan for each read.
- A read stops after the jobs of `DEFAULT_CI_JOB_TIME_MAX_RUNS` (100) runs, also when a check has fewer runs than it wants. The short-read message names that bound.
- The shard rule stays: the time of a check is the run time of its job plus its slowest shard job `<job> (…)`.
- The test fake of the release runs uses the names of the live API, with an `Upload Release Assets` job, the `Service Image` jobs, and runs with no release that hold the skipped `${{ matrix.title }} Image` job.
- The release constants of `src/devops_cli/ci/job_time.py` become private, because only that module reads them.
- The minor findings of the post-merge review of the change of #6522: the duplicate call in a test, the comment of the `Test Job Duration` job of `ci.yml`, the alarm sentence of `docs/TESTING.md`, and the shard and queue sentences of `HELP.ci.job_time_job`.
- The spec delta modifies two requirements of `ci-job-time`, because the command reads other job names and a bounded count of runs.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-job-time`: The release image jobs of the release workflow are checked, Only the wanted runs are read

## Impact

- Code: `src/devops_cli/ci/job_time.py`, `src/devops_cli/github/client.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- Workflow comment: `.github/workflows/ci.yml`
- Documents: `docs/TESTING.md`, `docs/commands/ci.md`, `docs/CLI_REFERENCE.md`
- Tests: `tests/github/test_ci_job_time.py`

## Feasibility

- `devops gh api repos/dan-petty/devops-cli/actions/runs/44977064803/jobs` (a release run of 2026-11-22) lists `Runner Image / Build`, `Runner Image / Verify`, `Runner Image / Attest & Tag`, the same three for `MCP Server Image` and `Service Image`, `Release Please`, `Upload Release Assets` and the three DevContainer jobs. No job has the bare name `MCP Server Image` or `Runner Image`.
- The jobs of run 44979901604 (no release) are `Release Please`, the skipped `Upload Release Assets`, the three skipped DevContainer jobs and the skipped `${{ matrix.title }} Image`.
- `.github/workflows/release.yml` names the caller job `${{ matrix.title }} Image` with `if: needs.release-please.outputs.release_created == 'true'`, and `.github/workflows/release-image.yml` names its jobs `Build` (`timeout-minutes: 20`), `Verify` (15) and `Attest & Tag` (10). Each job can run past 360 s, so each one is a check.
- The listing of completed push runs of `release.yml` on `main` gives `total_count` 2385. Of its last 100 runs, 21 are release runs, and the tenth release run is run 48.
- `timeout 280 uv run devops ci job-time --repo dan-petty/devops-cli --workflow release.yml --job "Runner Image / Build" --runs 10` on the base read 10 runs with a mean of 175 s and took 38 s. Six such reads one after the other take about 230 s of the 300 s job, so the checks of one workflow must share one read.

## Existing Tool Considered

No open tool reads the mean run time of named GitHub Actions jobs over the history of a branch with the shard rule and the alarm issue of this repository. The change fixes the in-repository check of #2699 and #6522 and builds no new component: about 150 changed lines, about 60k tokens and about 3 hours. It deletes the bare job names `MCP Server Image` and `Runner Image` from the default list and the fake.

## Dependencies

None. Related: #6522 and #6571.
