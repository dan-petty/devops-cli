# Tasks

## 1. Judge a request of an agent

Reads: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/implement_shell_policy.py`. Changes: `src/devops_cli/roadmap/implement_amend.py` (new), `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_amend.py` (new).

- [x] 1.1 In the new `tests/roadmap/test_roadmap_implement_amend.py`, add one test for each scenario of the requirements of `roadmap-plan-amendment`: `parse_request` returns the request of a last `plan-request` block, and none for a message with no block, a block that text follows, a bad JSON text, an unknown kind and an extra key. `judge` applies a `path` request for a tracked file with the same name, and refuses another name, an `old` that is tracked, an `old` marked `(new)` and a `new` that is untracked. It applies a `command` request that keeps the paths, and refuses a dropped path and the program `python`. It adds a `task` request as task `2.3` with its `Verification:` line. It refuses a ticked group and an `old` that only `## Criteria` holds. The bullet of `## Amendments` goes before `## Workflow follow-up`, is masked and has no checkbox, and a `scope` request gives a refusal. Verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_amend.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_amend.py`
- [x] 1.2 Write `src/devops_cli/roadmap/implement_amend.py`: `PlanRequest` (pydantic, `extra="forbid"`), `parse_request(message)` that finds the fence with `MARKDOWN` of `src/devops_cli/roadmap/step_files.py`, `Amendment`, `Applied`, `Refused` and `judge(request, tasks_md, tree)` with a `StagedTree`. Make `_valid_verify` of `src/devops_cli/roadmap/stage_form.py` public as `is_valid_verify`, and use it. Add the refusal texts to the messages file, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_amend.py tests/roadmap/test_roadmap_stage_form.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_amend.py tests/roadmap/test_roadmap_stage_form.py`

## 2. Ask the agent for a request

Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/test_roadmap_implement_prompt.py`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/test_roadmap_implement_prompt.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_implement_prompt.py`, add tests that the prompt names the block `plan-request` and the five kinds, says that an agent that asks changes no file and ticks no task, says that the job decides and that a change of a requirement or a criterion waits for a person, and no longer holds the words "write the file at that path anyway". Verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py`
- [x] 2.2 In step 4 of `src/devops_cli/ai/tasks/roadmap_implement_step.md`, replace the sentence about a wrong path with the rule for a request: the keys, one example block, and the five kinds. Verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py`

## 3. Apply an amendment and run the group again

Reads: `src/devops_cli/roadmap/implement_amend.py`, `tests/support/roadmap_implement.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_amend_job.py` (new).

- [x] 3.1 In the new `tests/roadmap/test_roadmap_implement_amend_job.py`, with the fixtures `job_world` and `ModelScript`, add the replays of the requirements of `roadmap-implement-job`. Wrong test path: step 1 changes no file and ends with a `path` request, step 2 does the group, the item is ready, `origin` holds the amendment commit, the archived `tasks.md` holds the new path and one bullet, and the pull request comment holds the line of the amendment with its evidence. A `command` request and a `task` request give the same result. A second request for group 1 stops the item Blocked. A stop with no request stops as before. A stop after an amendment puts the line of the amendment in a comment on the pull request. Verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_amend_job.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_amend_job.py`
- [x] 3.2 In `src/devops_cli/roadmap/implement_run.py`, make `_groups` read `tasks.md` again after each amendment. For a stopped step, judge `parse_request(outcome.last_message)` before `_stopped_by`. For `Applied`, write the file, commit with `_commit_if_changed`, keep the `Amendment` in a list of the run, and run the group again once. Add the lines of the amendments to `_comment` and `_Mark`, and post that comment on a stop when the pull request exists. Add the texts to the messages file, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_amend_job.py tests/roadmap/test_roadmap_implement_job.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_amend_job.py tests/roadmap/test_roadmap_implement_job.py`

## 4. Name the action taken and plan the dry run

Reads: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/request_plan.py`. Changes: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_implement_amend_job.py`.

- [x] 4.1 In `tests/roadmap/test_roadmap_failure.py`, add a test that `failure_lines(FailureClass.PLAN_DEFECT, taken=FailureAction.AMEND)` names `amend` taken and `wait` left. In `tests/roadmap/test_roadmap_dry_runs.py`, add a test that `implement_requests` lists the amendment commit, the split request and the return, each with its condition. In `tests/roadmap/test_roadmap_implement_amend_job.py`, add a replay in which the amended group stops again with "The agent changed no file.": the comment holds the class `plan_defect`, `Action taken: amend` and the action left `wait`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_implement_amend_job.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_implement_amend_job.py`
- [x] 4.2 Add the argument `taken` to `failure_lines` in `src/devops_cli/roadmap/failure.py`, pass the action `amend` from the stop in `implement_run.py` when the job applied an amendment for the group that stopped, and add the conditional writes to `implement_requests` in `src/devops_cli/roadmap/request_plan.py` with their texts in the messages file. Verify that `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_implement_amend_job.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_implement_amend_job.py`

## 5. Return the item or ask a person

Reads: `src/devops_cli/roadmap/return_item.py`, `src/devops_cli/roadmap/implement_amend.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_amend_job.py`.

