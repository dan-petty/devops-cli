# Proposal

## Why

Issue #2373: the owner asked on 2026-10-27 (the decision comment on #2356) whether branch measurement is worth its job time. Earlier tries were confounded by host load or changed several variables at once. The idle-host gate of the first plan stopped the work because the host load average was over 3.9. This change measures four configurations of one shard in three interleaved rounds on four pinned CPUs, times the serial coverage commands on the shard data files, records the results in `docs/TESTING.md`, and states the cost of branch measurement in seconds of CPU and of job time.

## What Changes

- Run four configurations of one shard in three interleaved rounds on four pinned CPUs (`taskset -c 0-3`, `-n 4`): no coverage, lines (`--cov=src --cov-report=`), lines and branches (`--cov=src --cov-report= --cov-branch`), and lines with the `ctrace` core (`COVERAGE_CORE=ctrace`). Record CPU time (user plus system), wall time, and the load average before each run.
- Time the serial coverage commands on the four shard data files: `coverage combine`, `coverage report --show-missing`, and `coverage xml`. Note that `coverage xml` runs only on pull requests.
- State the median CPU time and median wall time of each configuration.
- State the cost of branch measurement as the difference between the lines configuration and the lines and branches configuration, in CPU seconds and wall seconds per shard, and as four times the per-shard difference for whole-job CPU.
- State the serial end in seconds and as a percentage of the measured lines job time, and state whether it reaches 15 s.
- Document the results in `docs/TESTING.md` in a `### Coverage cost` subsection.
- This change alters no option and no threshold in `pyproject.toml` or CI. The change folder sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `docs/TESTING.md` gains a `### Coverage cost` subsection after `### Coverage`.
- The pull request archives this change folder. No tracked code or configuration file outside `docs/TESTING.md` changes.
- Floors and options remain unchanged: `fail_under = 85` in `pyproject.toml`, `--fail-under 90` in diff-cover, and test row options in `_resolve_pytest_cmd`.

## Acceptance

| Requirement | Description | Group |
| :--- | :--- | :--- |
| Coverage cost section | `docs/TESTING.md` holds a `### Coverage cost` subsection with a table of four configurations | 1 |
| Gate configurations named | Table holds no coverage, `--cov=src --cov-report=`, that command with `--cov-branch`, and that command with `COVERAGE_CORE=ctrace` | 1 |
| Pinned CPUs and no idle-host gate | Method pins each run to four CPUs with `taskset -c 0-3` and has no load-average stop | 1 |
| Three interleaved rounds | Report holds three runs of each configuration from three interleaved rounds with round, CPU time, wall time, load average | 1 |
| Median of each configuration | Median CPU time and wall time of each configuration | 1 |
| Cost of branches in seconds | Cost in CPU seconds and wall seconds per shard, and whole-job CPU as four times per-shard | 3 |
| Serial coverage commands timed | Wall time of `coverage combine`, `coverage report --show-missing`, `coverage xml` on four shard data files | 2 |
| Serial share statement | Serial end in seconds, percentage of lines job time, and whether it reaches 15 s | 3 |
| No threshold or gate option lowered | `fail_under` is 85, diff-cover is 90, gate options unchanged | 3 |
| Plan names a tracked file | `tasks.md` has groups whose `Changes:` line names `docs/TESTING.md` | 1, 2, 3 |

## Feasibility

The checks ran on 2026-11-08 in this worktree on commit bfe01926 (`origin/main`).

- `git grep -n '^branch' origin/main -- pyproject.toml` shows `pyproject.toml:237:branch = true`, merged in PR #4031 (#2163).
- `uv run python -c "from devops_cli.commands.ci import _resolve_pytest_cmd; print(' '.join(_resolve_pytest_cmd(shard=1, shards=4)[:6]))"` prints `uv run pytest --durations=10 --cov=src --cov-report=`.
- Running shard 1 of 4 with `taskset -c 0-3 uv run pytest -n 4` executes 5,126 tests across 263 files.
- Serial coverage commands run on shard data files: `coverage combine` combines shard files, `coverage report --show-missing` computes total and missing lines, and `coverage xml` writes the XML report.
- The bash `time` keyword with `TIMEFORMAT='%U %S %R'` captures user, system, and wall time for worker processes and controller.

## Existing Tool Considered

`coverage.py` 7.16.1 and `pytest-cov` 7.1.0 are in use and cover coverage measurement. The cores (`sysmon`, `ctrace`) and branch measurement are their options. `coverage combine`, `coverage report` and `coverage xml` measure the serial end. The bash `time` keyword and `statistics.median` provide timing and medians. No new tool is built.
