# Proposal

## Why

The check `Changed-Test Independence` runs the changed test files of a pull request three times, one run after another, each in a shuffled order. Each run used one process (`-n 0`), so the time of the job grows with the number of changed tests. On pull request #6562, one run of 1,473 tests took 454 s, and one run of 1,805 tests took 594 s. GitHub cancelled the job at its limit of 15 minutes in the second run, on each head. A cancelled job gives no result. Issue #6564 asks for a pass or fail result under the 5 min + 1 min bound of AGENTS.md rule 5, with the same tests, the same three shuffled runs and no higher timeout.

## What Changes

- A `--repeat` run of `devops ci test` uses the workers that a narrowed run of the same files gets: one process for up to 50 collected tests, else the worker cap (4 workers, or fewer when `PYTEST_XDIST_AUTO_NUM_WORKERS` is smaller). A given `-n` applies to each run. The command chooses the workers one time for all of its runs. A run on workers gives `--dist loadfile`, so all tests of one file run on one worker. Above 50 tests, a leak from one changed file into another changed file on another worker is not caught.
- The new option `--run <k>` of `devops ci test` starts only run `<k>` of the `--repeat` runs, with the seed of that run. It refuses a run above `--repeat` with exit 2.
- The job `changed-tests` of `ci.yml` is a matrix of three jobs, `Changed-Test Independence (run <k> of 3)`. Each job runs `devops ci test --repeat 3 --run <k>` on the changed test files. Its test step has a limit of 12 minutes under the job limit of 15 minutes, so a run that is too long fails with a message, and the job is not cancelled.
- The new job `changed-tests-result`, named `Changed-Test Independence`, needs the three runs and fails when one of them did not succeed.
- The workflow parity allowlist of `tests/commands/test_ci.py` holds the step of the new job.
- `docs/TESTING.md` and the generated page `docs/commands/ci.md` state the new worker rule and the option `--run`.
- The option and the worker choice are observable behavior of a command, so the change has deltas of `ci-test-workers` and `ci-test-shards`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-test-workers`: Repeat runs take the workers of a narrowed run (it replaces Repeat runs make no collection).
- `ci-test-shards`: One repeat run starts alone.

## Impact

- Code: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- Workflow: `.github/workflows/ci.yml`
- Documents: `docs/TESTING.md`, `docs/commands/ci.md`
- Tests: `tests/commands/test_ci_repeat.py`, `tests/commands/test_test_selection.py`, `tests/commands/test_ci.py`

## Feasibility

- The job log of #6562 at head `e78252815` (job 136565700410) shows `collected 1473 items` and `1473 passed in 454.18s`, then `The operation was canceled` at 21:15:31. The job log at head `399500f09` (job 136670779803) shows `collected 1805 items`, `1805 passed in 594.22s`, and the cancel at 01:16:16. Each job used 26 s to 31 s before pytest started.
- `src/devops_cli/commands/ci.py` on `origin/main` builds each repeat run with `_build_test_cmd("0", ...)`, so each run used one process and ignored `-n`.
- The five shard jobs of `Tests & Coverage` of the same run ran 4,847 to 5,852 tests each in 139 s to 193 s, with 4 xdist workers on the 4 CPUs of the runner (`created: 4/4 workers`).
- `tests/module_durations.json` records 3,372 s for the 1,327 test modules. The 53 changed files of `e78252815` record 988 s, and one file, `tests/roadmap/implement/test_roadmap_implement_job.py`, records 191.8 s of it.
- The changed test files of the 1,118 commits of `main` in the 21 days to 2026-11-21 record a median of 8.7 s, 72 s at the 90th percentile, 296 s at the 99th percentile, and 1,318 s at most (`git log --name-only` against `tests/module_durations.json`).
- pytest-xdist 3.8.0 and pytest-randomly 5.1.0 are in the dev group of `pyproject.toml`. pytest-randomly gives the same `--randomly-seed` to each xdist worker, so each worker collects the same shuffled order.

## Existing Tool Considered

pytest-xdist runs each shuffled run on the CPUs of the runner, and the matrix of GitHub Actions runs the three runs on three runners. Both are open, maintained tools, and the project uses both already: the test row runs on xdist workers, and `Tests & Coverage` is a matrix of shards. pytest-repeat (`--count`) repeats each test in one session with one seed, so it gives no new shuffle for each run and no parallel run. pytest-split splits files by recorded time, as the `--shard` option of `devops ci` does already, and a split by file keeps the slowest file in one process. The change builds only the option `--run` and the worker choice of a repeat run, which reuses `_narrowed_workers`: about 30k tokens to build, keep and fix, and about 1 hour of elapsed time. The change deletes the fixed `-n 0` of the repeat runs.

## Dependencies

None.