- [x] 5.1 In `tests/roadmap/test_roadmap_implement_amend_job.py`, add the replays of the requirements "A false premise returns the item to New" and "A scope change and a refused request wait for a person". Premise on a Planned item: the Status is New, the comment holds the evidence, `origin` has no branch, no worktree is left, and the record has no `implement.stopped`. Premise on a Staged item after group 1 passed: `origin` holds the old staged tip and `implement.group` is cleared. A premise with empty evidence, a `scope` request, a second request for a group and a `path` request with another file name stop the item as a question, with `tasks.md` as before. A `path` request whose `old` only `## Criteria` holds changes nothing. Verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_amend_job.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_amend_job.py`
- [x] 5.2 In `src/devops_cli/roadmap/implement_run.py`, return the item on a `premise` request with `apply_return(store, plan_return(...))` and clear the marks of the run. Stop the item as a question for a `scope` request, a refused request, a second request and an empty premise, with the class `plan_defect` and the action left `wait`. Add the texts to the messages file, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_amend_job.py tests/roadmap/test_roadmap_implement_job.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_amend_job.py tests/roadmap/test_roadmap_implement_job.py`

## 6. Share the split of the stage job

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/roadmap/stage_split.py` (new), `src/devops_cli/roadmap/stage.py`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/test_roadmap_stage_split.py` (new), `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [x] 6.1 In the new `tests/roadmap/test_roadmap_stage_split.py`, add tests that `ask_split` sends the number, the title, the budget, the groups and the criteria of its arguments to the client with the split prompt, returns the `StageSplit` of the reply, and sends a group that has `text` as it is. In the test file of the stage prompt rules, add a test that the split prompt says what a group with `text` means. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_split.py tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_split.py tests/roadmap/test_roadmap_stage_prompt_rules.py`
- [x] 6.2 Write `src/devops_cli/roadmap/stage_split.py` with `ask_split(client, request)`, move `_SPLIT_TASK` there, and make `_Planner._fit` in `src/devops_cli/roadmap/stage.py` call it, with its own rule of one split for each item. Add the sentence for a group with `text` to the split prompt, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_split.py tests/roadmap/test_roadmap_stage_prompt_rules.py tests/roadmap/test_roadmap_stage_plan.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_split.py tests/roadmap/test_roadmap_stage_prompt_rules.py tests/roadmap/test_roadmap_stage_plan.py`

## 7. Tell a refusal for the window from other refusals

Reads: `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/roadmap/implement_step.py`. Changes: `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/roadmap/implement_step.py`, `tests/roadmap/test_roadmap_implement_resplit.py` (new).

- [x] 7.1 In the new `tests/roadmap/test_roadmap_implement_resplit.py`, add a test that `build_step_inputs` with a window under the measure raises `OverWindowError`, that it is a `RoadmapImplementError` with the code `ROADMAP_IMPLEMENT_REFUSED`, and that it holds the measure and the limit. Verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_resplit.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_resplit.py`
- [x] 7.2 Add `OverWindowError` to `src/devops_cli/exceptions/roadmap.py`, with the fields `measured` and `limit`, and raise it in `build_step_inputs` of `src/devops_cli/roadmap/implement_step.py`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_resplit.py tests/roadmap/test_roadmap_implement_step.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_resplit.py tests/roadmap/test_roadmap_implement_step.py`

## 8. Split the group in the job

Reads: `src/devops_cli/roadmap/stage_split.py`, `src/devops_cli/roadmap/stage_criteria.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/commands/roadmap.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/test_roadmap_implement_resplit.py`.

- [x] 8.1 In `tests/roadmap/test_roadmap_implement_resplit.py`, add the replays of the requirement "A group over the limit of the step is split once for each item" with a scripted split reply. Group 2 of 3 becomes two groups, the old group 3 becomes group 4 with its tasks renumbered, the `## Criteria` lines keep their texts and get the new numbers, the amendment bullet and the comment line exist, and the job runs the new groups. A group of the reply over the limit, a second group over the limit, and a missing splitter stop the item as `plan_defect`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_resplit.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_resplit.py`
- [x] 8.2 In `src/devops_cli/roadmap/implement_run.py`, add the keyword `splitter` to `apply_implement`, catch `OverWindowError` in `_groups`, ask `ask_split` once for each item, check the reply with `path_problems`, `form_problems`, `criterion_problems` and `measure_groups`, renumber the later groups, write `tasks.md` and commit. Pass `get_llm_client(task="analysis")` from the implement job command, add the keyword to `JobWorld.run`, add the texts to the messages file, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_resplit.py tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_implement_command.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_resplit.py tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_implement_command.py`

## 9. Say in the documents what the job does for a wrong plan

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, `CONTEXT.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, `CONTEXT.md`.

- [x] 9.1 In `docs/ROADMAP_WORKFLOW.md`, section "The failure classes", change the sentence "The Job runs one action by itself" so that it names the fix rounds, `amend` for a request of the kinds `path`, `command` and `task`, `return` for a `premise` request, and the split of a group over the window. Add the rules of the judge, the section `## Amendments` and the question to a person. Verify that `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py` passes
  - Verification: `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py`
- [x] 9.2 In `docs/roadmap/implement.md`, add the paragraph "A plan request" after "A stop". In `CONTEXT.md`, change the entry "Implementing" to say that a step may ask for a bounded change of its plan, and that a false premise returns the item. Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes
  - Verification: `uv run devops ci docs`

## Criteria

- A replay with a wrong test path in the plan ends in a delivered pull request that has the corrected path in its `tasks.md`.: group 3
- A replay with a false premise returns the item with the evidence and no code.: group 5
- The amendment appears in the PR comment with the evidence.: group 3
- An amendment never changes a spec requirement or an acceptance criterion without a person.: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
