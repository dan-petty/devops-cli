# Tasks

## 1. Add the collection command builder

Reads: `src/devops_cli/ci/__init__.py`, `src/devops_cli/commands/ci.py`. Changes: `src/devops_cli/ci/test_workers.py` (new), `tests/ci/test_test_workers.py` (new).

- [ ] 1.1 Add the failing test `tests/ci/test_test_workers.py::test_the_collection_command_carries_the_run_targets_and_the_keyword_filter` for the collection command of a narrowed run
  - Verification: `$ uv run devops ci test tests/ci/test_test_workers.py` fails on the base
- [ ] 1.2 Write the test first in `tests/ci/test_test_workers.py`. It asserts that `collection_argv` answers `uv run pytest --collect-only -q -n 0`, then `--` and the two target paths, that it puts `-k slow` before `--` when the filter is given, and that it holds no `-k` when the filter is None. Then add `collection_argv(targets, keyword)` to `src/devops_cli/ci/test_workers.py`, with a docstring that says it builds the command of a narrowed run's collection and does no I/O
  - Verification: `$ uv run devops ci test tests/ci/test_test_workers.py` passes

## 2. Choose a narrowed run's workers from the collected tests

Reads: `src/devops_cli/ci/test_workers.py`, `src/devops_cli/roadmap/implement/implement_test_form.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_test_selection.py`, `tests/support/fakes/process.py`. Changes: `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_test_selection.py`.

- [ ] 2.1 Add the failing case `tests/commands/test_test_selection.py::test_a_selection_past_the_collected_test_limit_runs_on_the_capped_workers`, and replace `tests/commands/test_test_selection.py::test_a_selection_past_the_serial_limit_runs_on_the_capped_workers` with it, because the file count no longer decides alone
  - Verification: `$ uv run devops ci test tests/commands/test_test_selection.py` fails on the base
- [ ] 2.2 Write the failing cases first in `tests/commands/test_test_selection.py`. Import `ProcessAnswer` beside `ProcessFake`, and make `_pytest_runs` and `_started_runs` skip a child that holds `--collect-only`. Answer the collection with `process_fake.answer` and a matcher on `--collect-only` whose `ProcessAnswer` stdout holds one test id on each line: a collection of `DEFAULT_CI_TEST_SERIAL_MAX_TESTS + 1` ids runs on `DEFAULT_CI_TEST_NARROWED_WORKERS`, a collection of `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` ids runs serially, a collection that exits 5 runs serially, a collection that exits non-zero over 13 modules prints the warning and uses the file-count rule, a `-k slow` selection passes `-k slow` to the collection and to the run, a given `-n` makes no collection call, and a run with no paths makes none. Then add `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` at 50 beside the file-count constant, with a comment that states the rule. Add the fallback warning to the CI messages beside `repeat_seed_unavailable`. Add `_collected_test_count(targets, keyword)` beside `_narrowed_workers`: it returns None in a dry run, builds the command with `collection_argv`, starts it with `asyncio.run(_run_in_own_session(...))` and `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`, returns None on `subprocess.TimeoutExpired` and on any exit code except 0 and 5 with the warning printed, and otherwise counts the output with `collected_items`. Give `_narrowed_workers(targets, collected)` the collected count, and keep the count of test modules for the None case. Rewrite the `-n` help text to say that the collected tests choose the workers
  - Verification: `$ uv run devops ci test tests/commands/test_test_selection.py` passes

## 3. Skip the collection when the driving tests read the pytest run

Reads: `tests/commands/test_ci.py`, `tests/commands/test_ci_repeat.py`, `tests/support/session_spawns.py`, `tests/support/fakes/process.py`. Changes: `tests/commands/test_ci.py`, `tests/commands/test_ci_repeat.py`.

- [ ] 3.1 In `tests/commands/test_ci.py`, let the hooks of `record_spawns` return at once for a child that holds `--collect-only`, so the collection exits 0 and counts zero, and read the run's child in the timeout case by skipping the collection child. Drop a call that holds `--collect-only` from `runs` in `test_staged_sources_select_the_worktrees_tests`. Add `-n 2` to the argv of `_devops_ci_test`, so the live signal cases make no collection call. In `tests/commands/test_ci_repeat.py`, drop a call that holds `--collect-only` from the calls that `_invoke` returns
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py tests/commands/test_ci_repeat.py` passes

## 4. Describe the collected-test worker rule in the docs

Reads: `docs/TESTING.md`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`. Changes: `docs/TESTING.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`.

- [ ] 4.1 Replace the file-count sentence of `docs/TESTING.md` with the collected-test rule: the collection command, the threshold of 50 collected tests, the `-k` filter, the fallback on a collection failure, and the runs that make no collection call. State that a test that drives the command answers the collection through the process edge it already doubles. Then regenerate the CLI reference with `uv run devops docs generate --sync-readme`, which writes `docs/CLI_REFERENCE.md` and `docs/commands/ci.md` from the changed help text
  - Verification: `$ uv run devops ci docs` passes
- [ ] 4.2 Edit `docs/TESTING.md` and regenerate `docs/CLI_REFERENCE.md` and `docs/commands/ci.md` with `uv run devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
