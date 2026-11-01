# Proposal

## Why

Issue #2371 asks for two things. First, measure what each of the xdist workers repeats before and between its tests. Second, remove the largest share of that work. A full run on 16 workers took 287 s on 2026-10-27, and its tests added up to 151 s of that. The issue says the other 136 s is worker start, collection that each worker repeats, the tail of the longest tests and the coverage report.

Those figures are old. The suite now has 15,801 tests, not 11,285, and #2764 cut other repeated work after the measurement. The change measures again before it picks a lever.

## What Changes

- The change measures one full run on an idle host three times, and splits the CPU time of each worker into start, collection and busy time.
- The change ranks the heavy modules that a test body imports for the first time.
- The change applies the one candidate that removes the largest share of CPU time, and measures three runs again.
- The change adds no module that does not already exist, and no product code.
- The change alters no behavior that a consumer observes: it is a change to the test suite and to its settings. So it carries no spec delta and sets `skip_specs: true` in `.openspec.yaml`.
- The change fits one pull request.
- The coverage report is out of scope. Issue #2373 owns it. The startup-import tests are out of scope. Issue #2369 owns them.

## Acceptance

- Criterion 1, three-run CPU split per worker: group 1.
- Criterion 2, ranked list of first imports: group 1.
- Criterion 3, the change with the largest share, and the reason: groups 2 and 3.
- Criterion 4, at least 5% less CPU time in a full run on an idle host: group 3.
- Criterion 5, the median of `Tests & Coverage` does not rise: group 1 records the median before. Pending a person: the median after the merge, because only runs of `main` show it (see Workflow follow-up in `tasks.md`).

## Impact

- Files that group 3 can change, by candidate: `pyproject.toml`, `.github/workflows/ci.yml`, `tests/conftest.py`, `tests/support/`, or the top-level imports of the test modules. `design.md` lists the candidates.
- Existing code and tests that must stay green: `tests/commands/test_test_selection.py` pins the `addopts` and the pytest command of the `test` gate. `tests/invariants/test_hermetic_floor.py` pins the hermetic floor, so a fixture of the floor stays. `tests/support/check_test_settings.py` checks the timeout settings and the conftest environment. `tests/support/typer_commands.py` and the garbage collector threshold in `tests/conftest.py` are earlier cuts of repeated work (#1725, #2764): keep them.
- The scratch plugin that measures is not committed. It lives in `.data/agent/scratch/`.

## Feasibility

All commands ran on 2026-11-01 in a worktree of `origin/main` (1c20865a) on a 16-CPU host. The host was not idle (see the last item), so the numbers below show the mechanism and not the final figures.

- The suite size changed. `uv run pytest --collect-only -q -n 0 tests` printed `15756/15801 tests collected (45 deselected) in 28.62s`. The issue says 11,282 tests and 9 s.
- The premise "a test body pays the first import of the heavy libraries" is false for the four libraries that the first plan named. A script that runs the collection and then lists `sys.modules` printed `pydantic_ai True`, `anthropic True`, `kubernetes True` and `textual True` after collection and before any test. `git grep -lE "^(import|from) (pydantic_ai|anthropic|kubernetes|textual)\b" -- tests` lists 43 test modules, so every worker imports them while it collects. The libraries `google.genai`, `openai`, `agentops`, `litellm` and `libtmux` were not in `sys.modules` after collection. Group 1 finds out whether a test body imports them.
- A fixture that imports a module once per worker cannot lower the total CPU time. The worker imports the module once in both cases. It only moves the cost to another place. So the preload fixture cannot meet criterion 4. `design.md` rejects it with this evidence.
- Collection is repeated work. A worker collects the whole suite. In one process, `python -I -X importtime` over the collection printed `collect wall 19.0 cpu 19.0` and `cProfile` printed `41.084 seconds` with profile overhead. In that profile, `_pytest/fixtures.py:2155(_matchfactories)` had 853,589 calls and `process_argname` 1,564,991 calls. `grep -c "autouse" tests/conftest.py` prints 29. Imports are about 3 s of the 19 s (`importtime` self times, sum 2.7 s). So the cost of collection is mostly in building the fixture closure of 15,801 tests, and not in imports.
- Nothing newer removed the work. `git log origin/main` shows #2764 (`perf(ci): cut test job time and guard its mean`), which cut the cache build, the garbage collector, the shutdown polls and the Typer command build. It touched none of collection, the worker count or the first imports. Issue #2809 (`fix(k8s): bound the test workers`, commit 2314ef98) sets `PYTEST_XDIST_AUTO_NUM_WORKERS=2` in the runner pod (`k8s/devops/cronjob-runner.yaml:72`). A Job that implements this plan therefore runs 2 workers on 2 CPUs. It cannot measure the split of 16 workers. Task 1.3 stops in that case and names it as an open point. The open issues #2369 (startup-import tests) and #2373 (coverage cost) are separate work.
- The worker setting is `addopts = "-n logical --dist worksteal ..."` at `pyproject.toml:199`. The `Tests & Coverage` job runs `uv run devops ci --check --no-cache --only test` (`.github/workflows/ci.yml:146`) and so uses `-n logical` on the 4-CPU runner.
- The method works. A scratch plugin with the hooks `pytest_sessionstart`, `pytest_collection_finish`, `pytest_runtest_logstart` and `pytest_runtest_logreport` wrote one line for each of four workers: `{"worker": "gw2", "collection_wall_s": 0.15, "start_to_first_test_wall_s": 0.28, "busy_s": 1.81, "cpu_total_s": 2.02}`. The shell `time` of the controller counts the CPU time of the workers: `real 15.874s user 38.393s sys 3.931s`.
- The runner baseline moved. `uv run devops ci job-time` printed `the last 10 runs of Tests & Coverage took 376 s on average, and the limit is 300 s`. The issue says a median of 291 s. Criterion 5 therefore compares with the median that group 1 records now, and not with 291 s.
- The host is not idle. `uptime` printed `load average: 14.51, 23.42, 23.29` and, later, `5.36, 17.92, 21.34`. Criterion 1 needs a load under 2 before each run. Group 1 waits for that load, and the pull request stays a draft when the host never reaches it.

## Existing Tool Considered

`pytest-xdist` is in use and has the options `-n` and `--maxprocesses`. `pytest --durations=0` and `pytest -v` give the seconds and the worker of each test. `python -X importtime` lists the cost of each import. `cProfile` from the standard library shows where a collection spends its time. The shell `time` gives user and system CPU time of a process and its children. The plugin hooks of pytest give the start, collection and busy time of a worker, in a scratch file of about 40 lines that is not committed. The change builds no tool. The change deletes no internal code.
