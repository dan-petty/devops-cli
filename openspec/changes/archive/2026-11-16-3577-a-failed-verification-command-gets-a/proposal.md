# Proposal

## Why

The implement step gives a repair turn only to a failed static check or hook, so a failed verification command or a lost test stops the item at once, though the agent holds the failure text and can repair it (#3577).

## What Changes

- A verification command that exits 1 gets one repair turn with the class of its program, its masked output and a diagnosis hint.
- `verification_class` in `src/devops_cli/roadmap/implement/implement_shell_policy.py` maps the program after `uv run` to the class: `pytest` to test, `mypy` to types, `ruff` to lint, and the row after `devops ci` the same way.
- `_command_failure` records the argv, the exit status and the negative flag of a failed command in an optional stop list, and `commands_failure` passes that list through, so its callers still read a string.
- `_exit_failure` gives a command that exits 1, and that is no negative search, a failure with the class of its program, the changed paths and the verification flag.
- A lost test gets one repair turn that may restore or edit its test file, with the class `tests_lost` and the changed paths.
- `_extra_ask` gives no turn for the class `plan_defect` or `premise_false`, whatever repair paths the failure holds.
- The repair turn changes only the files of the step and the change's tasks file, judged by `_foreign_change`.
- The message of a foreign change in a turn no longer names a static check, and the two cases that assert the old sentence move with it.
- A stop whose failure now carries repair paths and has no round left appends the line that names the spent rounds, so a case that asserts an exact reason sets `roadmap.implement.repair_rounds=0` and expects `rounds_spent(0)`.
- The case of the repair turn writes its files and ticks no task in the first turn, so the wip keeper runs no verification command before the exit check, and the exit check makes the first run of the command.
- The cases that pin the old immediate stop in `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_command.py`, `tests/roadmap/implement/test_roadmap_implement_step_own_text.py`, `tests/roadmap/implement/test_roadmap_implement_wip.py`, `tests/roadmap/implement/test_roadmap_implement_step_attempts.py` and `tests/roadmap/implement/test_roadmap_implement_step_repair.py` state the new stop with that setting.
- The lost-test cases of `tests/roadmap/implement/test_roadmap_implement_step_tests_kept.py` get the setting and the rounds line, and one new case shows the repair turn that restores a test.
- The spec delta of `roadmap-implement-step/exit-checks` states the new turns and their classes, because a roadmap job's stop and repair behavior is observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/exit-checks`: A step asks for a fix of a failed check within the repair rounds, A step keeps the tests that existed, A failed exit check stops the step and resets the checkout, A failure that no attempt can fix gets no repair round

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_verification_class.py`, `tests/roadmap/implement/test_roadmap_implement_step_attempts.py`, `tests/roadmap/implement/test_roadmap_implement_step_repair.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_command.py`, `tests/roadmap/implement/test_roadmap_implement_step_own_text.py`, `tests/roadmap/implement/test_roadmap_implement_wip.py`, `tests/roadmap/implement/test_roadmap_implement_step_tests_kept.py`

## Feasibility

- The probe of the staging commit says, word for word: The path `src/devops_cli/roadmap/implement_step.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_step.py`, `tests/support/implement_step.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it. The plan uses the moved path `src/devops_cli/roadmap/implement/implement_step.py`.
- The probe says, word for word: The path `tests/roadmap/test_roadmap_implement_step_repair.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/implement/test_roadmap_implement_step_repair.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it. The plan reads and changes the moved path.
- The probe says, word for word: The path `src/devops_cli/roadmap/failure.py` is a file of the staging commit, and the path `docs/ERRORS.md` is a file of the staging commit. The classes that the issue names sit in the first: `src/devops_cli/roadmap/failure.py:73:TESTS_LOST = "tests_lost"`.
- The probe also says, word for word: Not probed, the bound of 10 commands is reached: `roadmap.implement.repair_rounds`, `src/devops_cli/config/settings.py`, `ruff`, `mypy`, `test`, `types`, `lint`, `plan_defect`, `premise_false`, `_extra_ask`, `_exit_failure`, `ModelRetry`, `_repair_rounds`, `repair_paths`, `TESTS_LOST`, `_foreign_change`, `pytest`. This run read `_command_failure`, `commands_failure`, `_exit_failure`, `_plan_failure`, `_extra_ask`, `_foreign_change`, `_repair_rounds`, the rounds line and the wip keeper with the calls below.
- `read_file` of `src/devops_cli/roadmap/implement/implement_step.py` lines 1655 to 1686 confirmed the premise of the issue: the failed verification command is wrapped with no repair paths at `src/devops_cli/roadmap/implement/implement_step.py:1667:return _Failure(early)`, while the failed static check carries the changed paths at `src/devops_cli/roadmap/implement/implement_step.py:1680:return _Failure(static, frozenset(changed))`.
- `read_file` of the same file lines 1830 to 1846 showed the gate of the turn: `src/devops_cli/roadmap/implement/implement_step.py:1836:if failure is None or failure.repair_paths is None:`, so a failure with no repair paths gets no turn today.
- `read_file` of the same file line 1620 showed the lost-test stop with no paths: `src/devops_cli/roadmap/implement/implement_step.py:1620:return _Failure(lost, klass=FailureClass.TESTS_LOST)`, and line 1642 stages the changed files before it at `src/devops_cli/roadmap/implement/implement_step.py:1642:changed = _stage(source)`, so the paths that the lost-test failure needs are at hand.
- `read_file` of the same file lines 1804 to 1822 showed the file limit of a turn: `src/devops_cli/roadmap/implement/implement_step.py:1814:allowed = ask.may_change | {tasks}`, and `src/devops_cli/roadmap/implement/implement_step.py:1406:repair_paths: frozenset[str] | None = None` showed the field that the new failures set.
- `read_file` of `src/devops_cli/roadmap/implement/implement_shell_policy.py` lines 460 to 520 showed `src/devops_cli/roadmap/implement/implement_shell_policy.py:494:argv: list[str]`, so the step reads the program after `uv run` from the argv that `read_verification` returns.
- `read_file` of `src/devops_cli/lang/en/messages.py` lines 3190 to 3260 showed `src/devops_cli/lang/en/messages.py:3222:implement_stop_repair_turn_changed: str = (`, whose text names the static check: `src/devops_cli/lang/en/messages.py:3223:The extra turn for the static check changed files that the step had not changed`.
- The first finding of the review is a real defect and group 2 corrects it: `tests/roadmap/implement/test_roadmap_implement_step_repair.py:195:The extra turn for the static check changed files that the step had not changed: ` and the same sentence at line 216 are the whole expected reason of two cases, so group 2 updates both with the reworded message.
- The `problem` of the previous reply names two paths that no file of the commit holds. They are files that the fake writes inside the temporary checkout: `tests/roadmap/implement/test_roadmap_implement_step_attempts.py:45:write_call("tests/test_sample.py", BAD_TEST),` and `tests/roadmap/implement/test_roadmap_implement_step_attempts.py:46:write_call("src/sample.py", SHOUT_CODE),`. They are no paths of the repository, so the task of group 2 now names them in prose and not in a code span, and the group creates no file.
- `read_file` of `src/devops_cli/roadmap/implement/implement_step.py` lines 1140 to 1260 showed `src/devops_cli/roadmap/implement/implement_step.py:def _command_failure` and `src/devops_cli/roadmap/implement/implement_step.py:def commands_failure`, which return `str | None`, so the reason stays a string and the argv, the exit status and the negative flag travel in an optional list; the same range shows `src/devops_cli/roadmap/implement/implement_step.py:1213:failure = _command_failure(` with the call that passes the found argv.
- The second finding of the earlier plan is a real defect too: `src/devops_cli/roadmap/implement/implement_step.py:2167:log.before_request = keeper.check` runs the keeper before each model request, and it runs the verification of each freshly ticked task at `src/devops_cli/roadmap/implement/implement_wip.py:172:index for index in fresh if self.verify(self.group.tasks[index].verification) is None`. A first turn that ticks a task therefore spends the fake's first run on the keeper, and the exit check would already pass. The new case of group 2 ticks no task in its first turn, so the exit check makes the first run of the command and the repair turn follows; `src/devops_cli/roadmap/implement/implement_step.py:1664:source, inputs.group.verification_commands, log.trace, log.verified` shows that the exit check runs the group's verification commands whatever the ticks are.
- `read_file` of the same file lines 1930 to 1960 showed the round gate: `src/devops_cli/roadmap/implement/implement_step.py:1949:repair = ask is not None and used < start.allowed`, and `src/devops_cli/roadmap/implement/implement_step.py:1952:return _Rounds(run, failure, used, number, start.allowed, spent=ask is not None)`, so a budget of 0 runs no turn and still reports a spent round.
- `read_file` of the same file lines 2088 to 2120 showed the line that the stop appends: `src/devops_cli/roadmap/implement/implement_step.py:2111:if reason and rounds_spent:` and `src/devops_cli/roadmap/implement/implement_step.py:2112:MESSAGES.roadmap.implement_stop_rounds.format(rounds=budget)`, and `tests/support/implement_step.py:def rounds_spent` gives that line to a test as `rounds_spent(0)`.
- The staged value of the repair bound is `src/devops_cli/config/defaults.py:979:DEFAULT_ROADMAP_IMPLEMENT_REPAIR_ROUNDS: int = 3`; the plan adds no setting and gives the existing bound no new name.
- `read_file` of `tests/roadmap/implement/test_roadmap_implement_step_repair.py` lines 180 to 270 showed `tests/roadmap/implement/test_roadmap_implement_step_repair.py:254:test_a_failed_verification_command_gets_no_extra_turn`, which the new turn makes false, so group 2 gives it the setting `roadmap.implement.repair_rounds=0` and names that no round is left.
- `read_file` of `tests/roadmap/implement/test_roadmap_implement_step_attempts.py` lines 1 to 190 showed the case at line 139, `tests/roadmap/implement/test_roadmap_implement_step_attempts.py:139:def test_a_failed_verification_command_gets_no_round_and_names_no_rounds(`, which asserts `requests == 2` and `[(1, "stop")]`; group 2 rewrites it as the case of the repair turn, and the fake's files are written in the temporary checkout at `tests/roadmap/implement/test_roadmap_implement_step_attempts.py:45:write_call("tests/test_sample.py", BAD_TEST),`.
- `read_file` of `tests/roadmap/implement/test_roadmap_implement_step.py` lines 344 to 400 showed `tests/roadmap/implement/test_roadmap_implement_step.py:352:def test_a_failed_verification_command_stops_the_step_and_resets_the_checkout(`, whose group ticks every task, so group 3 keeps the ticks and only sets the setting and the rounds line.
- The cases of `tests/roadmap/implement/test_roadmap_implement_step_own_text.py`, `tests/roadmap/implement/test_roadmap_implement_wip.py` and `tests/roadmap/implement/test_roadmap_implement_step.py` that assert an exact reason or a request count run with `roadmap.implement.repair_rounds=0`, as groups 3 and 4 state.
- The requirement texts of the spec delta sit under the 500-character limit: the masking and the spent-round detail of the first move into its scenarios, and the parse rule of the second stays in its scenario, so no requirement text carries it.
- The scenarios that name no code in a code span are covered by a behavior group: group 2 changes and runs `tests/roadmap/implement/test_roadmap_implement_step_attempts.py` and `tests/roadmap/implement/test_roadmap_implement_step_repair.py`, group 3 runs `tests/roadmap/implement/test_roadmap_implement_step.py`, and group 5 changes and runs `tests/roadmap/implement/test_roadmap_implement_step_tests_kept.py`.
- No task names a run-time sample file: the new module of group 1 is a path of the repository, and the files of the cases live in the temporary checkout and are named in prose.
- `_command_failure` runs each command with `cwd=source` at `src/devops_cli/roadmap/implement/implement_step.py:1173:done = run_subprocess(list(argv), cwd=source, quiet=True, timeout=limit)`, so it needs a checkout of the repository; `commands_failure` and `_exit_failure` call it and need a checkout too. `verification_class` reads the argv alone, so it needs no checkout, no client and no network.
- The plan introduces no new program. Every verify runs `uv run devops ci test`, which runs `pytest` in the image: `uv`, `devops`, `pytest`, `git`, `ruff` and `mypy` are in the runner tools list, and NOT_IN_RUNNER names none of them. The tests double the process edge and use a temporary checkout, so they reach no network, no cluster and no real scanner. The pod sets `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`.
- The first checks that the implementation runs are `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_verification_class.py`, then `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_attempts.py tests/roadmap/implement/test_roadmap_implement_step_repair.py`, then `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_tests_kept.py`, then the gate `uv run devops ci`.

## Existing Tool Considered

pydantic-ai `ModelRetry` covers the validation of a model output and a tool call. It cannot judge the exit status of a shell verification command, and it cannot limit the files that the next turn changes, so the step extends its own repair rounds: about 40000 tokens to build, 2000 tokens each quarter to keep, 8000 tokens to repair one miss, and about 3 hours.

## Dependencies

None.
