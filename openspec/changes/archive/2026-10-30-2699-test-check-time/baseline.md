# Baseline

This file records where the time of the `Tests & Coverage` job goes on the GitHub runner, before this change. Every figure comes from the Actions API (`devops gh api repos/<owner>/<repo>/actions/runs/<run_id>/jobs`, and `.../actions/jobs/<job_id>/logs`) for the 24 latest successful runs of `ci.yml` on `main`, read on 2026-10-30. The job runs on `ubuntu-26.04`, 4 CPUs, 4 pytest workers (`-n logical`).

## The job, run by run

Seconds. "Job s" is `completed_at - started_at` of the job. The step columns are the same difference for each step. "Other" is the job's own set-up, the changed-line coverage step and the post steps. "Tests" is the number of items that pytest collected, and "pytest s" is the time that pytest printed on its last line. "Start to collected" is the time from the first line of `devops ci` to the line `4 workers [N items]`. "Collected to last row" is the time from that line to the last full row of dots.

| Run id | Commit | Job s | Checkout | Setup uv | Promtool | Gate step | Other | Tests | pytest s | Start to collected | Collected to last row |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 40985544611 | ae446f0f | 404 | 4 | 18 | 3 | 375 | 4 | 13803 | 369 | 43 | 299 |
| 40984740506 | 79ff8bda | 345 | 4 | 19 | 3 | 315 | 4 | 13803 | 309 | 35 | 247 |
| 40983651748 | 34136cbc | 399 | 4 | 20 | 3 | 366 | 6 | 13802 | 359 | 46 | 285 |
| 40982073460 | a3453463 | 413 | 4 | 18 | 4 | 383 | 4 | 13786 | 377 | 43 | 338 |
| 40980414753 | 4a57b950 | 321 | 4 | 16 | 3 | 293 | 5 | 13770 | 288 | 35 | 257 |
| 40979165917 | 5278c53e | 418 | 4 | 22 | 3 | 383 | 6 | 13770 | 377 | 43 | 337 |
| 40977313797 | 279b3d01 | 425 | 5 | 18 | 3 | 395 | 4 | 13754 | 388 | 46 | 347 |
| 40976203755 | 043463b6 | 324 | 4 | 15 | 2 | 299 | 4 | 13754 | 294 | 31 | 266 |
| 40971514618 | bf5cf0e8 | 411 | 5 | 20 | 3 | 379 | 4 | 13694 | 372 | 43 | 334 |
| 40969160859 | 244bafbf | 409 | 4 | 21 | 3 | 375 | 6 | 13694 | 368 | 43 | 329 |
| 40943393132 | 9e8317bb | 378 | 4 | 17 | 3 | 350 | 4 | 13579 | 343 | 40 | 307 |
| 40941576081 | 9c7a5f50 | 396 | 4 | 18 | 3 | 368 | 3 | 13579 | 361 | 43 | 323 |
| 40938998553 | 31fe55cb | 398 | 3 | 18 | 3 | 369 | 5 | 13491 | 363 | 45 | 322 |
| 40930588438 | c4623188 | 380 | 4 | 17 | 3 | 352 | 4 | 13464 | 347 | 41 | 309 |
| 40924557601 | 23058712 | 359 | 5 | 19 | 3 | 326 | 6 | 13433 | 322 | 40 | 285 |
| 40922244310 | 19a2e084 | 368 | 7 | 21 | 3 | 331 | 6 | 13431 | 327 | 42 | 288 |
| 40920125482 | abd016db | 307 | 4 | 14 | 3 | 282 | 4 | 13431 | 278 | 35 | 245 |
| 40915228489 | 11b7cb53 | 279 | 3 | 16 | 2 | 254 | 4 | 13338 | 250 | 34 | 218 |
| 40912439467 | ec2f7f7d | 387 | 5 | 22 | 3 | 350 | 7 | 13289 | 345 | 41 | 307 |
| 40909960125 | 4f993dce | 382 | 4 | 18 | 4 | 352 | 4 | 13289 | 347 | 42 | 309 |
| 40907514910 | 7f85930f | 364 | 4 | 19 | 3 | 334 | 4 | 13104 | 329 | 40 | 292 |
| 40905709379 | edf53257 | 279 | 4 | 16 | 2 | 253 | 4 | 13062 | 248 | 31 | 220 |
| 40900120508 | 8036e7ef | 384 | 4 | 21 | 3 | 349 | 7 | 13055 | 344 | 44 | 303 |
| 40898352709 | 39fae855 | 396 | 8 | 21 | 3 | 358 | 6 | 13055 | 353 | 42 | 314 |

