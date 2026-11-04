# Tasks

## 1. Add the development dependency pytest-split

Reads: `pyproject.toml`, `uv.lock`. Changes: `pyproject.toml`, `uv.lock`.

- [x] 1.1 Add `pytest-split==0.11.0` to the `dev` group of `pyproject.toml` and run `uv lock`, so the lockfile holds the one new package
  - Verification: `uv lock --check`

## 2. Run one shard of the test row with devops ci

Reads: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_ci.py`. Changes: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_ci_shard.py`.

- [x] 2.1 Add `tests/commands/test_ci_shard.py`: the unsharded row is unchanged, a shard holds the split options and no floor and no report, the dry run lists the split, a shard above the total or under 1 exits 2, a sharded run reads and writes no cached verdict, and no other row changes
  - Verification: `uv run devops ci test tests/commands/test_ci_shard.py` fails on the base
- [x] 2.2 Add the options `--shard` and `--shards` to the callback of `devops ci`, the argument `shard` and `shards` to `_resolve_pytest_cmd`, `_with_test_shard` for the `test` row, and the help and message strings
  - Verification: `uv run devops ci test tests/commands/test_ci_shard.py` passes

## 3. Time the check from the first shard to the end of the join

Reads: `src/devops_cli/github/client.py`, `src/devops_cli/config/defaults.py`, `tests/github/test_ci_job_time.py`. Changes: `src/devops_cli/github/client.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `tests/github/test_ci_job_time.py`.

- [x] 3.1 Add cases to `tests/github/test_ci_job_time.py`: a run with shard jobs is timed from the first shard start to the end of the job, a job with a longer name does not count, a run whose job was cancelled is left out, and the default window is 20 runs
  - Verification: `uv run devops ci test tests/github/test_ci_job_time.py` fails on the base
- [x] 3.2 Change `_job_seconds` in `src/devops_cli/github/client.py` to take the first start of the job and its shard jobs, and set `DEFAULT_CI_JOB_TIME_RUNS` to 20
  - Verification: `uv run devops ci test tests/github/test_ci_job_time.py` passes

## 4. Split the test job in CI

Reads: `.github/workflows/ci.yml`, `tests/invariants/test_workflow_contracts.py`, `tests/commands/test_ci.py`, `tests/invariants/test_architectural_invariants.py`. Changes: `.github/workflows/ci.yml`, `tests/invariants/test_workflow_contracts.py`, `tests/commands/test_ci.py`, `tests/invariants/test_architectural_invariants.py`.

- [x] 4.1 Replace the job `test` of `ci.yml` with the matrix job `test-shard` and the job `test`, named `Tests & Coverage`, that waits for it, fails when a shard did not succeed, combines the coverage data, checks `fail_under` and runs the changed-line coverage. Pin `actions/upload-artifact` and `actions/download-artifact` by commit
  - Verification: `uv run devops ci --check --only actionlint,zizmor` passes
- [x] 4.2 Rewrite the plan-only contract in `tests/invariants/test_workflow_contracts.py` for the two jobs, with a mutation case for each new part, and update the parity allowlist and the job checks of `tests/commands/test_ci.py` and `tests/invariants/test_architectural_invariants.py`
  - Verification: `uv run devops ci test tests/invariants/test_workflow_contracts.py tests/commands/test_ci.py tests/invariants/test_architectural_invariants.py` passes

## 5. State the new test jobs in the documents

Reads: `docs/TESTING.md`, `docs/SDLC.md`, `docs/adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md`. Changes: `docs/TESTING.md`, `docs/SDLC.md`, `docs/adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md`, `docs/commands/ci.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`.

- [x] 5.1 Describe the shards, the join and the 20-run window in `docs/TESTING.md` and `docs/SDLC.md`, add the line to ADR 0014, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci --check --only docs` passes

## 6. Read the log of a failed shard in the implement watch

Reads: `src/devops_cli/roadmap/implement_pull.py`, `tests/roadmap/test_roadmap_implement_pull.py`. Changes: `src/devops_cli/roadmap/implement_pull.py`, `tests/roadmap/test_roadmap_implement_pull.py`.

- [x] 6.1 Make the watch name a failed shard check before the failed join check, and test it with both checks failed
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_pull.py` passes

## Workflow follow-up

- Pending a person: after the merge, read `Test Job Duration` on `main`. The first 20 pushes hold single-job runs, so the mean of 20 falls under 300 s after about 15 pushes. State the mean in #3050 then. If it stays over 300 s, add a number to the matrix `shard` of `test-shard`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
