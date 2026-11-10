# Proposal

## Why

The implement job ticks a task when its group changed the named files and its tests pass, so a test that collects eleven cases passes a task that names six, and the job reports a success that it did not check. #3451

## What Changes

- Add `src/devops_cli/roadmap/implement/implement_test_form.py`, which reads the test file and the case count that a task names and counts the items of a pytest collection.
- Add `BIN_PYTEST` to `src/devops_cli/config/commands.py` and the mismatch text to `src/devops_cli/lang/en/messages.py`.
- Add the form check to `_exit_failure` in `src/devops_cli/roadmap/implement/implement_step.py`, after the verification commands and before the base replay.
- Add `tests/roadmap/implement/test_roadmap_implement_test_form.py` for the reader and `tests/roadmap/implement/test_roadmap_implement_step_test_form.py` for the replay of a mismatched group.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: A step reads the test form that a task names, A step refuses a test that does not match the form of its task, A step records the form check in its trace

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_test_form.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_test_form.py`, `tests/roadmap/implement/test_roadmap_implement_step_test_form.py`

## Feasibility

- The probe line reads: The path `tests/output/test_network_table_color.py` is a file of the staging commit.
- The probe line reads: The path `openspec/changes/archive/2026-11-04-2646-the-network-table-colors-a-safe/tasks.md` is a file of the staging commit.
- The probe line reads: The path `implement_test_names.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_test_names.py`. No commit in the history deleted or renamed it.
- The probe line reads: Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it, and `list_files` shows `src/devops_cli/roadmap/implement/implement_test_names.py` in the tree of the staging commit.
- The delivered test is parametrized at the staging commit, so the loop of the issue text is no longer in the tree: `tests/output/test_network_table_color.py:23:@pytest.mark.parametrize(` and `tests/output/test_network_table_color.py:26:def test_the_network_table_colors_a_status_by_its_risk(status: str, expected_cell: str) -> None:`.
- The task still names six cases: `openspec/changes/archive/2026-11-04-2646-the-network-table-colors-a-safe/tasks.md:7:with one parametrized test over six statuses`.
- `read_file` shows eleven entries in `STATUS_CELLS` of `tests/output/test_network_table_color.py` between line 9 and line 19. No tool counted that set, so the count of eleven is unverified, and the check compares the named count with the collection at run time and not with a count in this plan.
- The step has no form check today: `src/devops_cli/roadmap/implement/implement_step.py:1438:early = _format_failure(source, changed, log.trace)` runs the verification commands and `src/devops_cli/roadmap/implement/implement_step.py:1446:static = _static_failure(source, changed, log.trace)` runs the static checks.
- The failure seam carries a class and a repair path: `src/devops_cli/roadmap/implement/implement_step.py:1298:reason: str` and `src/devops_cli/roadmap/implement/implement_step.py:1299:repair_paths: frozenset[str] | None = None`.
- The trace seam exists: `src/devops_cli/roadmap/implement/implement_trace.py:134:def check(self, command: str, status: int | None) -> None:`.
- The command runner already records a check event and runs a command outside the agent shell: `src/devops_cli/roadmap/implement/implement_step.py:1066:done = run_subprocess(list(argv), cwd=source, quiet=True, timeout=limit)`.
- The task text and its code spans are already parsed: `src/devops_cli/roadmap/step_files.py:83:return tuple(dict.fromkeys(p for task in self.tasks for p in task.paths))`, and a task holds its text at `src/devops_cli/roadmap/step_files.py:45:text: str`.
- A test path is decided by `src/devops_cli/ci/fail_to_pass.py:190:def is_test_file(path: PurePosixPath) -> bool:`.
- The command bound of the trace is `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS` with the value 160, at `src/devops_cli/config/constants.py:3424:CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS: Final[int] = 160`.
- The programs are `BIN_UV` with the value `uv`, at `src/devops_cli/config/commands.py:52:BIN_UV: str = "uv"`, and `BIN_PYTEST` with the value `pytest`, which the change adds beside `BIN_RUFF` with the value `ruff` at `src/devops_cli/config/commands.py:46:BIN_RUFF: str = "ruff"`.
- `run_subprocess` gets `cwd=source`, so the collection call needs a checkout of the repository.
- The new command is `uv run pytest --collect-only -q` on the named test file. `pytest`, `uv` and `devops` are runner tools of the image. Its failure class is `test`, whose action is `repair`, and a collection that times out is `timeout`, whose action is `retry`.
- The pod settings that apply are `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`. The checkout is writable, and `.gitignore:37:.pytest_cache/` keeps the pytest cache out of the commit.
- The verify program of each group is `uv run devops ci test`, whose programs `uv` and `devops` the image holds, and its failure class is `test`.
- The first checks against the real system are `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_test_form.py`, then `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_test_form.py`.
- The premise holds in the count and not in the loop: the step reads no test form, and the gap of six named cases against the delivered cases is what the plan closes.

## Existing Tool Considered

pytest (pytest-dev/pytest, MIT, maintained) collects one item for each parametrized case and one item for a loop over the same cases, so one collection run tells the two forms apart. It reads no task text, so the change builds a reader of the named test file and the named case count: 30k tokens to build, 5k tokens a month to keep and fix, and 72 hours of elapsed time. The change deletes no internal code.

## Dependencies

None.
