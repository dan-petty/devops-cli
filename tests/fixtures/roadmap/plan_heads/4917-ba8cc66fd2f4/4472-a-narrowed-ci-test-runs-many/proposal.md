# Proposal

## Why

A narrowed `devops ci test` run picked its worker count from the number of test files, so a selection of a few files that hold many slow tests ran serially and hit the 1800 s timeout of the command (#4472). The run must size its workers from the tests that it selects, so a selection of many slow tests ends well inside that timeout.

## What Changes

- `src/devops_cli/ci/test_workers.py` gains `collection_argv`, a pure builder of the serial collection command for a narrowed run's target list and keyword filter.
- `_narrowed_workers` in `src/devops_cli/commands/ci.py` chooses the workers of a narrowed run from the number of tests that the selection collects, and reads the file count only when the collection fails.
- `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` joins `src/devops_cli/config/defaults.py` at 50 collected tests; `DEFAULT_CI_TEST_SERIAL_MAX_FILES` keeps 12 and `DEFAULT_CI_TEST_NARROWED_WORKERS` keeps 4.
- `src/devops_cli/lang/en/messages.py` gains the warning that names a failed collection, and `src/devops_cli/lang/en/help.py` states the collected-test rule of `-n`.
- The count of collected tests reuses the `collected_items` counter of the implement step, so the change writes no second counter.
- `tests/commands/test_test_selection.py` scripts the collection and asserts the worker choice, the keyword filter, the fallback and the runs that make no collection call.
- `tests/commands/test_ci.py` and `tests/commands/test_ci_repeat.py` skip a collection call when they read the pytest run.
- `docs/TESTING.md` states the collected-test rule, and the regenerated `docs/CLI_REFERENCE.md` and `docs/commands/ci.md` carry the new `-n` help.
- A given `-n`, a run with no paths, a dry run and a `--repeat` run make no collection call and keep their worker choice.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ci-test-workers`: Collected tests choose the workers, Small selections stay serial, Keyword filter changes the count, Collection uses the run selection, Collection failure falls back, Explicit workers win, Full suite keeps addopts

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ci/test_workers.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/TESTING.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`
- Tests: `tests/ci/test_test_workers.py`, `tests/commands/test_test_selection.py`, `tests/commands/test_ci.py`, `tests/commands/test_ci_repeat.py`

## Feasibility

- `read_file` on `src/devops_cli/commands/ci.py` lines 1815-1935 showed `src/devops_cli/commands/ci.py:1830:if len(targets) <= DEFAULT_CI_TEST_SERIAL_MAX_FILES:` and `src/devops_cli/commands/ci.py:1832:return str(DEFAULT_CI_TEST_NARROWED_WORKERS)`, so a narrowed run given no `-n` picks its workers from the number of target paths and from nothing else.
- `read_file` on `src/devops_cli/config/defaults.py` lines 472-490 gave the staged values `src/devops_cli/config/defaults.py:482:DEFAULT_CI_TEST_SERIAL_MAX_FILES: Final[int] = 12` and `src/devops_cli/config/defaults.py:483:DEFAULT_CI_TEST_NARROWED_WORKERS: Final[int] = 4`, and the plan adds `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` at 50 collected tests beside them.
- `read_file` on `src/devops_cli/commands/ci.py` showed `src/devops_cli/commands/ci.py:1910:workers = numprocesses if numprocesses is not None else _narrowed_workers(targets)`, so a given `-n` already wins; the plan keeps that order and makes no collection call when a given `-n` is present.
- `read_file` on `src/devops_cli/commands/ci.py` showed `src/devops_cli/commands/ci.py:1907:_run_shuffled_repeats(_build_test_cmd("0", verbose, k, x, None), targets, repeat, seed)`, so a `--repeat` run returns before the worker choice and keeps its serial shuffled order.
- `read_file` on `src/devops_cli/commands/ci.py` showed `src/devops_cli/commands/ci.py:1815:cmd.extend(["-k", k])`, so the run's keyword filter is one option of the command the collection must repeat.
- `read_file` on `src/devops_cli/roadmap/implement/implement_test_form.py` showed `src/devops_cli/roadmap/implement/implement_test_form.py:85:def collected_items(output: str) -> int:` and `src/devops_cli/roadmap/implement/implement_test_form.py:48:_ITEM_MARK: Final[str] = "::"`, so the counter reads the quiet collection's lines that hold a test id; `src/devops_cli/roadmap/implement/implement_step.py:1441:collected = collected_items(done.stdout)` shows the implement step already counts a collection with it, and the plan imports that function instead of writing a counter.
- `references` for `collected_items` answered 4 files: `src/devops_cli/roadmap/implement/implement_step.py` (lines 150, 1441), `src/devops_cli/roadmap/implement/implement_test_form.py` (lines 5, 85, 91), `tests/roadmap/implement/test_roadmap_implement_test_form.py` and an archive task file. The three outside the archive stay unchanged, and the decisions say why: the function keeps its home, its one caller and its tests.
- `read_file` on `tests/support/session_spawns.py` showed `tests/support/session_spawns.py:53:return b"", b""`, so a child doubled with `record_spawns` answers an empty collection and counts zero; the tests that need a counted collection answer it through `process_fake` instead, whose answer carries output, as `tests/commands/test_ci.py:1787:ProcessAnswer(stdout=report, delay=duration)` shows.
- `read_file` on `tests/commands/test_test_selection.py` showed `tests/commands/test_test_selection.py:72:return [list(call.argv) for call in process_fake.calls if "pytest" in call.argv]` and `tests/commands/test_test_selection.py:569:assert (exit_code, [_worker_options(spawn.argv) for spawn in spawns]) == (0, [workers])`; both take the first pytest child as the run, so each must skip a child that holds `--collect-only`.
- `read_file` on `tests/commands/test_ci.py` showed `tests/commands/test_ci.py:68:pytestmark = pytest.mark.usefixtures("refuse_nested_test_runs")` and the two hooks `tests/commands/test_ci.py:2494:spawns = record_spawns(monkeypatch, on_communicate=outlive_the_timeout)` and `tests/commands/test_ci.py:2527:record_spawns(monkeypatch, on_communicate=record_handlers)`; each hook answers every child, so each must let the collection through with exit 0, and the timeout case reads the run's child and not the collection's.
- `read_file` on `tests/commands/test_ci.py` showed `tests/commands/test_ci.py:1887:runs = [call for call in process_fake.calls if "pytest" in call.argv]`, and `tests/commands/test_ci_repeat.py:198:[cmd for cmd, _cwd in calls],` compares the whole call list with one run, so both filter a collection call out.
- `read_file` on `tests/commands/test_ci.py` showed the live driver `tests/commands/test_ci.py:2603:[str(devops), "ci", "test", "tests/test_x.py"],`, whose `uv` is a fake on PATH that waits for a signal; the driver passes `-n 2`, so it makes no collection call and the signal reaches the run.
- `read_file` on `src/devops_cli/lang/en/help.py` line 772 showed `src/devops_cli/lang/en/help.py:773:"Number of parallel worker processes. Unset, a run narrowed to a few test files runs "`, and `search_code` for `Number of parallel worker processes` showed the same text generated into `docs/CLI_REFERENCE.md` and `docs/commands/ci.md`, so the help text is the source of both documents.
- `search_code` for `DEFAULT_CI_TEST_SERIAL_MAX_FILES` returned `docs/TESTING.md:160:where starting xdist workers costs more than it saves`, the sentence of the file-count rule that this change replaces.
- `read_file` on `src/devops_cli/lang/en/messages.py` line 1775 showed `src/devops_cli/lang/en/messages.py:1775:repeat_seed_unavailable: str = "Could not read HEAD to derive a shuffle seed; pass --seed."`, beside which the fallback warning joins the same CI messages.
- The probe lines that confirm the cited paths, word for word: The path `src/devops_cli/commands/ci.py` is a file of the staging commit. The path `tests/roadmap/implement/test_roadmap_implement_job.py` is a file of the staging commit. The path `test_roadmap_implement_step.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/implement/test_roadmap_implement_step.py`. No commit in the history deleted or renamed it.
- The probes say `Not probed, the bound of 10 commands is reached: src/devops_cli/config/defaults.py, it.policy, _narrowed_workers, DEFAULT_CI_TEST_SERIAL_MAX_TESTS, addopts`; this run read `src/devops_cli/config/defaults.py`, `_narrowed_workers` and the collection rule with `read_file`, `search_code` and `references`, and `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` is a constant this change creates, so no probe can hold it.
- Not checked by this run: the reproduction on a loaded host, the elapsed 30 m 2 s and the count of 399 tests over the seven files; no tool of this run starts a test suite, so those numbers stand as the issue's report and the plan repeats no timing claim.
- The first check against the real system is the census of the issue's selection: `uv run pytest --collect-only -q -n 0 tests/roadmap/implement/test_roadmap_implement_extension.py tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_job_extension.py tests/roadmap/implement/test_roadmap_implement_limits.py tests/roadmap/implement/test_roadmap_implement_step.py tests/roadmap/implement/test_roadmap_implement_tool_log.py tests/roadmap/test_roadmap_mcp.py`. Its count is unverified by this run; the implementation stops when the count differs from the issue's 399.
- The second check is `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`, which must print the collected count in its warning-free path and run on `DEFAULT_CI_TEST_NARROWED_WORKERS`, so the collection the command runs is the collection a person can run.
- The reply answers the problem with three corrections: the docs citation now quotes `docs/TESTING.md:160:where starting xdist workers costs more than it saves`, a substring of the staged line; `src/devops_cli/roadmap/implement/implement_test_form.py` leaves `what_changes`, because no group changes it; and the only value the plan states for `DEFAULT_CI_TEST_SERIAL_MAX_FILES` is 12, the staged value.
- The program the change adds is the collection command `uv run pytest --collect-only -q -n 0 <targets> [-k <filter>]`. `uv` and `pytest` are runner tools of the image, not `NOT_IN_RUNNER`. Its failure classes are `test`, when the collection exits non-zero and the command falls back to the file-count rule, and `timeout`, when it passes `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`; the command catches both and continues.
- The pod settings that apply to that program: `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`. A collection-only run writes no file outside the checkout, so the read-only root filesystem suits it.
- `_run_in_own_session`, which the plan calls to start the collection, needs a checkout of the repository as its precondition; it needs no client of a service and no network of its own, and `uv` reaches a network only when the environment is not yet built.
- `_get_project_root`, which the plan calls to name the checkout of the collection, needs a checkout of the repository as its precondition; it needs no client of a service and no network.
- `collected_items`, which the plan calls on the collection output, takes text alone: it needs no checkout, no client of a service and no network.
- `collection_argv`, which the plan calls to build the collection command, takes a list of paths and a filter alone: it needs no checkout, no client of a service and no network.

## Existing Tool Considered

The issue's alternatives check records `pytest-xdist` as the tool in use, and no other open, maintained tool sizes the workers of a run from the tests it selects. The change keeps xdist and adds a small policy of its own: about 2,000 tokens to write, 4,000 tokens to keep and fix, and half a day of elapsed time. It deletes no internal code: `_narrowed_workers` keeps its name and gains the collected count, and the file-count constant stays as the fallback bound.

## Dependencies

- Pull request #4898 also changed `src/devops_cli/commands/ci.py` and has merged, so this change rebases on it and waits for nothing.
