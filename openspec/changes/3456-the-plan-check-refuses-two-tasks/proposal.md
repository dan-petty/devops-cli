# Proposal

## Why

The plan check of `devops roadmap stage` tests the form, the paths, the criteria and the content of a plan, but it never compares two tasks of that plan (#3456). The plan of #3417 held task 3.1 and task 3.2 that added the same paragraph to `docs/roadmap/implement.md`, and every check accepted it. A step runs one task group with a model and a token budget, so a duplicate task can make the model repeat an edit, spend the group on no change, or stop the group when the second edit writes no file.

## What Changes

- `check_proposal` refuses two tasks whose normalized work text is the same, and names both task numbers and the group or groups.
- The duplicate check reads the work text of a task only: `test`, `implementation` and `documentation`. A shared `Verification:` line, a `process` check and the fixed `uv run devops docs generate --sync-readme` suffix never make a duplicate.
- The work text of each task is collapsed to one line and casefolded before it is compared.
- A new message in `src/devops_cli/lang/en/messages.py` carries the duplicate-task problem, with one phrase for a group and one for two groups.
- `tests/roadmap/test_roadmap_stage_content.py` gains a test for a duplicate in one group, a test for a duplicate across two groups, a test for two tasks that share a verification command, a test for a documentation task that repeats a work text, and a test for work text that differs only in spacing and case.
- The change carries a spec delta on `roadmap-stage`, because the plan check is behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Two tasks of a plan state different work

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_stage_content.py`

## Feasibility

- The probes confirm the premise: `The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit.` and `The path `tests/roadmap/test_roadmap_stage_content.py` is a file of the staging commit.` The code of `src/devops_cli/roadmap/stage_change.py` in the context holds `def check_proposal(` and `def _task_texts(group: StageGroup) -> list[str]:`, so the rule has a place to live and the task order has one renderer.
- The probes confirm the message catalog: `The path `src/devops_cli/lang/en/messages.py` is a file of the staging commit.` That file holds the `stage_problem_*` entries that `content_problems` formats, so the new problem joins them.
- The probes confirm that the task text is already parsed and rendered: `The path `src/devops_cli/roadmap/step_files.py` is a file of the staging commit.` and `_task_texts` renders the tasks of a group from `test`, `implementation`, `documentation` and `process`, so the check needs no parser.
- First check of the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` on the branch tip runs the module as it stands and shows the existing content tests pass, before any test of this change is written.
- Second check of the real system: after the new test is written and before the rule, the same command `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the new duplicate-task test and passes on the rest.
- Third check: `uv run devops ci test tests/roadmap/` runs the roadmap stage and replay modules that call `check_proposal`, so a new problem on a plan that no fixture duplicates shows up there.
- Fourth check: `uv run devops ci` on the pull request runs the static checks, the type check and the full suite over the new rule.

## Existing Tool Considered

`TaskGroup.tasks` in `src/devops_cli/roadmap/step_files.py` and the renderer `_task_texts` in `src/devops_cli/roadmap/stage_change.py` already hold and order the task text of a group, so the check compares fields that a parser gives it and adds no parser. The cost is about 500 tokens to build and test, and about 15 minutes elapsed.

## Dependencies

None.
