# Proposal

## Why

Issue #2699. The required check `Tests & Coverage` took 372 s on average over the last 24 successful runs of `main` on the GitHub runner, and 387 s over the newest 10 (`baseline.md`). AGENTS.md rule 5 makes a check that averages more than 5 minutes a P0 bug. Nothing fails when the time goes over the limit again.

## What Changes

- The biggest step is the test step: 341 s of the 372 s of the job (92%). Inside it, each of the 13,900 tests paid a fixed cost that no test asked for. The change removes that cost. Five cuts, each measured alone (`design.md`):
  - `tmp_path_retention_policy = "failed"` and a runtime directory made without a number: pytest listed the whole base directory for every numbered directory (89 s of CPU in a run, 15 s after).
  - The autouse fixture `isolate_llm_response_cache` builds nothing: the cache is built on first use (54 s of CPU of settings loads in a run, none after).
  - The garbage collector's young threshold is 50,000 in the root conftest (22 to 37 s in a worker, 5 to 10 s after).
  - The five test servers poll their shutdown every 0.01 s (19 s of idle teardown).
  - The click command of a Typer app is built once for each state of the app, not once for each `CliRunner.invoke` (about a tenth of the CPU of the run).
- `devops ci job-time` is new. It reads the time of a job in the last completed `push` runs of a workflow on a branch from the Actions API, and fails when the mean is over 300 s or fewer than 10 runs could be read. The conclusion of the job decides, not that of the run: a job that passed, failed or timed out counts, so the run that the guard turned red still gives its test time to the next window. The new job `Test Job Duration` in `ci.yml` runs it after each push to `main` and every day. The change carries one spec delta for it, because a command, its options and its messages are observable.
- No test is skipped, deselected or changed. No threshold moves: `fail_under = 85` and the 90% floor of the changed lines are as they were. The cuts are in test infrastructure (`pyproject.toml`, `tests/conftest.py`, `tests/support/`, five fixtures of test servers), and the one change that a test file needs is that `tests/support/markdown_examples.py` keeps its parse by the text of the document, since a path can now be reused.
- The change fits one pull request.

## Result

Measured here, not on the runner. The runner is the only source for the acceptance number, and its ten runs come after the merge. This change does not show that the mean is under 300 s.

- Same tests: the collected test ids of the base and of the change differ by the 22 new tests of `tests/test_ci_job_time.py` and nothing else (`pytest --collect-only -q`: 13,918 ids and 13,940 ids, 0 removed). All pass.
- Same coverage: the total is 93.73% before and 93.74% to 93.75% after, on 90,391 and 90,489 statements. The 98 added statements are the new command; its misses are covered by the new tests. Every other file has the same missing lines, except `telemetry/tracer.py` lines 604 and 605, which the base worktree covered because its `HEAD` was detached (a measurement artifact of the base tree, not of the change). `fail_under` and the changed-line floor are unchanged.
- Same run, first measure: 4 pinned CPUs (`taskset -c 0-3`, `-n 4`, the options of the gate), interleaved on one shared host. Base: 398, 378, 378 and 380 s (mean 383). Change: 280, 288, 282 and 295 s (mean 286). The ratio is 0.75.
- Same run, second measure (review): base and change at the same time on separate sets of 4 CPUs, the sets swapped in a second pair, host load 6 to 17. Wall time 390.6 s against 479.0 s (0.82) and 391.4 s against 484.6 s (0.81). CPU time 1,347 s against 1,685 s (0.80) and 1,339 s against 1,705 s (0.785). A run under heavier load gave 0.85 on wall time.
- The ratio is therefore 0.75 to 0.85, and 0.79 to 0.82 on CPU time. Applied to the runner's means the projection is 294 to 305 s from the 24-run mean (372 s) and 304 to 317 s from the newest 10 runs (387 s), which are slower because the suite grew from 13,055 to 13,803 tests across the 24 runs. The spread of the mean of ten runs is about 12 s. The target of 300 s is **not shown to be met**. It is inside the noise of the projection.
- The biggest step, `Tests & Coverage Quality Gate`: 341 s before (24 runs). The measure after comes from `devops ci job-time` once ten pushes to `main` have run, and from the run of the pull request for one sample.
- If ten runs on `main` read over 300 s, the next cuts are in #2371 (what each worker repeats at start: collection takes 40 s on the runner) and #2373 (the cost of coverage). Each has its own acceptance.

