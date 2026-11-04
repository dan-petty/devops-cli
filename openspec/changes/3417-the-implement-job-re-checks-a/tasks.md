# Tasks

## 1. Extract the shared definition check into the premise module

Reads: `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/roadmap/refine.py`, `tests/roadmap/test_roadmap_stage_probe.py`. Changes: `src/devops_cli/roadmap/premise.py` (new), `src/devops_cli/roadmap/stage_probe.py`, `tests/roadmap/test_premise.py` (new).

- [ ] 1.1 In `tests/roadmap/test_premise.py`, write `test_the_definition_lines_of_an_identifier_come_from_the_commit`, which runs the shared function on the commit of the checkout and asserts that the definition line of `_delivery_title` names `src/devops_cli/roadmap/implement_run.py`. Run it first and see it fail on the missing module
  - Verification: `uv run devops ci test tests/roadmap/test_premise.py tests/roadmap/test_roadmap_stage_probe.py` fails on the base
- [ ] 1.2 Create `src/devops_cli/roadmap/premise.py` with `definition_lines(source, sha, name)`, which runs the extended `git grep` of `_definition_pattern` at `sha` and returns the definition lines, and `defines(source, sha, name)`, which reports whether the commit defines the name. Move `_definition_pattern` and the definition branch of `_Run.identifier` of `src/devops_cli/roadmap/stage_probe.py` into the new module, and call it from `_Run.identifier` so the stage probe keeps its behavior and its messages
  - Verification: `uv run devops ci test tests/roadmap/test_premise.py tests/roadmap/test_roadmap_stage_probe.py` passes

## 2. Check the premise of a behavior group before its step

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/premise.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `tests/roadmap/test_roadmap_implement_job.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_implement_job.py`, add `test_a_behavior_group_that_adds_a_guard_the_base_already_runs_returns_the_item`, whose tasks file says to add the guard `_delivery_title`, and assert the item is New with the definition line in the comment and that no step ran. Add `test_a_behavior_group_whose_guard_the_base_lacks_runs`, which asserts the group runs and commits. Run both first and see the first fail
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` fails on the base
- [ ] 2.2 Add `guard_names(group)` to `src/devops_cli/roadmap/implement_run.py`, which reads a task of an add verb, a word such as guard or check, and one backticked identifier. Before a behavior group starts, call `defines` of `src/devops_cli/roadmap/premise.py` at the worktree HEAD for each name, and take the existing premise return path with the definition line as its evidence when one is found. A group of another kind runs no check
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py` passes

## 3. Record the new premise check on the implement page

Reads: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md`. Changes: `docs/roadmap/implement.md`.

- [ ] 3.1 Add a paragraph to the page `docs/roadmap/implement.md` that says the job checks the premise of a behavior group at the branch tip before the group starts, that a definition of a guard the task adds returns the item to New with the definition line, and that the job writes nothing in that case
  - Verification: `uv run devops ci docs` passes
- [ ] 3.2 Add the behavior-group premise check and its return to New to the page `docs/roadmap/implement.md`, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
