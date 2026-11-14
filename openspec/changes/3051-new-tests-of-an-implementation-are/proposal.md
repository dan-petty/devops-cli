# Proposal

## Why

The implement job writes tests but checks their strength nowhere: `src/devops_cli/roadmap/implement/implement_scoped_ci.py:def scoped_checks` builds the static rows and the tests, and no mutation run and no changed-line coverage. A test that asserts nothing, a mutant that no test kills and a new line that no test covers all pass the job and reach the pull request. #3051 asks the job to check the strength of the new tests before the push.

## What Changes

- Add `src/devops_cli/roadmap/implement/implement_strength.py`: the assertion scan of the new test files, the bounded mutation run, and the coverage run of the scoped test modules with its delta.
- Bound the mutation run at `roadmap.implement.command_timeout_seconds` (1800 s) and at `CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES` (30) changed source files, and name the bound and each file that the run did not test.
- Run the scoped test modules with `--cov=src --cov-report= --cov-fail-under=0`, because `devops ci test` passes no coverage option, then `uv run coverage xml -q` and diff-cover at `--fail-under 100`.
- Leave the changed files of a task group of kind `other` out of the strength check, with the group number as the reason.
- Run the strength check after the scoped checks in `_scoped_run` of `src/devops_cli/roadmap/implement/implement_run.py` and give a failed report to the existing repair loop.
- Show the strength report and the skip reason in the comment on the pull request.
- Document the strength check, its bounds and its skip in `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/repair`: The job checks the strength of the new tests, The strength check is bounded, The strength check skips the files of a group of kind other, The comment shows the strength report, The job runs the scoped checks before it pushes

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_strength.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement/implement_run.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_strength.py`

## Feasibility

- The premise holds: `read_file` of `src/devops_cli/roadmap/implement/implement_scoped_ci.py` lines 100-200 showed `src/devops_cli/roadmap/implement/implement_scoped_ci.py:156:ScopedCheck(names["tests"], (BIN_UV, "run", BIN_DEVOPS, "ci", "test", *tests))`, and no mutation run and no coverage delta beside it.
- `search_code` for `"uv", "run", "pytest"` showed `src/devops_cli/commands/ci.py:1919:cmd = ["uv", "run", "pytest"]` in `_build_test_cmd`, which adds no coverage option, and `search_code` for `addopts =` showed `pyproject.toml:228:addopts = "-n logical --dist worksteal -p no:logfire -p no:pytest_logfire -p no:randomly --hypothesis-profile=ci"` with no `--cov`.
- So the `tests` scoped check writes no coverage data, and group 3 runs the scoped test modules again with coverage on instead of reading that check's data.
- The coverage run takes the options of a shard, `--cov-report=` and `--cov-fail-under=0`, because a narrowed run measures part of the tree and must not fail the floor of the whole.
- The two report commands are those of CI: `search_code` for `diff-cover .data/coverage.xml` showed `.github/workflows/ci.yml:292:uv run diff-cover .data/coverage.xml --compare-branch=`, with `--fail-under 90`; the strength check passes `--fail-under 100`, because one uncovered changed line must fail it.
- `read_file` of `src/devops_cli/config/constants.py` lines 3560-3580 gave the staged value of the file-count bound: `src/devops_cli/config/constants.py:3571:CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES: Final[int] = 30`.
- `search_code` gave the staged value of the command bound, `src/devops_cli/config/defaults.py:1040:DEFAULT_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS: int = 1800`, and of the repair bound, `src/devops_cli/config/defaults.py:957:DEFAULT_ROADMAP_IMPLEMENT_REPAIR_ROUNDS: int = 3`; `src/devops_cli/roadmap/implement/implement_scoped_ci.py:165:limit = load_settings().roadmap.implement.command_timeout_seconds` reads the first as the bound of every scoped check.
- The probes name the two settings as identifiers, not files: "The path `roadmap.implement.command_timeout_seconds` is no file of the staging commit. No commit in the history deleted or renamed it."
- The probe line for the repair bound reads the same: "The path `roadmap.implement.repair_rounds` is no file of the staging commit. No commit in the history deleted or renamed it."
- The probes left the cited files unread: "Not probed, the bound of 10 commands is reached: `src/devops_cli/commands/ci.py`, `.ast-grep/rules/test-function-has-assertion.yml`, `tests/gate/construct_gate.py`, `.github/workflows/ci.yml`, `src/devops_cli/ci/mutate.py`, `src/devops_cli/config/constants.py`". This run read those files itself, and the reads below are its own.
- The assertion rule exists: `read_file` of `.ast-grep/rules/test-function-has-assertion.yml` lines 1-14 showed `.ast-grep/rules/test-function-has-assertion.yml:6:message: Test function has no assert, no pytest.raises, and no assertion or double check.`, and the rule below it matches the node kind `function_definition` with the name regex `^test_`.
- The mutation selection and the report parser exist: `file_symbols` of `src/devops_cli/ci/mutate.py` showed `src/devops_cli/ci/mutate.py:def select_targets` and `src/devops_cli/ci/mutate.py:def tally`, and `read_file` of lines 199-245 showed that `select_targets` returns `MutationTarget` rows and `tally` reads `mutmut results --all true`.
- The two tools are pinned dev dependencies: `search_code` for `"mutmut==` gave `pyproject.toml:120:"mutmut==3.8.1",`, and for `diff-cover==` gave `pyproject.toml:110:"diff-cover==11.0.1",`. The change adds no line to `pyproject.toml`.
- `file_symbols` of `src/devops_cli/roadmap/implement/implement_run.py` showed `_scoped_run` at line 1290, `_scoped_rounds` at 1324, `_comment` at 1531 and `_scoped_lines` at 1601; `read_file` of lines 1290-1347 showed `_scoped_run` computes the changed paths and `plan_tests`, and `_scoped_rounds` gives a failed result to `_fix` up to `roadmap.implement.repair_rounds`.
- `read_file` of `src/devops_cli/roadmap/step_files.py` lines 25-50 showed `src/devops_cli/roadmap/step_files.py:36:KIND_LINE: re.Pattern[str] = re.compile(r"^Kind: (?P<kind>\w+)\.", re.M)`, which reads the kind of a group from its task text.
- `list_files` of `src/devops_cli/roadmap/implement` and of `tests/roadmap/implement` showed the modules and the test modules that the groups read and create, and `list_files` of `docs/roadmap` showed `docs/roadmap/implement.md`.
- The earlier reply packed no file of the commit in group 3. Group 3 now names `pyproject.toml`, `src/devops_cli/commands/ci.py` and `.github/workflows/ci.yml` in its task text, and every group names a file that the commit holds.
- `select_targets(source, [], changed=True, base=base)` of `src/devops_cli/ci/mutate.py:def select_targets` needs a checkout of the repository at `source`, and no client and no network.
- `run_subprocess` for `uv run ast-grep scan`, `uv run mutmut run`, `uv run mutmut results --all true`, `uv run pytest --cov=src --cov-report= --cov-fail-under=0`, `uv run coverage xml -q` and `uv run diff-cover` needs a checkout of the repository at `source`, and no client; the programs are in the image or are console scripts of the dev group, so it needs no network.
- `plan_tests(source, changed)` of `src/devops_cli/roadmap/implement/implement_scoped_ci.py:def plan_tests` needs a checkout of the repository at `source`, and no client and no network.
- `tally(results_text, targets)` and `parse_task_groups(text)` need no checkout, no client and no network.
- The commands need the failure class `timeout` for a run past `roadmap.implement.command_timeout_seconds` (action `retry`) and the class `test` for a strength finding (action `repair`); a run that reaches a bound is no failure, so it raises none.
- The programs are `uv`, `pytest` and `ast-grep` from the runner image, and `mutmut`, `diff-cover` and `coverage` as console scripts of the pinned dev group; no program of the change is `NOT_IN_RUNNER`.
- The pod settings hold: the checks write `.data/` and `mutants/` in the worktree and need no privilege, so `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault` stay.
- The first mutmut run of a fresh checkout copies the whole tree and runs the whole suite serially, so the bounded run usually reaches the bound before it mutates; the report names the bound and the check does not fail for it.
- The skip reads the kind of a group with `KIND_LINE` of `src/devops_cli/roadmap/step_files.py` and its files from the task text of the group.
- The commit holds `tests/roadmap/implement/test_roadmap_implement_scoped_ci.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py` and `tests/roadmap/test_roadmap_limit_classes.py`, which the groups read.
- The first check against the real system is `uv run ast-grep scan --rule .ast-grep/rules/test-function-has-assertion.yml --json tests/roadmap/implement/test_roadmap_implement_strength.py` in the checkout, which must name the line of a test function with no assertion.
- The next check is `uv run pytest --cov=src --cov-report= --cov-fail-under=0 tests/roadmap/implement/test_roadmap_implement_strength.py`, then `uv run coverage xml -q`, then `uv run diff-cover .data/coverage.xml --compare-branch=origin/main --fail-under 100 --format markdown:.data/strength-coverage.md`, which must name the changed file and its missing lines.
- The last check is `uv run devops ci mutate --dry-run --changed --base origin/main` in the checkout, which must list the mutmut run and results requests and make no request.

## Existing Tool Considered

boxed/mutmut 3.8.1 (`https://github.com/boxed/mutmut`, BSD-3-Clause, maintained) covers the mutation run, through `select_targets` and `tally` of `src/devops_cli/ci/mutate.py`; diff-cover 11.0.1 (`https://github.com/Bachmann1234/diff_cover`) covers the changed-line coverage, with the command of `.github/workflows/ci.yml`; pytest-cov and `coverage xml` measure the scoped test modules; and the ast-grep rule `test-function-has-assertion` covers the assertion scan. The change builds no mutation engine and no coverage differ.

## Dependencies

- #5547 changes `src/devops_cli/commands/ci.py`, the file that holds `devops ci mutate`, which this plan reads; this plan changes no line of it.
- #5575 changes `src/devops_cli/commands/ci.py`, the same file of the `devops ci` rows that this plan reads and does not change.
- #5528 changes `src/devops_cli/config/settings.py`, the file that holds `roadmap.implement.command_timeout_seconds` and `roadmap.implement.repair_rounds`, which this plan reads and does not change.
