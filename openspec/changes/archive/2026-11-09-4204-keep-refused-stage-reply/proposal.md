# Proposal: #4204

## Why

The stage job of the roadmap Service staged no item on 2026-11-09 (#4204). The live run of item #4062 needed the refused reply and the first problem text, and the job kept neither: it kept only the last problem, and a plan that fails the gates leaves no plan file. A reply that holds only placeholders (`x`, `placeholder`) in every text also used the second request, and the second reply was the same. The main causes were found and fixed in other pull requests: the gateway answered through a fallback model (#4216), the reference reason could be null (#4215), the reply was cut at 4096 output tokens (#4224), tool calls were joined (#4243), and the window estimate ended the tools too early (#4238). What remains of #4204 is the record of a refused reply and the early stop.

## What Changes

- `_gated` in `src/devops_cli/roadmap/stage/stage.py` logs one line `stage reply refused: item=#<n> request=<n> input_tokens=<n> tools_offered=<bool> result=<refused|degenerate>` for each refused reply. `request` is the number of the last request of the plan run, `input_tokens` is its input, and `tools_offered` says whether it offered a function tool. `RunTrace` gets the field `last_input_tokens`.
- A failed item keeps its refused replies and their problems in `roadmap/stage/<owner>/<repo>/<n>.refused.json`, beside the plan file, under the key of the plan input. The staging of the item deletes the file, and a new failed plan replaces it. A reply over 128 KiB is dropped and only its size stays, and a problem is cut at 8,000 characters and masked for secrets. The file is written with the same atomic writer as the plan file.
- A first or second reply with a placeholder (`is_placeholder` of the pull request form) in `why`, `existing_tool`, each line of `feasibility` and each task of each group ends the item at once with the new `RoadmapStageDegenerateError`, a subclass of `RoadmapStageError`. The job sends no second request. `StageResult` gets the value `degenerate`, so `devops_cli_roadmap_stage_total{result="degenerate"}` counts the item and `failed` keeps the other failures.
- `devops roadmap eval stage` shows `degenerate N` in the line of how the cases ended, through the new `Outcome.DEGENERATE`.
- The change adds requirements to `roadmap-stage` and `roadmap-stage-eval`, because the log line, the file, the metric result and the report are observable.
- It fits one pull request.

## Criteria of #4204

- 1 (log fields), 2 (kept replies) and 3 (`degenerate` result and eval count) are delivered here. Criterion 2 asks for a 7-day age limit "as the gated plan has". The premise is false: the plan file has no age limit. It goes when the item is staged or its input changes. The refused file follows the same rule, and it has a size bound.
- 4 (`staged` above 0 in each 24 hours) and 5 (name and remove the cause) are results of the fixes of #4215, #4216, #4224, #4238 and #4243, and #4205 holds them. They need Service data, not code.
- A schema violation (`StructuredOutputValidationError`) is not a refused reply: the reply never reaches `_gated`. Its failure line holds a count of violations. The text of the violations in the log is out of this change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: adds the requirements `A refused reply is logged`, `A failed item keeps its refused replies` and `A reply of placeholders ends the item`.
- `roadmap-stage-eval`: adds the requirement `The live report counts the degenerate cases`.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`, `src/devops_cli/roadmap/stage/stage_eval_run.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`, `tests/roadmap/stage/test_roadmap_stage_eval_run.py`.
- Documents: `k8s/README.md` (roadmap Service item 15), `docs/TELEMETRY.md` (generated).
- No new setting, so no ConfigMap change and no rollout order. The two constants are code constants.
- Metric: the label `result` of `devops_cli_roadmap_stage_total` gets one more value, `degenerate`. The series count grows by 1 for each repository (1 repository today, so 1 series). No label is added.
- The refused file is on the data volume of the Service, at most about 2 x (128 KiB + 8,000 characters) for each item that failed in the plan, and it is deleted when the item is staged.

## Feasibility

- The premise "the job keeps only the last problem": `_gated` in `stage.py` held `outcome.problem` of the second `_settle` only, and `_keep` wrote a plan file only for a plan that passed. Read in the code at `origin/main` 750cf789.
- The premise "the same placeholder reply returns on the second request": issue #4204 gives the log of 2026-11-08 and the sample of #3566. This change does not prove it; it removes the second request only for a reply that is a placeholder in every text, which the gates refuse in any case (`content`, `form`, `paths`, `spec-delta`). A reply that is only in part a placeholder still goes back once.
- The premise "the plan file has a 7-day age limit": false. `stage_plan_record.py` deletes a plan file when the item is staged or when the key changes (`delete_plan_record` in `_kept` and in the writer). No code ages a file.
- A reply with a placeholder `summary` fails the schema (`summary_problem`), so it never reaches the check. A placeholder in `why`, `existing_tool`, `feasibility` and the tasks passes the schema, as the log of #4204 shows.
- The usage of the last request: pydantic-ai gives `ModelResponse.usage.input_tokens` for each reply, and `RunTrace._add_reply` already sums it. `last_input_tokens` keeps the value of the last reply.
- First check, which fails on origin/main: `uv run devops ci fail-to-pass --base origin/main`. Second check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_refused_reply.py tests/roadmap/stage/test_roadmap_stage_eval_run.py`.

## Existing Tool Considered

- pydantic-ai output validators with `ModelRetry` retry an invalid reply. They neither record the refused reply nor tell a placeholder reply from another one, and the stage job already sets the retries of the schema (`_REPLY_RETURNS`).
- `is_placeholder` of `roadmap/pull_form.py` is the placeholder rule of the content gate, and this change reuses it. No second word list.
- `write_json_file` with `atomic=True` and `mask_secrets` are the existing writer and masker. `RefusedRecord` is a pydantic model, as `StagePlanRecord` is.
- No open tool keeps a refused model reply per item in a Service. The cost to build: about 60,000 tokens, with tests, and about 2 hours. The cost to keep is low: one small module and a bounded file. The cost to fix: a change of the file layout touches one module. The change deletes no internal code.
