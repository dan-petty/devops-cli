# Tasks

## 1. Type the stop of an agent run from its messages

Kind: behavior. Reads: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`. Changes: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`.

- [x] 1.1 `test_a_stopped_investigation_names_its_cause` in `tests/roadmap/refine/test_roadmap_refine_investigation.py`: a text reply gives the reason `text_reply` with its text, calls to a tool that the run does not offer until the tools retry limit is spent give `refused_tool_call` with the tool name and the limit that the run used, an exhausted output retry gives `output_retries_exhausted` with the limit that the caller set, and a spent call limit gives `budget_exhausted` with the limit name
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py` fails on the base
- [x] 1.2 Add `StopCause` and `stop_cause` to `src/devops_cli/roadmap/agent_run.py`: it reads the last reply of the run, the limit that ended the tools, the retry prompt of a call to a tool that is no function tool of the run, the output cut, the invalid arguments and the output retry limit that the caller set, and returns a reason (`text_reply`, `refused_tool_call`, `budget_exhausted`, `output_retries_exhausted`), the name of the tool or of the limit, and the text of each reply. The limit that ended the tools wins over the refused call, because the `_offering` hook takes the tools away at that limit and the next call then gets the same tool retry stop. Add `stop_reason` and `stop_detail` to `RunTrace`. Add `texts` and `cause` to `InvestigationStopped` in `src/devops_cli/roadmap/refine/refine_investigation.py`, and fill them in `_stopped_outcome`, which takes the resolved output retries from `investigate`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py` passes

## 2. Give the findings of a text reply and name the stop

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/agent_run.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`.

- [x] 2.1 `test_a_stopped_verification_run_names_its_cause` in `tests/roadmap/stage/test_roadmap_stage_toolbox.py`: a text reply that pydantic-ai refuses raises with the reason `text_reply` and names the text, calls to a tool that the run does not offer until the tools retry limit is spent raise with `refused_tool_call`, the tool name and the limit that the run used, an invalid findings reply past the output retry limit raises with `output_retries_exhausted` and names the limit that the run used, and a spent call limit raises with `budget_exhausted`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py` fails on the base
- [x] 2.2 In `chat_structured` of `src/devops_cli/roadmap/stage/stage_toolbox.py`, rely on pydantic-ai `AutoOutputSchema` (`_output.py:638-655`, which strips Markdown fences at `_output.py:981`) for valid findings text replies. Set `trace.stop_reason` and `trace.stop_detail` before raising: the cause of the stop, `window_starved` or `model_error`. In `_stopped`, build the message of a review stop from the cause: the tool name and the tools retry limit of a refused call, the limit that ended the tools, the output retry limit that the run used, or the text reply that pydantic-ai refused, with the new texts `stage_verify_stop_text_reply`, `stage_verify_stop_refused_tool`, `stage_verify_stop_output_retries` and `stage_verify_stop_budget` in `src/devops_cli/lang/en/messages.py`. Keep the text for the output cut and the invalid arguments
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py` passes

## 3. Record the stop reason of a failed eval case

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/commands/roadmap_eval_verify.py`, `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`.

- [x] 3.1 `test_a_failed_case_records_its_stop_reason` in `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`: run `evaluate_cases` with `ToolboxModel(Script(...).model())` and the `stage_repo` clone, as `test_roadmap_stage_verify_eval.py:730-781` does, on a case whose review stops with `text_reply` that pydantic-ai refuses; the case ends as failed, the JSON holds that reason for the case, and the text report names the case and its reason
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` fails on the base
- [x] 3.2 Add `reason: str = ""` to `CaseOutcome` in `src/devops_cli/roadmap/stage/stage_verify_eval.py`. In `_run_cases`, give the `ToolboxClient` of each case a `traces` list, keep the `stop_reason` of the last trace of a case whose review raises, and give it to `_outcome`, which sets it on `_not_run`. Write `cases[].reason` in `verify_json`, and append a line for each failed case with its name and reason in `render_verify`, with the new text `verify_eval_failed_case` in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` passes

## Criteria

- Group 2: A run with a model that answers in text in place of the output tool gives the findings of the model or a stop whose message names the cause. A test with a scripted model shows the case.
- Pending person: `devops roadmap eval verify --case <case>` with the local verification model gives findings on the good case of #3410 and on `good-2739-the-subprocess-environment-guard-accepts-gh`, or the report names why it cannot., It needs the local `qwen3.8:27b` verification model and a network, which no offline test can run; a person runs the command after the merge.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