| Mean of | Job s | Setup uv | Gate step | pytest s | Start to collected | Collected to last row |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| The newest 10 runs | 386.9 | 18.7 | 356.3 | 350.1 | 40.9 | 304.0 |
| All 24 runs | 371.9 | 18.5 | 341.3 | 335.7 | 40.4 | 295.0 |

The spread is wide. The job took 279 s at best and 425 s at worst. Two runs on the same number of tests (13,055 and 13,062 items) took 396 s and 279 s. The standard deviation of one run is 38 s, so the mean of ten runs moves by about 12 s from one window to the next.

## The biggest step

The step `Tests & Coverage Quality Gate` takes 341 s of the 372 s mean (92%). It runs `uv run devops ci --check --no-cache --only test`, which runs

```
uv run pytest --durations=10 --cov=src --cov-report=term-missing
```

with `-n logical --dist worksteal` from `addopts`. No other step takes more than 22 s: `Set up uv toolchain` (the `uv sync --locked --all-groups --all-extras --compile-bytecode` of the shared action) takes 18.5 s, checkout 4.4 s, promtool 3 s. Cutting a set-up step cannot bring the job under 300 s: all set-up steps together are 26 s.

## Inside the test step

From the job log of run 40985544611 (369 s of pytest, 13,803 items) and the 23 other logs:

- Workers start and collect: 31 to 46 s, mean 40 s, before the first test runs. Every worker imports and collects the whole suite; none shares the work.
- Tests: 295 s, from the collection line to the last full row of dots. The rows get slower at the end, because a worker that has no test left cannot split the last long tests.
- The report: the terminal report of coverage for 560 files takes about 9 s (`coverage report --show-missing` alone, measured on a workstation), after the last test.
- The slowest single test takes 9 s, so a long test is not the cause. The ten slowest tests of the run add up to 54 s of 1,314 s of test time (workstation proxy, below).

## Where the CPU goes (a proxy)

The runner is not a workstation, so the figures below are a proxy: they come from the same tree on a workstation with the process pinned to 4 CPUs (`taskset -c 0-3`, `-n 4`, 13,918 tests, the options of the gate). The pinned run took 324 s against the 372 s mean of the runner, a ratio of 1.15, and it is the same kind of run: 4 workers on 4 CPUs.

| Part of the run | Figure | Source |
| :--- | ---: | :--- |
| All time inside tests (set-up, call, tear-down), summed over the workers | 1,314 s | `pytest --durations=0` |
| Set-up of the tests alone | 362 s (28%) | the same |
| Set-up of 3 autouse fixtures (`isolate_session_bus`, `tmp_path`, `isolate_llm_response_cache`) | 168 s (13% of the CPU) | a plugin that times each fixture |
| `make_numbered_dir` (one call for each `tmp_path` and each `mktemp`) | 88.7 s in 28,028 calls, 3.2 ms for each | a plugin that times the function |
| The garbage collector, per worker | 22 to 37 s of about 300 s | `gc.callbacks`, a plugin |
| Pure-Python YAML parse | 53 s | a plugin that times `get_data` |
| Coverage (`sysmon` core), against no coverage, wall time | 324 s against 269 s (+20%) | two pinned runs |
| `tests/test_cli_startup_imports.py` (56 interpreters) | 99 s of 1,314 s (7.5%) | `pytest --durations=0` |

Two micro-measurements explain the first rows. `make_numbered_dir` lists every entry of the base directory to find the next number: with `tmp_path_retention_policy = "all"` the base directory of a worker holds one directory for every test it has run, so the 1st call took 0.16 ms and the 3,500th took 1.64 ms (a loop of 3,500 calls in a scratch directory). The default garbage collector threshold of 2,000 made a collection run 4,000 to 7,000 times in a worker, and the ten full collections of a 1,040-test sample took 0.9 s each, 8.9 s of the 11.3 s the collector took (a serial run of 22 test modules, 50 s in all).

## Decision

The largest part is the test step, and inside it the tests themselves (295 s). No test can be skipped and no threshold can be lowered, so the cut is the work that every test repeats and that no test asks for: the numbered directories, the settings load of an autouse fixture, and the garbage collector. Together they are a fifth of the CPU of the run. `design.md` records the other candidates and why each was rejected or left to its own item.
