# Tasks

## 1. Extract the shared definition check into the premise module

Reads: `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/roadmap/refine.py`, `tests/roadmap/test_roadmap_stage_probe.py`. Changes: `src/devops_cli/roadmap/premise.py` (new), `src/devops_cli/roadmap/stage_probe.py`, `tests/roadmap/test_premise.py` (new).

- [x] 1.1 In `tests/roadmap/test_premise.py`, write `test_the_definition_lines_of_an_identifier_come_from_the_commit`, which runs the shared function on the commit of the checkout and asserts that the definition line of `_delivery_title` names `src/devops_cli/roadmap/implement_run.py`. Run it first and see it fail on the missing module
  - Verification: `uv run devops ci test tests/roadmap/test_premise.py tests/roadmap/test_roadmap_stage_probe.py` fails on the base
- [x] 1.2 Create `src/devops_cli/roadmap/premise.py` with `definition_lines(source, sha, name, git=git_result)`, which runs the extended `git grep` of `_definition_pattern` at `sha` and returns the definition lines, and `defines(source, sha, name)`, which reports whether the list is not empty. Move `_definition_pattern` and the definition branch of `_Run.identifier` of `src/devops_cli/roadmap/stage_probe.py` into the new module. Call `definition_lines` from `_Run.identifier` with `self.git`, so the stage probe keeps its command budget, its messages and its line limit
  - Verification: `uv run devops ci test tests/roadmap/test_premise.py tests/roadmap/test_roadmap_stage_probe.py` passes

## 2. Check the premise of a behavior group before its step

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/premise.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/premise.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_premise.py`, `tests/roadmap/test_roadmap_implement_job.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_implement_job.py`, add `test_a_behavior_group_that_adds_a_guard_the_base_already_runs_returns_the_item`, whose tasks file has a behavior group (a failing test, then a task that adds the guard `_delivery_title`), and assert the item is New with the definition line in the comment, that no model request ran and that the branch tip is as it was. Add `test_a_behavior_group_whose_guard_the_base_lacks_runs`, which asserts the group runs and commits, and `test_a_group_that_is_not_behavior_runs_though_the_base_defines_the_name`. Add the table test of `added_guard` to `tests/roadmap/test_premise.py`. Run them first and see the first fail
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [x] 2.2 Add `added_guard(task_text)` and `false_premises(source, sha, group)` to `src/devops_cli/roadmap/premise.py`. `added_guard` reads a task of an add verb, the word guard or check, and exactly one identifier in a code span. `false_premises` calls `definition_lines` for each such name. In `src/devops_cli/roadmap/implement_run.py`, call `false_premises` before the step of a group for which `TaskGroup.is_behavior` holds, at the last commit that is no `wip:` commit, and return the item to New with the definition lines when there are any. A group of another kind runs no check
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes

## 3. Record the new premise check on the implement page

Reads: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md`. Changes: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 3.1 Add a paragraph to the page `docs/roadmap/implement.md` that says the job checks the premise of a behavior group at the branch tip before the group starts, that a definition of a guard the task adds returns the item to New with the definition line, and that the job writes nothing in that case
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
