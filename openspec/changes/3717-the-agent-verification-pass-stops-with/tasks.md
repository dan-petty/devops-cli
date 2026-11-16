# Tasks

## 1. Type the stop of an agent run from its messages

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`. Changes: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `tests/ai/client/test_roadmap_agent_run.py`.

- [ ] 1.1 `test_the_stop_of_a_text_reply_keeps_its_text_and_its_reason` in `tests/ai/client/test_roadmap_agent_run.py`: three text replies end the run with `text_reply` and the text of each reply, and an exhausted output retry gives `output_retries_exhausted` with the limit 2
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py` fails on the base
- [ ] 1.2 Add `StopReason` and `StopCause` to `src/devops_cli/roadmap/agent_run.py` and the function `stop_cause`, which reads the last reply, the retry prompt of a tool that is no function tool, the output cut and the invalid arguments. Add `texts` and `cause` to `InvestigationStopped` in `src/devops_cli/roadmap/refine/refine_investigation.py`, and fill them in `_stopped_outcome`, which takes the resolved output retries
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py` passes

## 2. Give the findings of a text reply and name the stop

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/ai/client/structured.py`, `src/devops_cli/roadmap/agent_run.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`.

- [ ] 2.1 `test_a_text_reply_that_holds_the_findings_gives_them` in `tests/roadmap/stage/test_roadmap_stage_toolbox.py`: a text reply with the findings gives them, a text reply with no findings raises with `text_reply`, a third call to a tool that the run does not offer raises with `refused_tool_call`, an exhausted output retry raises with `output_retries_exhausted` and names the limit 2, and an exhausted call limit raises with `budget_exhausted`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py` fails on the base
- [ ] 2.2 In `chat_structured` of `src/devops_cli/roadmap/stage/stage_toolbox.py`, for `Verification` and `LaterVerification`, parse each text of the stop with `_repair_and_validate_payload` and return the model that validates. Set `trace.stop_reason` before raising: the cause of the stop, `window_starved`, or `model_error`. In `_stopped`, build the message of a review stop from the cause, with a new text for `text_reply`, `refused_tool_call`, `output_retries_exhausted` and `budget_exhausted` in `src/devops_cli/lang/en/messages.py`, and keep the existing text for the output cut and the invalid arguments
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py` passes

## 3. Record the stop reason of a failed eval case

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/commands/roadmap_eval_verify.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`.

- [ ] 3.1 `test_a_failed_case_records_its_stop_reason` in `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`: a case that stops with `text_reply` ends as failed, the JSON holds the reason, and the text report names it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` fails on the base
- [ ] 3.2 Add `reason` and `error` to `CaseVerification` and `reason` to `CaseOutcome` in `src/devops_cli/roadmap/stage/stage_verify_eval.py`. In `task`, catch a rejected key first, then `AIClientError` and `RoadmapStageError`, and return a stopped `CaseVerification` with the reason of the last trace. In `_outcome`, map a stopped verification to `_not_run` with its reason, and read the reason back in `stored_cases`. Write `cases[].reason` in `verify_json`, and append a line for each failed case with its name and reason in `render_verify`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` passes

## Criteria

- Group 2: A run with a model that answers in text in place of the output tool gives the findings of the model or a stop whose message names the cause. A test with a scripted model shows the case.
- Pending person: `devops roadmap eval verify --case <case>` with the local verification model gives findings on the good case of #3410 and on `good-2739-the-subprocess-environment-guard-accepts-gh`, or the report names why it cannot., It needs the local `qwen3.8:27b` verification model and a network, which no offline test can run; a person runs the command after the merge.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
