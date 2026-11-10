# Proposal

## Why

The stage plan can name the test module that a change updates and still omit the test case whose assertion the change breaks, as the plan of #3415 did with `test_every_command_reads_and_the_checkout_does_not_change`. The plan then passes the path check, and the implementer finds the case only when the module runs (#3443). The plan request also holds no list of the cases that name a symbol of a changed source file, so the planner cannot see them before it writes a group.

## What Changes

- The premise probe lists, for each cited test module and cited source file that the staging commit holds, the test cases of the module whose body names a symbol, message or constant that the source file binds.
- The probe reads each cited file once with `git cat-file -p` and adds no command kind, so the pinned command set of `tests/roadmap/stage/test_roadmap_stage_probe.py` stays as it is.
- The line that reports the reached command bound names each test module and source file that the probe did not list.
- The planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` requires a behavior group that changes a source file and names an existing test module to name each case that the change invalidates, or to state that it updates no existing test case.
- `docs/roadmap/stage.md` states the listing and both prompt rules, and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` asserts the rules.
- The change carries a spec delta because the plan request and the planner prompt are observable to a consumer.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The probe lists the test cases of a cited test module, The probe names the pair that its command bound leaves unlisted, The stage prompt names the test case that a change invalidates, The stage prompt says when a group updates no existing test case

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/roadmap/stage.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_probe.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The premise of the issue holds at the staged commit: `tests/roadmap/stage/test_roadmap_stage_probe.py:166:assert {args[0] for args in ran} == {"cat-file", "grep", "log", "ls-tree"}` pins the exact set of command names, so a change that adds a command kind breaks that case, and `read_file` of lines 100 to 180 showed the line.
- The set of that line holds four names, and the plan decides each one: `cat-file` carries the new read of a cited test module and a cited source file, and `grep`, `log` and `ls-tree` stay unchanged; the issue quotes `{"cat-file", "grep", "log"}`, which is the set before #3415 added `ls-tree`.
- The cited test path moved: `The path `tests/roadmap/test_roadmap_stage_probe.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_probe.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.` The plan cites `tests/roadmap/stage/test_roadmap_stage_probe.py` and restores no old path.
- The cited snapshot path moved the same way: `The path `tests/roadmap/__snapshots__/test_roadmap_stage_plan.ambr` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/__snapshots__/test_roadmap_stage_plan.ambr`.`
- The cited plan of #3415 is archived: `The path `openspec/changes/3415-the-stage-probe-names-the-files/tasks.md` is no file at the root of the staging commit.` Commit 4ada738e2 deleted or renamed it, and the record is `openspec/changes/archive/2026-11-04-3415-the-stage-probe-names-the-files/tasks.md`.
- The path `coverage.py` names the external tool and no file of the repository: `The path `coverage.py` is no file of the staging commit. No commit in the history deleted or renamed it.` The plan creates no such file and lists the cases with the probe's own reads.
- The bound is staged at `src/devops_cli/config/constants.py:3276:CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS: Final[int] = 10`, and `tests/roadmap/stage/test_roadmap_stage_probe.py:133:assert CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS == 10` pins it; the plan keeps both.
- The probe already reports what the bound leaves out: `src/devops_cli/roadmap/stage/stage_probe.py:class Probe` holds `skipped`, and its `text` appends the message `stage_probe_skipped` with the bound, so the new listing uses that line.
- `docs/roadmap/stage.md:21:The premise probe asks the staging commit about each path, class field and identifier that the issue cites` shows that the plan request holds the probe lines, so the listing of the referencing cases belongs to the probe.
- Functions that need a checkout of the repository: `probe_premise` of `src/devops_cli/roadmap/stage/stage_probe.py:def probe_premise`, because it runs `git cat-file` and `git grep` at the staging commit; `git_result` of `src/devops_cli/roadmap/refine/refine.py:def git_result`, which runs the command in the checkout; and `load_task_prompt` of `src/devops_cli/ai/task_loader.py:def load_task_prompt`, which reads the task files of the checkout. No call of the plan needs a client of a service or a network.
- The verify command runs `uv`, `pytest` and `git`, all in the runner image, and a failure is failure class `test` with action `repair`; the pod sets `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`, and the plan introduces no other program.
- The first checks against the real system are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, then `uv run devops roadmap eval stage --replay` with the score of the same model before and after the change.
- The messages file is a file of the commit, named at `tests/roadmap/stage/test_roadmap_stage_plan.py:98:MESSAGES_FILE = "src/devops_cli/lang/en/messages.py"`, and this run read its `stage_probe_skipped` entry at `src/devops_cli/lang/en/messages.py:3596:stage_probe_skipped: str = "Not probed, the bound of {bound} commands is reached: {items}"`; the group adds the two new texts beside it.
- The issue's rule that the plan snapshot records the prompt rule does not hold as written: `tests/roadmap/stage/test_roadmap_stage_plan.py:203:assert change.files == snapshot` snapshots the rendered change folder, so the snapshot holds no prompt text; the plan asserts the rule in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` and changes no snapshot.
- The probe's per-run state is private to `src/devops_cli/roadmap/stage/stage_probe.py`: `callers` of the name of that state shows the other two modules of the repository define their own class of the same name and call only their own, so no caller outside the probe module reads it and the plan changes no other source file.

## Existing Tool Considered

tarpas/pytest-testmon (MIT, maintained) selects the tests that a change affects, and the dynamic contexts of coverage.py map a test case to the lines it runs; neither names the assertion that a change invalidates. The change builds one listing in the probe instead: about 20k tokens to build, about 3k tokens each quarter to keep and fix, and about 3 hours of elapsed time. It deletes no internal code.

## Dependencies

None.
