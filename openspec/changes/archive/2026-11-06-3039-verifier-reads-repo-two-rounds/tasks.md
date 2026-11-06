# Tasks

## 1. Return the task order and verify form findings

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_verify.py`. Changes: `src/devops_cli/roadmap/stage_verify.py`, `tests/roadmap/test_roadmap_stage_verify.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_verify.py`, replace `test_the_return_types_are_the_three_that_the_issue_names` with `test_the_return_types_add_task_order_and_verify_form`. The test asserts that `RETURN_TYPES` and `OPEN_TYPES` hold `TASK_ORDER` and `VERIFY_FORM`, and that a finding of either type with a quote in the input is returned and is open
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py` fails on the base
- [x] 1.2 Add `DefectType.TASK_ORDER` and `DefectType.VERIFY_FORM` to `RETURN_TYPES` in `src/devops_cli/roadmap/stage_verify.py`. `OPEN_TYPES` takes them through `RETURN_TYPES`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py` passes

## 2. Run the verifier with the read tools

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/stage_tools.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`. Changes: `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `tests/roadmap/test_roadmap_stage_verify.py`, `tests/roadmap/test_roadmap_stage_verification.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_stage_verify.py`, assert that the tool set of a verify run holds the nine read tools of the toolset `base` and no write tool, and that the run starts with the system text of the pass and the request, and holds no planner message
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py` fails on the base
- [x] 2.2 In `src/devops_cli/roadmap/stage_toolbox.py`, make `ToolboxClient.chat_structured` run an agent with the read tools for the schema `Verification`, as it does for `StageProposal`, with a new `RunTrace` in `traces`. Other schemas keep the inner client
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py` passes
- [x] 2.3 In `tests/roadmap/test_roadmap_stage_verification.py`, assert that the verify request of a plan holds no planner message, and that the item comment lists each verifier read with its path
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verification.py` fails on the base
- [x] 2.4 In `src/devops_cli/roadmap/stage.py` and `src/devops_cli/roadmap/run.py`, pass the verifier as a `ToolboxModel` of the task `verification` and build its runner in `_planner_of`. Combine the traces of the planner runner and the verifier runner in `_Planner.plan`. In `src/devops_cli/commands/roadmap.py`, wire the same model for the stage command. Update `src/devops_cli/ai/tasks/roadmap_stage_verify.md` to say that the reviewer can call the read tools to check each claim
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verification.py` passes

## 3. Keep the verify request inside the window

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/refine_investigation.py`. Changes: `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_stage_verify.py`.

- [x] 3.1 In `tests/roadmap/test_roadmap_stage_verify.py`, assert that the verify request of the largest plan of the golden set has at most the stage window minus `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` tokens, and that the cited files kept are the first in plan order
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py` fails on the base
- [x] 3.2 In `src/devops_cli/roadmap/stage_verify.py`, cap the cited files of `VerificationInput` to the room that the window leaves, in plan order. Keep the constants of the caps in `src/devops_cli/config/constants.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py` passes

## 4. Repair the plan up to two rounds

Kind: behavior. Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_stage_verification.py`.

- [x] 4.1 In `tests/roadmap/test_roadmap_stage_verification.py`, replace `test_the_revised_plan_is_not_returned_again` with `test_the_plan_is_returned_twice_then_stays_in_draft`. The test uses a verifier that returns a return-type finding on each review, and asserts two planner repair calls, three reviews, and the staged change with the open finding that keeps the draft with `plan/needs-fix`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verification.py` fails on the base
- [x] 4.2 Add `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS` with the value 2 to `src/devops_cli/config/constants.py`. In `_Planner._verified` of `src/devops_cli/roadmap/stage.py`, loop over the repair rounds with the return rule, and remove the single-return branch
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verification.py` passes

