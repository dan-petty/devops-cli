# Proposal

## Why

A narrowed `devops ci test` run chose its worker count from the number of test files, so a selection of 7 files that hold 399 slow tests ran serially and hit the 1800 s timeout. The run sizes its workers from the tests that it selects, so that selection runs in parallel and ends inside the timeout (#4472).

## What Changes

- `_narrowed_workers` in `src/devops_cli/commands/ci.py` chooses the workers of a narrowed run from the number of tests that the selection collects, and reads the file count only when the collection fails or a dry run makes no collection call.
- `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` joins `src/devops_cli/config/defaults.py` at 50 collected tests; `DEFAULT_CI_TEST_SERIAL_MAX_FILES` keeps 12 as the fallback bound and `DEFAULT_CI_TEST_NARROWED_WORKERS` keeps 4.
- `_collection_cmd` reuses the existing `_build_test_cmd` and adds `--collect-only -q`, so the collection carries the same target list and `-k` filter as the run.
- The count of collected tests reuses the existing `collected_items` helper, so the change writes no second counter.
- A collection that exits 5, no tests collected, is a count of zero, so the run is serial and no warning is printed.
- `src/devops_cli/lang/en/messages.py` gains the warning that names a failed collection, and `src/devops_cli/lang/en/help.py` states the collected-test rule of `-n`.
- `tests/commands/test_test_selection.py` scripts the collection and asserts the worker choice, the keyword filter, the fallback, the empty collection and the runs that make no collection call.
- The fallback case selects 13 target files, where the file-count rule gives `DEFAULT_CI_TEST_NARROWED_WORKERS` while a count of zero gives `-n 0`, so one test shows which rule chose the workers.
- `tests/commands/test_ci.py` and `tests/commands/test_ci_repeat.py` skip a collection call when they read the pytest run.
- `docs/TESTING.md` states the collected-test rule, and the regenerated `docs/commands/ci.md` carries the new `-n` help.
- A given `-n`, a run with no paths, a dry run and a `--repeat` run make no collection call and keep their worker choice.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ci-test-workers`: Collected tests choose the workers, Small selections stay serial, Keyword filter changes the count, Collection uses the run selection, Collection failure falls back, Explicit workers win, Full suite keeps addopts

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/TESTING.md`, `docs/commands/ci.md`
- Tests: `tests/commands/test_test_selection.py`, `tests/commands/test_ci.py`, `tests/commands/test_ci_repeat.py`

## Feasibility

- `read_file` on `src/devops_cli/commands/ci.py` lines 1890-2060 showed `src/devops_cli/commands/ci.py:1940:if len(targets) <= DEFAULT_CI_TEST_SERIAL_MAX_FILES:` and `src/devops_cli/commands/ci.py:1942:return str(DEFAULT_CI_TEST_NARROWED_WORKERS)`, so the staged file-count rule gives `-n 0` for up to 12 target paths and `-n 4` above them.
- The review finding is fixed at its place: both cited lines lie inside the range that this run read, `read_file` on `src/devops_cli/commands/ci.py` lines 1890-2060, which showed `src/devops_cli/commands/ci.py:2020:workers = numprocesses if numprocesses is not None else _narrowed_workers(targets)`, so a given `-n` already wins, and `src/devops_cli/commands/ci.py:2017:_run_shuffled_repeats(_build_test_cmd("0", verbose, k, x, None), targets, repeat, seed)`, so a `--repeat` run returns before the worker choice.
- `read_file` on `src/devops_cli/commands/ci.py` lines 1890-2060 showed `src/devops_cli/commands/ci.py:1925:cmd.extend(["-k", k])` and `src/devops_cli/commands/ci.py:1929:cmd.extend(targets)`, so the run's keyword filter and its targets are the two parts the collection must repeat.
- `read_file` on `src/devops_cli/config/defaults.py` lines 480-505 gave the staged values `src/devops_cli/config/defaults.py:494:DEFAULT_CI_TEST_SERIAL_MAX_FILES: Final[int] = 12` and `src/devops_cli/config/defaults.py:495:DEFAULT_CI_TEST_NARROWED_WORKERS: Final[int] = 4`; the plan adds `DEFAULT_CI_TEST_SERIAL_MAX_TESTS: Final[int] = 50` beside them, and the staged tree defines no value for it, so no probe can hold it.
- `read_file` on `src/devops_cli/roadmap/implement/implement_test_form.py` lines 80-95 showed `src/devops_cli/roadmap/implement/implement_test_form.py:85:def collected_items(output: str) -> int:` and `src/devops_cli/roadmap/implement/implement_test_form.py:88:return sum(1 for line in output.splitlines() if _ITEM_MARK in line)`, so that function counts the test ids of a quiet collection and needs no second implementation; `search_code` for `def collected_items` showed that line as its only definition.
- `read_file` on `tests/support/fakes/process.py` lines 40-70 showed `tests/support/fakes/process.py:49:class ProcessAnswer:`, so a scripted collection answer exists in the process fake.
- `read_file` on `tests/support/session_spawns.py` lines 40-60 showed `tests/support/session_spawns.py:53:return b"", b""`, so a child doubled with `record_spawns` answers an empty collection and counts zero.
- `search_code` for `def _pytest_runs` showed `tests/commands/test_test_selection.py:70:def _pytest_runs(process_fake: ProcessFake) -> list[list[str]]:`, `search_code` for `def _started_runs` showed `tests/commands/test_test_selection.py:532:def _started_runs(`, and `search_code` for `test_a_selection_past_the_serial_limit_runs_on_the_capped_workers` showed `tests/commands/test_test_selection.py:572:def test_a_selection_past_the_serial_limit_runs_on_the_capped_workers(`, so the helper that the plan edits and the case that it replaces exist as named.
- `search_code` for `for call in process_fake.calls if "pytest" in call.argv` showed `tests/commands/test_ci.py:1947:runs = [call for call in process_fake.calls if "pytest" in call.argv]`, `search_code` for `def _run_recording_handlers` showed `tests/commands/test_ci.py:2555:def _run_recording_handlers(`, `search_code` for `def _devops_ci_test` showed `tests/commands/test_ci.py:2626:def _devops_ci_test(` and `search_code` for `def test_the_gate_and_a_plain_run_stay_in_file_order` showed `tests/commands/test_ci_repeat.py:188:def test_the_gate_and_a_plain_run_stay_in_file_order(`, so group 2 names helpers that the staged tree holds.
- `search_code` for `Number of parallel worker processes` showed `src/devops_cli/lang/en/help.py:891:"Number of parallel worker processes. Unset, a run narrowed to a few test files runs "` and the same text generated into `docs/commands/ci.md`, so the `-n` help states the file-count rule and must state the collected-test rule.
- `search_code` for `runs serially for up to` showed `docs/TESTING.md:170:- Given no `-n`, a narrowed `devops ci test` runs serially for up to `DEFAULT_CI_TEST_SERIAL_MAX_FILES` test modules`, the sentence of the file-count rule that this change replaces, and the released history line of `CHANGELOG.md:3341`.
- The probe lines that confirm the cited paths, word for word: The path `src/devops_cli/commands/ci.py` is a file of the staging commit. The path `tests/roadmap/implement/test_roadmap_implement_job.py` is a file of the staging commit. The path `test_roadmap_implement_step.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/implement/test_roadmap_implement_step.py`. No commit in the history deleted or renamed it.
- The probes say `Not probed, the bound of 10 commands is reached`; this run read `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/roadmap/implement/implement_test_form.py`, `tests/support/fakes/process.py` and `tests/support/session_spawns.py` with `read_file`, and `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` is a constant this change creates, so no probe can hold it.
- Not checked by this run: the reproduction on a loaded host, the elapsed 30 m 2 s and the count of 399 tests over the seven files; no tool of this run starts a test suite, so those numbers stand as the issue's report and the plan repeats no timing claim.
- The first check against the real system is the census of the issue's selection: `uv run pytest --collect-only -q -n 0 tests/roadmap/implement/test_roadmap_implement_extension.py tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_job_extension.py tests/roadmap/implement/test_roadmap_implement_limits.py tests/roadmap/implement/test_roadmap_implement_step.py tests/roadmap/implement/test_roadmap_implement_tool_log.py tests/roadmap/test_roadmap_mcp.py`. Its count is unverified by this run, and the implementation stops when the count differs from the issue's 399.
- The second check is `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`, which must run on `DEFAULT_CI_TEST_NARROWED_WORKERS` when that file collects more than 50 tests, so the collection the command runs is the collection a person can run.
- The program the change adds is the collection command `uv run pytest -n 0 --collect-only -q <targets> [-k <filter>]`. `uv` and `pytest` are runner tools of the image, not `NOT_IN_RUNNER`. Its failure classes are `test`, when it exits non-zero and the command falls back to the file-count rule, and `timeout`, when it passes `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`; the command catches both and continues.
- The pod settings that apply to that program: `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`. A collection-only run writes no file outside the checkout, so the read-only root filesystem suits it.
- `_run_in_own_session`, which the plan calls to start the collection, needs a checkout of the repository as its precondition; it needs no client of a service and no network of its own, and `uv` reaches a network only when the environment is not yet built.
- `run_subprocess_async`, which `_run_in_own_session` calls to start the child, needs a checkout of the repository as its precondition; it needs no client of a service and no network of its own.
- `_get_project_root`, which the plan calls to name the checkout of the collection, needs a checkout of the repository as its precondition; it needs no client of a service and no network.
- `collected_items`, which the plan calls on the collection output, takes text alone: it needs no checkout, no client of a service and no network.
- `_build_test_cmd`, which `_collection_cmd` calls, takes the worker value, two flags, the filter and the targets alone: it needs no checkout, no client of a service and no network.

## Existing Tool Considered

`pytest-xdist` is the parallel runner the command already uses, and no open, maintained tool sizes the workers of a run from the tests it selects, so the change writes about 40 lines of policy in the command module. Cost: about 2,000 tokens to write, 4,000 tokens to keep and fix, and 4 hours of elapsed time. It deletes no internal code: the file-count rule stays as the fallback, and `_narrowed_workers` keeps its name.

## Dependencies

- Pull request #5266 changes `tests/roadmap/implement/test_roadmap_implement_job.py` and `tests/roadmap/implement/test_roadmap_implement_step.py`; no group of this change touches either file, so the overlap is no dependency and nothing waits for it.
