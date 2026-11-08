# Tasks

## 1. Run four coverage configurations and record medians

Reads: none. Changes: `docs/TESTING.md`.

- [x] 1.1 Run the four coverage configurations (no coverage, lines with `--cov=src --cov-report=`, lines and branches with `--cov-branch`, and lines with `COVERAGE_CORE=ctrace`) in three interleaved rounds on shard 1 pinned to four CPUs with `taskset -c 0-3` and `-n 4`. Record the user plus system CPU time, wall time, and load average before each run
- [x] 1.2 Add the `### Coverage cost` subsection to `docs/TESTING.md` with the method description, the run records table (round 1 to 3, CPU seconds, wall seconds, load average), and the median table for each of the four configurations
- [x] 1.3 Verify that `docs/TESTING.md` contains the `### Coverage cost` subsection, all four gate configurations, the `taskset -c 0-3` pinned CPU rule, and the three round records with `git grep -n 'Coverage cost' docs/TESTING.md` and `git grep -n 'taskset -c 0-3' docs/TESTING.md`

## 2. Time the serial coverage commands

Reads: none. Changes: `docs/TESTING.md`.

- [x] 2.1 Time `coverage combine`, `coverage report --show-missing`, and `coverage xml` on four shard data files using the bash `time` keyword
- [x] 2.2 Add the serial command timings table to `docs/TESTING.md` under `### Coverage cost`, reporting the wall time of each command and noting that `coverage xml` runs only on pull requests
- [x] 2.3 Verify that `docs/TESTING.md` records the wall time for each serial command with `git grep -n 'coverage combine' docs/TESTING.md` and `git grep -n 'coverage xml' docs/TESTING.md`

## 3. State the cost and apply the conditional change

Reads: none. Changes: `docs/TESTING.md`.

- [x] 3.1 Calculate the difference between lines and lines-and-branches medians in CPU seconds and wall seconds for one shard, and whole-job CPU as four times the per-shard difference
- [x] 3.2 Calculate the combined serial end (`coverage combine` plus `coverage report`) in seconds and as a percentage of the lines job time. State whether it reaches 15 s and whether a follow-up issue is needed
- [x] 3.3 Add the branch cost statement and serial share statement to `docs/TESTING.md`, confirm that no threshold or gate option was lowered (`fail_under = 85` in `pyproject.toml`), and verify with `git diff origin/main -- pyproject.toml src .github`
