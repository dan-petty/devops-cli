# Tasks

## 1. Refuse a body text that ends with a cut mark

Kind: behavior. Reads: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_pull_form.py`. Changes: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_pull_form.py`.

- [x] 1.1 Write `test_a_body_text_that_ends_with_a_cut_mark_is_refused` in `tests/roadmap/test_roadmap_pull_form.py` first: `body_problems` and `build_body` name a problem for a why that ends with `...` or `…`, and `body_problems` finds no problem for a why that holds `...` inside a sentence; it fails on the base because the body rule is absent
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` fails on the base
- [x] 1.2 Add `form_body_cut` to the messages, and a check at the end of `_text_problems` in `src/devops_cli/roadmap/pull_form.py` that appends it when the text above `Closes` or `Plans` ends with `...` or `…`, so `body_problems` and `plan_body_problems` refuse a cut text and `build_body` raises with every problem and writes nothing
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` passes

## 2. Add the refused_reply failure class

Kind: behavior. Reads: `src/devops_cli/roadmap/failure.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_stop_clear.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/roadmap/failure.py`, `tests/roadmap/test_roadmap_failure.py`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 Change `test_the_classes_are_the_twenty_of_the_taxonomy` in `tests/roadmap/test_roadmap_failure.py` to `test_the_classes_are_the_twenty_one_of_the_taxonomy` with `refused_reply` in the set, and add `"refused_reply": "wait"` to `test_the_default_actions_are_the_ones_of_the_design`; both fail on the base because `FailureClass.REFUSED_REPLY` does not exist. Keep `test_a_new_digest_does_not_clear_a_stop_for_a_lost_test` in `tests/roadmap/test_roadmap_stop_clear.py` green, so `tests_lost` keeps the action `wait` and the base scenario `A new runner image and a lost test` still holds
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/invariants/test_roadmap_workflow_doc.py` fails on the base
- [x] 2.2 Add `REFUSED_REPLY = "refused_reply"` to `FailureClass` after `REFUSED_TOOL`, and `FailureClass.REFUSED_REPLY: FailureAction.WAIT` to `ACTION_BY_CLASS` in `src/devops_cli/roadmap/failure.py`, so a body that the model cannot repair twice waits for a person. Name the class in the typed-class paragraph of the module docstring. Add its row to the class table of `docs/ROADMAP_WORKFLOW.md`, and keep `test_each_class_has_exactly_one_default_action_in_one_table` equal to the enum
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/invariants/test_roadmap_workflow_doc.py` passes
- [x] 2.3 Edit `docs/ROADMAP_WORKFLOW.md` to add the `refused_reply` row to the class table
  - Verification: `$ uv run devops ci docs` passes

## 3. Add the one-retry rebuild of a refused body

Kind: behavior. Reads: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/roadmap/retitle.py`, `src/devops_cli/ai/tasks/roadmap_retitle.md`. Changes: `src/devops_cli/roadmap/pull_retry.py` (new), `src/devops_cli/ai/tasks/roadmap_implement_body.md` (new), `tests/roadmap/test_roadmap_pull_retry.py` (new).

- [ ] 3.1 In `tests/roadmap/test_roadmap_pull_retry.py`, write `test_a_refused_body_is_rebuilt_once_from_the_problems` first: a build that refuses the first text and accepts the second returns the rebuilt body after one rewrite call, and a build that refuses both raises `RefusedPullReply` with the problems of the second text after one rewrite call and no third call
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_retry.py` fails on the base
- [ ] 3.2 Create `src/devops_cli/roadmap/pull_retry.py` in the shape of `src/devops_cli/roadmap/retitle.py`: `RefusedPullReply` with its problems, `retried_body(*, text, build, rewrite)` that runs `build(text)` once and, on `ValidationError`, calls `rewrite(text, problems)` once and runs `build` again, and `GatewayPullBody.rewrite` that asks the `analysis` client with `load_task_prompt(_PROMPT)` for a `BodyReply` of one text. Create the prompt `src/devops_cli/ai/tasks/roadmap_implement_body.md` and name it in the constant `_PROMPT`, so the prompt is no orphan: it edits the refused text, keeps its facts, fits the limit and holds no `...` and no placeholder
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_retry.py` passes

## 4. Rebuild the implement job's refused body once

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/pull_retry.py`, `src/devops_cli/commands/roadmap.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/commands/roadmap.py`, `tests/roadmap/implement/test_roadmap_implement_body_retry.py` (new), `tests/roadmap/implement/test_roadmap_implement_job.py`.

- [ ] 4.1 In `tests/roadmap/implement/test_roadmap_implement_body_retry.py`, write `test_a_refused_body_is_rebuilt_once_and_written` first: a run whose `build_body` refuses the first why and whose fake `rewriter` returns a good why writes the rebuilt body after one model call, and `body_problems` finds no problem in it; `test_a_second_refusal_stops_the_item_as_refused_reply` asserts the class `refused_reply` and no third model call; `test_a_cut_why_in_the_rebuilt_text_stops_the_item` asserts that no `...` reaches the body
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_body_retry.py tests/roadmap/implement/test_roadmap_implement_job.py` fails on the base
- [ ] 4.2 In `src/devops_cli/roadmap/implement/implement_run.py`, add `rewriter: Any = None` to `apply_implement`, `_implement_item` and `_ItemRun`, and change `_body` to call `retried_body` with `build_body`, the why of `_why` and a rewrite through `self.rewriter`. A run with no rewriter builds the body once, and a refusal stops the item with `failure_class=FailureClass.REFUSED_REPLY`. Catch `RefusedPullReply` and stop with the same class and the message `implement_stop_body_refused`. Pass `rewriter=get_llm_client(task="analysis")` in `src/devops_cli/commands/roadmap.py`, where the command already passes `splitter`, and keep `tests/commands/test_all_commands_help_dryrun.py` green. Give the refused-body case of `tests/roadmap/implement/test_roadmap_implement_job.py` the class `refused_reply`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_body_retry.py tests/roadmap/implement/test_roadmap_implement_job.py` passes

## 5. Document the one retry of a refused body

Kind: other. Reads: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/roadmap/implement.md`.

- [ ] 5.1 State in `docs/roadmap/implement.md` that the job rebuilds a body that the form check refuses one time, writes the rebuilt body when it passes, and stops the item with `refused_reply` on a second refusal, so no text with `...` or a placeholder reaches the pull request
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `docs/roadmap/implement.md` for the one retry and the second refusal
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 4: A job that gets a refused body sends the problems to the model once.
- Group 4: A rebuilt body that passes is written to the pull request.
- Group 4: A second refusal stops the item with the refused-reply failure class.
- Group 1: The job writes no `...` into a title or body.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