## 5. Report the recall floor of the verify eval

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_verify_eval.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage_verify_eval.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_verify_eval.py`.

- [x] 5.1 In `tests/roadmap/test_roadmap_stage_verify_eval.py`, assert that the rendered report of `render_verify` states the recall of the blocker and major defects, the floor of 90 percent, and whether the recall meets it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify_eval.py` fails on the base
- [x] 5.2 Add `CONST_ROADMAP_VERIFY_RECALL_FLOOR` with the value 0.9 to `src/devops_cli/config/constants.py`. Add the report text to `src/devops_cli/lang/en/messages.py`, and print the floor line in `render_verify` of `src/devops_cli/roadmap/stage_verify_eval.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify_eval.py` passes
- [x] 5.3 In `tests/roadmap/test_roadmap_stage_verify_eval.py`, assert that the verifier of each case of `evaluate_cases` is a `ToolboxClient` for the checkout of the commit of the case, so the pass reads that checkout with the read tools
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify_eval.py` fails on the base
- [x] 5.4 In `src/devops_cli/roadmap/stage_verify_eval.py` and `src/devops_cli/commands/roadmap_eval_verify.py`, build a `ToolboxClient` for each case inside its checkout, with the model of the `verification` task and the window of that task, and pass it to `verify`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify_eval.py` passes

## 6. Close the gaps that the review of the change found

Kind: behavior. Reads: `src/devops_cli/roadmap/refine_judge.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/agent_run.py`. Changes: `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_verify_eval.py`, `src/devops_cli/roadmap/refine_judge.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/commands/roadmap_eval_verify.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify_tools.md`, `tests/roadmap/test_roadmap_stage_verify.py`, `tests/roadmap/test_roadmap_stage_verification.py`, `tests/roadmap/test_roadmap_stage_verify_eval.py`, `tests/roadmap/test_roadmap_refine_trust.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/support/scripted_model.py`.

- [x] 6.1 Assert that a full request at the window 65536 is offered the nine tools on its first request, that a quote of a tool answer returns the plan, that a mixed first round lists each finding, and that the review takes the window of the task `verification`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py`
- [x] 6.2 Keep the request below `tool_stop(window)` less the reserve, count the instructions, read the quote from the tool answers, give the planner each open finding, list the findings of each round, and take the window of the task `verification`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verification.py`
- [x] 6.3 Assert that the eval gives `read_spec` the OpenSpec tool and that `--model` keeps the rest of the task, then do both, and make the agent run the only path of `plan_stage` and `evaluate_cases`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify_eval.py`
- [x] 6.4 Assert that a `task_order` or `verify_form` finding on a proposal of refine is advice and that the plain prompt names no tool, then move the tool rules to `roadmap_stage_verify_tools.md` and add `JUDGE_OPEN_TYPES`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_trust.py`
- [x] 6.5 Assert that a verification run that hits a limit names that run, and give it its own message. Change the report of the comment to name the planner and the review
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py`

- [x] 6.6 Assert that a verification run counts its tool calls in the row `stage_verify`, then give each agent schema its row, and state it in the metric text, `k8s/README.md` and the alert text. Changes: `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/tool_metrics.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`, `docs/TELEMETRY.md`, `k8s/README.md`, `k8s/monitoring/prometheus-values.yaml`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_toolbox.py`

## 7. Document the repair rounds and the floor

Kind: documents. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`.

- [x] 7.1 In `docs/roadmap/stage.md`, state that the verifier reads the repository with the read tools, that two repair rounds run before the draft keeps `plan/needs-fix`, and that `task_order` and `verify_form` return the plan. Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`
- [x] 7.2 In `docs/ROADMAP_WORKFLOW.md`, state the recall floor of 90 percent of the blocker and major defects as the value of `CONST_ROADMAP_VERIFY_RECALL_FLOOR`, and state the two repair rounds
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: allow the spend of `uv run devops roadmap eval verify --source <repository>` on this code and on the base, and record the recall of the blocker and major defects on the pull request. A sample of one case of 2026-11-05 used 578,119 input tokens, so one run of 44 cases costs about 25 M input tokens, more than the limit of 3 M input tokens that the agent had for this work. Criterion 2 of the issue stays not measured until this run.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
