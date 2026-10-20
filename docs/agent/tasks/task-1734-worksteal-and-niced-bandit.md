# Task: The Gate's Test Workers Finish Together and Bandit Stops Competing With the Test Row (#1734)

**Issue**: [#1734](https://github.com/dan-petty/devops-cli/issues/1734)
**Scope**: scope/ci
**Feasibility**: Replaying xdist 3.8's `load` and `worksteal` schedulers over the per-test times of a full run (the JUnit report of the 2026-10-20 measurement) gives:

| Workers | `load` ends at | `worksteal` ends at | Saved |
|---|---|---|---|
| 16 (local) | 103.7s | 97.1s | 6.6s |
| 4 (the CI runner) | 358.1s | 316.2s | 41.9s |

The 41.9s saving on 4 workers matches the runner's measured 51s tail. `-n 0` still sets xdist's dist to `no`, so the narrowed runs' worker choice (#1669) is unchanged. The pytester tests that pass their own `-n 2 --dist loadfile` still pass under an outer `worksteal` run. This WSL2 kernel has no `CONFIG_SCHED_AUTOGROUP`, so a niced process yields CPU to the gate's other rows.

## Description

- [x] `pyproject.toml`'s `addopts` runs `-n logical --dist worksteal`, with a comment giving the replay numbers.
- [x] The gate's security row starts `uv run nice -n 10 bandit ...`, at niceness `DEFAULT_CI_BANDIT_NICENESS` in `config/defaults.py`.
  - Targets and the medium threshold are unchanged.
  - `devops ci security` runs the same row.
  - `tests/test_ci.py::test_the_gate_starts_bandit_below_the_test_row_s_priority` records the argv the gate starts. It fails at the base with `[] != ['nice', '-n', '10']`.
- [x] `docs/TESTING.md`, `docs/SDLC.md` and `docs/ROUTINE_TASKS.md` say so. `ROUTINE_TASKS.md` no longer says the gate caps workers at 8.
- [x] Three alternating pairs of full runs at load 19-71: the last worker finished closer to the median with `worksteal` in every pair (85.7s to 64.1s, 36.1s to 22.3s, 302.8s to 35.3s). Wall time followed the host's load.
  - One gate run before and one after, at load 24-56 and 20-42: 13m53s and 7m23s. The niced Bandit ended 34s before the test row.
- The 4-worker saving on the CI runner is a replay estimate until CI's own timings confirm it. #1725's closing re-measurement reads them.
