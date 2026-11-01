# Proposal

## Why

Issue #2373: the owner asked on 2026-10-27 (the decision comment on #2356) if the measure of branches that #2163 proposes is worth its job time. No clean number exists for what coverage costs the test row. The runs of #2356 had a host load of 10 to 39, and one run changed three things at once (core, contexts and branches). This change measures the cost on a host that is idle, and it reports the number on #2163 for the owner to decide. The owner sets the thresholds, not this change.

## What Changes

- Run four configurations of the test row three times each, on a host with a load under 2 before each run: no coverage, lines, lines and branches, and lines with the `ctrace` core. Report the median CPU time (user plus system) and the median wall time of each.
- Time the serial end of the lines run as three commands, each alone: `coverage combine`, `coverage report --show-missing` and `coverage xml`.
- State the cost of the branch measurement in seconds of CPU and of wall time.
- When `coverage combine` plus `coverage report` take 5 % or more of the wall time of the lines run, run the lines configuration three more times without the term report, and state the saving. A change to the options of the test row is then a follow-up issue. This change alters no option and no threshold.
- The change delivers numbers, not a behavior. It changes no code, no test, no workflow, no manifest and no document of the repository, so it has no spec delta and sets `skip_specs: true` in `.openspec.yaml`. The tools and scratch files stay under `.data/agent/scratch/` outside git. The table goes to the pull request body and to a comment on #2163, as the issue asks.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- The pull request holds this change folder, archived. No tracked file outside `openspec/changes/` changes.
- Code and tests this change keeps as they are:
  - `_resolve_pytest_cmd` in `src/devops_cli/commands/ci.py` builds the command of the "lines" configuration. The change reads it and does not edit it.
  - `tests/commands/test_ci.py::test_the_gate_test_row_writes_the_term_report_and_no_xml_report` and `tests/commands/test_ci.py::test_gate_test_step_argv_is_unchanged` pin that command. They stay green.
  - The requirement "The test row writes no XML report" of `openspec/specs/ci-coverage-reports/spec.md` stays true.
  - `fail_under = 85` in `pyproject.toml` stays at 85.
- #2163 (open) plans `branch = true` in `pyproject.toml`. If it merges first, the "lines" configuration cannot be run, so group 1 stops the work when `pyproject.toml` holds a `branch` key.

## Acceptance

| Criterion of #2373 | Group |
| :--- | :--- |
| 1. A table of the median CPU time and wall time of four configurations, each from three runs on an idle host | 1 (method and guard), 2 (runs and table) |
| 2. The cost of the branch measurement in seconds of CPU time and job time | 4 (statement), posted on #2163 and written in the pull request body |
| 3. The serial end timed as separate commands: `coverage combine`, `coverage report --show-missing`, `coverage xml` | 3 |
| 4. A change, if one is made, lowers the CPU time of "lines" and lowers no threshold | 4 makes no change to the options or to a threshold: a saving found is a follow-up issue, and the check `git diff origin/main -- pyproject.toml src .github` prints nothing |

## Feasibility

The checks ran on 2026-11-01 in a worktree at `origin/main` (commit 1c20865a).

- The gate command is not the one that the archived design of #2356 states. `uv run python -c "from devops_cli.commands.ci import _resolve_pytest_cmd as r; print(' '.join(r()))"` prints `uv run pytest --durations=10 --cov=src --cov-report=term-missing`. The gate writes no XML report since #2582 and #1743 (both closed). The "lines" configuration therefore has no `--cov-report=xml`. CI runs `uv run coverage xml -q` alone in the `Changed-Line Coverage` step (`.github/workflows/ci.yml`, line 168), so the `coverage xml` time is still a real cost of the job, paid after the gate.
- No branch measurement is on yet. `git grep -n '^branch' origin/main -- pyproject.toml` prints nothing, and `[tool.coverage.run]` holds `parallel = true` (line 230). `fail_under = 85` is at line 235. The plan for #2163 (`openspec/changes/2163-coverage-measures-branches-and-ci-keeps/tasks.md`) adds `branch = true`, and #2163 is open.
- Nothing newer did this measure. `git grep -n -i 'cov-branch\|ctrace' origin/main -- docs src openspec/specs` finds no cost figure. The only text is the archived design of #2356 (`openspec/changes/archive/2026-10-27-2356-coverage-floor-and-test-cost/design.md`, line 80), which says the cost "is not established" and names #2373. #2356 is closed as completed.
- The old figures are stale as a baseline. #2764 (`e76f656c`, 2026-10-30) cut the work of the tests after the 287 s of #2356, so the plan measures again and does not reuse 287 s, 93.01 % or 90.75 %.
- The versions are `coverage` 7.16.1, `pytest-cov` 7.1.0, `pytest-xdist` 3.8.0 and `pytest` 9.1.1 (`uv pip list`). The suite collects 15,756 tests (`uv run pytest --collect-only -q`), and `git ls-files 'src/*.py' | wc -l` prints 629 files.
- The host is not idle now. `cat /proc/loadavg` prints `30.65 25.70 22.84` (16 CPUs), because other agents run beside this one. The condition "load under 2" of the issue holds only at some times, so group 1 makes the work wait for it, and stop when it does not come.
- The user plus system CPU time of a run, workers included, comes from the bash `time` keyword with `TIMEFORMAT='%U %S %R'`. On a trial run of `tests/commands/test_ci.py` with `-n 4` and coverage it printed `79.411 6.399 43.155`, which is more CPU time than wall time, so the time of the worker processes is counted. `/usr/bin/time` is not installed here.
- `pytest-cov` combines the data files of the workers in the controller and deletes them (`pytest_cov/engine.py`, `DistMaster.finish` calls `self.cov.combine()`). So `coverage combine` cannot run alone on the data of a normal run. `coverage combine --keep` exists (`uv run coverage combine --help`). A scratch plugin that calls `Coverage.combine` with `keep=True` leaves the worker files. A trial run with it left 5 worker files in `.data/`. On that trial data (one test file), `coverage combine --keep`, `coverage report --show-missing` and `coverage xml` took 1.4 s, 15.8 s and 17.6 s of wall time. So the three commands run alone, and the report and the XML are not small.
- `coverage run` with `patch = subprocess` would also leave worker files, but it measures every Python subprocess that the tests start, and the gate does not (`pyproject.toml` has no `patch` key). The scratch plugin keeps the data of the gate command, so it is the faithful way.

## Existing Tool Considered

Nothing is built. `coverage.py` 7.16.1 and `pytest-cov` 7.1.0 are in use, and the cores (`sysmon`, `ctrace`) and branch measurement are their options. `coverage combine --keep`, `coverage report` and `coverage xml` give the time of the serial end. The bash `time` keyword and `statistics.median` of the standard library give the CPU time, the wall time and the median. `hyperfine` is not installed and is in no tools lock (`git grep -n -i hyperfine origin/main -- . ':!openspec'` prints nothing). It would add a tool to time twelve runs of one hour each, which bash does. The scratch runner is about 20 lines of shell and the plugin is 6 lines of Python. Both stay under `.data/agent/scratch/` and are not committed. No internal code is deleted.
