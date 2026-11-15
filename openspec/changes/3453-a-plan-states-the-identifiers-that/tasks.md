# Tasks

## 1. Parse the Adds line of a task group

Kind: behavior. Reads: `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/test_roadmap_step_files.py`. Changes: `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/test_roadmap_step_files.py`.

- [x] 1.1 `test_the_added_names_of_a_group_come_from_its_adds_line` in `tests/roadmap/test_roadmap_step_files.py` gives a group the line `Adds:` with `_delivery_title` and `_publish`, and fails on the base because `TaskGroup.added_names` does not exist; `test_an_adds_line_that_names_no_code_span_is_a_problem` fails on the base because `adds_problem` does not exist
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_step_files.py` fails on the base
- [x] 1.2 Add `ADDS_LINE` and the property `TaskGroup.added_names` to `src/devops_cli/roadmap/step_files.py`: the code spans of the `Adds:` line of a group, each once, in file order, and none for a group with no such line. Add the function `adds_problem`, which gives a reason when the line holds a name outside a code span or holds no code span. Write the two tests first, and see them fail
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_step_files.py` passes

## 2. Give the group an adds field, write the line, and name it in both prompts

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_kind.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_kind.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 2.1 `test_a_behavior_group_renders_the_identifiers_that_it_adds` in `tests/roadmap/stage/test_roadmap_stage_content.py` calls `group_text` on a behavior group whose `adds` holds `_delivery_title`, and `test_an_other_group_that_adds_a_name_fails_the_schema` in `tests/roadmap/stage/test_roadmap_stage_kind.py` calls `_other_problems` on an `other` group whose `adds` holds `_delivery_title`; the base line `src/devops_cli/roadmap/stage/stage_change.py:621:def _other_problems(group: StageGroup) -> list[str]:` refuses no `adds`, so both tests fail on the base. `test_the_prompts_name_the_adds_field_of_a_group` in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` reads both prompts and fails on the base, and `test_the_plan_of_this_change_has_no_content_problem` builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_kind.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 2.2 Give `StageGroup` in `src/devops_cli/roadmap/stage/stage_change.py` the field `adds`, a list of identifiers, and refuse it in `_manifest_problems` and `_other_problems` for a group of another kind. Add the messages `stage_group_adds` and `stage_kind_adds_other` to `src/devops_cli/lang/en/messages.py`, and write the `Adds:` line in `group_text` after the line of the kind and the files, each name in a code span. Add `adds` to the clause of the keys of a group and to the rules of `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md`, because both prompt tests read the fields of `StageGroup`. Run `uv run devops roadmap eval stage --replay` and `uv run devops roadmap eval stage --limit 5` before and after the change, and state the score of each
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_kind.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 2.3 Edit `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md` to name the `adds` field and the `Adds:` line of a group, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 3. Read the line in the plan reader

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/test_roadmap_plan_read.py`. Changes: `src/devops_cli/roadmap/plan_read.py`, `tests/roadmap/test_roadmap_plan_read.py`.

- [ ] 3.1 `test_the_reader_takes_the_added_names_of_a_group_from_its_adds_line` in `tests/roadmap/test_roadmap_plan_read.py` builds a `tasks.md` whose behavior group holds `Adds:` with `_delivery_title` and calls `read_change`, so it fails on the base with no `adds` field; `test_the_reader_refuses_an_adds_line_with_no_code_span` holds `Adds:` with `_delivery_title` and no code span, and fails on the base because `read_change` raises no `PlanReadError`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` fails on the base
- [ ] 3.2 Set `adds` in `_group` of `src/devops_cli/roadmap/plan_read.py` from `TaskGroup.added_names`, and raise `PlanReadError` with the reason of `adds_problem` when the line is malformed. State the `Adds:` line in the module docstring beside the kind of a group. Write the two tests first, and see them fail
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` passes

## 4. Read the added names in the premise check

Kind: behavior. Reads: `src/devops_cli/roadmap/premise.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_premise.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`, `tests/roadmap/implement/test_roadmap_implement_typed_result.py`. Changes: `src/devops_cli/roadmap/premise.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_premise.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`, `tests/roadmap/implement/test_roadmap_implement_typed_result.py`.

- [ ] 4.1 `test_a_behavior_group_that_adds_a_defined_name_returns_the_item` in `tests/roadmap/implement/test_roadmap_implement_job.py` gives a behavior group the `Adds:` line `_delivery_title` and a task that names no guard, so the base runs the group and the test fails on the base; `test_a_sentence_that_names_a_defined_guard_with_no_adds_line_runs_the_group` gives a task that says to add a check beside the guard `_delivery_title` and no `Adds:` line, so the base returns the item and the test fails on the base; `test_a_behavior_group_whose_adds_line_names_an_undefined_guard_runs_the_group` holds the `Adds:` line with `_missing_guard` and a task that names the defined guard `_delivery_title`, so the base returns the item and the test fails on the base. `test_the_check_withdraws_the_checkpoint_of_group_one` in `tests/roadmap/implement/test_roadmap_implement_checkpoint.py` and `test_typed_result_a_return_to_new_writes_returned_as_its_last_mark` in `tests/roadmap/implement/test_roadmap_implement_typed_result.py` keep their asserts, and each of their fixtures gets the `Adds:` line `_delivery_title` so the job still returns the item with no prose rule
  - Verification: `$ uv run devops ci test tests/roadmap/test_premise.py tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_checkpoint.py tests/roadmap/implement/test_roadmap_implement_typed_result.py` fails on the base
- [ ] 4.2 Read `TaskGroup.added_names` in `false_premises` of `src/devops_cli/roadmap/premise.py`, and delete `added_guard`, `_ADD_VERB`, `_GUARD_SPAN`, the `keyword` import and the `added_guard` entry of `__all__` there. Delete the table test `test_a_task_adds_a_guard_only_when_the_identifier_follows_the_guard_word`, its `added_guard` import and the `pytest` import that only it uses from `tests/roadmap/test_premise.py` in the same step, so the module imports and ruff finds no unused import. Add the line `Adds:` with `_delivery_title` to the behavior group of `_guard_tasks` in `tests/roadmap/implement/test_roadmap_implement_job.py`, to the behavior group 3 of `tests/roadmap/implement/test_roadmap_implement_checkpoint.py` and to the behavior group 1 of `tests/roadmap/implement/test_roadmap_implement_typed_result.py`, because each of those groups adds `_delivery_title` and the check reads only the line. Change `premise_guard_defined` in `src/devops_cli/lang/en/messages.py` to name the identifier and its definition line and no task text, and update the docstrings of `false_premises` and `_check_premise` in `src/devops_cli/roadmap/implement/implement_run.py` to the `Adds:` line. Write the three new tests first, and see them fail
  - Verification: `$ uv run devops ci test tests/roadmap/test_premise.py tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_checkpoint.py tests/roadmap/implement/test_roadmap_implement_typed_result.py` passes

## 5. State the line in the plan check guide

Kind: other. Reads: `docs/roadmap/plan-check.md`, `src/devops_cli/roadmap/plan_read.py`. Changes: `docs/roadmap/plan-check.md`.

- [ ] 5.1 State in `docs/roadmap/plan-check.md` that the reader takes the `Adds:` line of a group into the `adds` field, that it refuses a name outside a code span, and that the implement job reads the same line for the premise check of a behavior group
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `docs/roadmap/plan-check.md` to state the `Adds:` line that the reader takes into the `adds` field of a group
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