## Expected state after the merge

The guard reads the ten runs before a push. At the merge these are the slow runs, 372 to 387 s on average. The job `Test Job Duration` is therefore expected to be **red** on the merge push and on about 8 pushes after it (the mean falls under 300 s only when at least 8 of the 10 runs are new, for a new mean of 277 s). This red is not a regression. It says that the mean of ten runs of the new code is not yet read. The first push whose window holds only new runs reads the true mean. If it reads over 300 s, the job stays red, and that is the signal the guard exists to give. #2699 stays open until the mean reads under 300 s.

## Feasibility

- The premise is real. The 24 successful runs of `ci.yml` on `main` that were the baseline (`gh api repos/<owner>/<repo>/actions/runs/<run_id>/jobs`, read on 2026-10-30) average 372 s for the job and 341 s for the test step. The job log of each run gives the test count, the pytest time, and the time of collection (`baseline.md`).
- The cost of the cuts was measured before any code was written. A plugin timed each fixture (`make_numbered_dir` 88.7 s in 28,028 calls; `isolate_llm_response_cache` 53.6 s), `gc.callbacks` timed the collector, and cProfile of a 1,040-test sample showed `typer.main.get_command` at 13%.
- The cuts were tried one at a time against the options that the gate uses. Each one that was rejected has its evidence in `design.md`: more workers, another coverage core, libyaml for the settings, the startup-import probes, `gc.freeze()`, a bytecode cache.
- The guard works with the Actions API as it is: `GET /repos/{repo}/actions/workflows/{workflow}/runs?branch=main&event=push&status=completed` and `GET /repos/{repo}/actions/runs/{id}/jobs` give `started_at` and `completed_at` of each job. The fixture `tests/fixtures/github/ci_runs_main.json` holds 12 of the answers as they were recorded on 2026-10-30.
- The numbers of the runner are not reproducible on a workstation. The pinned run took 324 s in the base, against 372 s on the runner (a ratio of 1.15, 4 CPUs each), and the host varied by 20% between runs. For that reason the proof is by pairs of runs on one host and by counters inside the process (time in the collector, in fixtures, in `make_numbered_dir`), and the acceptance number is left to the runner.

## Existing Tool Considered

- **pytest**: `tmp_path_retention_policy` (a documented option of pytest 9.1.1) removes the numbered-directory cost. pytest-xdist's `-n` (already in use) and `--dist worksteal` were tried and stay.
- **CPython `gc`**: `gc.set_threshold` raises the young threshold. `gc.freeze` was tried and left out.
- **typer**: `typer.testing.CliRunner` is the runner that the suite already uses; the cache replaces its `_get_command` in tests only.
- **coverage.py**: the `sysmon` core is the default on Python 3.14 and the cheapest of the three cores that were timed. No option of coverage.py or pytest-cov lowers its cost without lowering what it measures.
- **GitHub Actions API** through the existing GitHub session (`GitHubClient`, which paces, retries and classifies errors). Nothing is built for the measure: `gh` and the Actions API give job times, and the new command only adds the mean and the limit. `timeout-minutes` stops a long job and does not average runs. No open tool averages the last ten runs of a job and fails: the built-in step timings and the usage metrics of GitHub are views, not checks.
- Code deleted: the eager `get_llm_response_cache()` call in a fixture, the numbered `mktemp("run")` of `isolate_session_bus`, and the `serve_forever` defaults in five fixtures. Nothing else is replaced.
