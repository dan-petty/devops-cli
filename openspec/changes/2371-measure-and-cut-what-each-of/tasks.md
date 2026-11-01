# Tasks

## 1. Measure the split, and rank the first imports

Reads: `pyproject.toml` (`addopts`, line 199), `tests/commands/test_cli_startup_imports.py` (`CONST_CLI_HEAVY_MODULES`, lines 19 to 32). Changes: scratch files in `.data/agent/scratch/` only. No file under git changes in this group.

- [ ] 1.1 Verify the method on a small selection. Write a scratch plugin `.data/agent/scratch/workersplit.py` with the hooks `pytest_sessionstart`, `pytest_collection_finish`, `pytest_runtest_logstart`, `pytest_runtest_logreport` and `pytest_sessionfinish`. For each xdist worker it appends one JSON line with the CPU time at the start of the session (`time.process_time()`, which counts the start of the interpreter and the imports before it), the time of the collection, the time to the first test, the busy time and the CPU time in total. A second hook records, after each test, the heavy modules that are new in `sys.modules` and the CPU time of that test. Run `PYTHONPATH=.data/agent/scratch WORKERSPLIT_OUT=.data/agent/scratch/split.jsonl uv run pytest -p workersplit -n 4 -q tests/watchers`, and verify that `split.jsonl` holds four lines, one for each worker
- [ ] 1.2 Record the baseline of the runner. Run `uv run devops ci job-time` and write the mean and the median of `Tests & Coverage` of the last ten runs in the notes file `.data/agent/scratch/2371-measurement.md`
- [ ] 1.3 Run the full suite three times on an idle host. Before each run, wait until the first load average in `uptime` is under 2 and write the `uptime` line in the notes file. Run `bash -c 'time uv run pytest -p workersplit'` with the scratch plugin. Write the `user` plus `sys` time of each run, and the lines of `split.jsonl` of each run, in the notes file. The result is the split of criterion 1. If the load stays over 2, stop, leave the pull request a draft and name this task as the open point
- [ ] 1.4 Rank the first imports. From the heavy-module records of the three runs, list the modules that a test body imports for the first time, with the CPU time of the test that imported each one. For each of the top five, run `uv run python -X importtime -c 'import <module>'` and write its import time in seconds. Write the ranked list in the notes file. The result is the list of criterion 2

## 2. Choose the change with the largest share

Reads: the notes file of group 1, `design.md` (table of candidates). Changes: the notes file.

- [ ] 2.1 For each row of the table in `design.md` except the rejected one, compute the CPU time it can remove from the figures of group 1, as the formula of its last column gives. Write the share of each row in the notes file, and the row with the largest share. If no row reaches 5% of the total CPU time, follow the stop rule in `design.md` and do not go on to group 3. Verify that the notes file names one row and gives its figures
- [ ] 2.2 Verify the choice against the existing code. For the chosen row, list in the notes file the tests that pin its files (`uv run devops ci test tests/commands/test_test_selection.py tests/invariants/test_hermetic_floor.py`) and run them on the unchanged tree. Verify that they pass

## 3. Apply the chosen change and measure again

Reads: the files of the chosen row in `design.md`. `tests/conftest.py` is about 47 KB, so read only the fixtures that the numbers name. Changes: the files of the chosen row, and `docs/TESTING.md`.

- [ ] 3.1 Apply the chosen row in its files. Change the pin in `tests/commands/test_test_selection.py` in the same commit when the change alters `addopts`. Verify that `uv run devops ci test tests/commands/test_test_selection.py tests/invariants/test_hermetic_floor.py tests/support` passes
- [ ] 3.2 Run the full suite three times on an idle host with the command of task 1.3. Write the `user` plus `sys` time of each run in the notes file, and the change against the baseline. Verify that the mean CPU time is at least 5% lower than in group 1. If it is not, follow the stop rule in `design.md`
- [ ] 3.3 Verify that the full suite passes as the CI job runs it: `uv run devops ci --check --no-cache --only test`. Verify that `uv run devops ci test-settings` passes
- [ ] 3.4 Write the result in the `Run time` part of `docs/TESTING.md` and in the comment above the setting that the change touches: the lever, the CPU time before and after, and the date. Verify that `uv run devops docs generate --sync-readme` leaves no diff and that `uv run devops ci docs` passes
- [ ] 3.5 Put the notes of the three groups in the body of the pull request: the split of each worker for the three runs, the ranked first imports, the lever and the reason why it has the largest share, and the CPU time before and after. Verify that the body holds each of the five criteria of the issue with its figure

## Workflow follow-up

- Pending a person: after the merge, read `uv run devops ci job-time` once ten runs of `main` have the change. The median of `Tests & Coverage` must not be above the median that task 1.2 recorded.
