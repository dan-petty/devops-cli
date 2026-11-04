# Proposal

## Why

The required check `Tests & Coverage` averages 7 to 8 minutes on `main`. AGENTS.md rule 5 sets the bound at 5 minutes, so the check is a P0 bug (#3050). The job `Test Job Duration` of #2699 already reports the mean, and it is red on this state. This change makes the check fast, and it does not skip a test or lower a threshold.

The measure shows that the cost is not one slow step. It is the work of 18,000 tests on the 4 CPUs of one runner, and the runner speed moves that work by half.

## What Changes

- The test job runs in 4 shards on 4 runners. The shard jobs are named `Tests & Coverage (shard <n> of <total>)`. Each shard runs one quarter of the tests with `devops ci --check --no-cache --only test --shard <n> --shards 4`.
- `devops ci` takes the options `--shard` and `--shards`. They narrow the test row to one part of the suite with `pytest-split` (`--splits`, `--group`, `--splitting-algorithm least_duration`). A shard prints no coverage report and does not check the floor, because it measures a part of the tree. It keeps its coverage data in `.data/.coverage`.
- Each shard uploads `.data/.coverage` as an artifact. The job `Tests & Coverage` keeps its name and becomes the aggregate: it fails when a shard did not pass, downloads the data of the shards, combines them with `coverage combine`, and runs `coverage report`. The floor `fail_under = 85` of `pyproject.toml` applies to the combined data. The step `Changed-Line Coverage` reads the same combined data. The required check names do not change (ADR 0004, ADR 0014).
- A plan-only pull request still runs `tests/invariants` and nothing more. Shard 1 runs them, and the aggregate reports success without a download.
- `devops ci job-time` measures the check as a person waits for it: from the start of the first job `Tests & Coverage (…)` to the end of the job `Tests & Coverage`. Without shard jobs it reads the one job, as before. The default window grows from 10 to 20 runs, as the issue asks.
- `pytest-split` 0.11.0 joins the development dependencies.
- The observable change is a new option pair and the new default of `--runs`. The change therefore carries spec deltas: a new capability `ci-test-shards`, and changes to `ci-job-time` and `ci-coverage-reports`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ci-test-shards`: The test row runs in shards and the aggregate job checks the combined coverage

### Modified Capabilities

- `ci-job-time`: The job time covers the shard jobs, and the default window is 20 runs
- `ci-coverage-reports`: The changed-line coverage step reads the data that the aggregate job combined

## Impact

- Code: `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/github/client.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- Workflow: `.github/workflows/ci.yml`
- Dependencies: `pyproject.toml`, `uv.lock`
- Documents: `docs/TESTING.md`, `docs/SDLC.md`, `docs/commands/ci.md`, `docs/CLI_REFERENCE.md`, `docs/adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md`
- Tests: `tests/commands/test_ci.py`, `tests/github/test_ci_job_time.py`, `tests/invariants/test_workflow_contracts.py`

## Feasibility

The premise holds. The numbers come from the Actions API (`uv run devops gh api repos/dan-petty/devops-cli/actions/runs/<id>/jobs`) and from the job logs of 2026-11-04.

- The job `Tests & Coverage` on the last 30 completed pushes to `main` (2026-11-03 20:31 to 2026-11-04 16:54 UTC) took 474 s on average (7 min 54 s). The last 20 took 472 s. The fastest took 337 s and the slowest 578 s. No run was under 300 s.
- The runs fall into two groups: about 340 s to 440 s and about 500 s to 580 s. Both groups run the same suite.
- One fast run and one slow run, step by step:

  | Step | Fast run 41872247751 (46cf2883) | Slow run 41861187222 (7cf83354) |
  | :--- | :--- | :--- |
  | Set up job, filter, checkout | 8 s | 4 s |
  | Set up uv toolchain | 17 s | 19 s |
  | Install promtool | 2 s | 4 s |
  | Tests & Coverage Quality Gate | 323 s | 497 s |
  | Whole job | 355 s | 528 s |
  | Tests in the gate | 18,189 passed in 315.76 s | 18,187 passed in 488.92 s |
  | Runner region | westus3 | southcentralus |
  | Slowest test (`test_local_ai_commands_run_cleanly`) | 14.8 s | 46.9 s |
  | Slowest roadmap tests (`test_roadmap_implement_step`) | 4.7 s to 6.8 s | 6.7 s to 9.4 s |

- The difference of 174 s is in the test session alone. The setup steps differ by 2 s. The suite is the same (two tests differ), and every test ran 1.4 to 3.2 times longer on the slow runner. The cause of the swing is the speed of the runner, not a test that was added. The earlier 4 min 42 s of the issue came from a fast runner and a suite of 15,700 tests.
- The fast run alone is 355 s, over the bound. A cut of constant work cannot bring the slow runners under 300 s: the suite grew from about 15,700 tests on 2026-11-01 to 18,189 on 2026-11-04, and the check at 4 CPUs scales with it.
- The ruleset requires the names `Static Analysis`, `Tests & Coverage` and `Semantic PR title`. ADR 0004 names top-level aggregating jobs as the stable contract and rejects binding the ruleset to matrix jobs. The aggregate job keeps the name.
- `pytest-split` 0.11.0 was released on 2026-02-03 and lists Python 3.14. A local run on this tree with `--splits 4 --group 1..4 --splitting-algorithm least_duration` on 316 tests gave 79 tests in each group (237 deselected in each), with `pytest-xdist` 3.8.0 (`-n 4`), `pytest-cov` 7.1.0 and `syrupy` 6.1.1. Syrupy reported no unused snapshot. With `--cov-report= --cov-fail-under=0` a shard printed no report and kept `.data/.coverage`. `coverage combine .data/shards/*/.coverage` combined two such files, and `coverage report` then failed at 21% against `fail_under = 85`, so the floor holds on the combined data.
- `PYTEST_ADDOPTS` cannot carry the shard options: `build_subprocess_env` refuses that key (#2747). The options are therefore options of `devops ci`.

What cannot be proven before the merge: the mean of 20 runs of `main` at or under 300 s. The first 20 pushes after the merge still hold the old single-job runs in the window, so `Test Job Duration` stays red until about 15 new runs replace them. Before the merge, the pull request shows the wall time of the check on its own runs: from the first shard start to the end of the aggregate.

An estimate from the logs above: a shard needs about 30 s of setup, about 25 s of collection and a quarter of the 316 s to 489 s test time. The aggregate needs about 70 s for its setup, the download, the combine, the report and diff-cover. That gives about 215 s on a fast runner and about 260 s on a slow one.

## Existing Tool Considered

`pytest-split` (jerry-git, MIT, 0.11.0) splits a suite into equal groups and works with `pytest-xdist` and `pytest-cov`. `coverage combine` merges the data files of the shards, and `actions/upload-artifact` and `actions/download-artifact` carry them between jobs. The change builds no splitter and no merge. The cost of the code it adds is one option pair, about 6,000 tokens to build, about 1,500 tokens to keep, and about 3 hours. `pytest-testmon` and `pytest-xdist` alone were considered and rejected in the design.

## Dependencies

None.
