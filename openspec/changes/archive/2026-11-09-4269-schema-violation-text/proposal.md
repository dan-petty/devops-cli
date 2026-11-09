# Proposal: #4269

## Why

The log lines of the stage job show `StructuredOutputValidationError: N schema violation(s)` and no text of the violations (#4269). The cause stays hidden. Two real faults hid behind this line for one day, the null reference reason (#4214) and the cut at 4096 output tokens (#4220). The text is lost in three places: `RunTrace._add_violations` keeps only the count of the retry prompt, `_stopped` raises the error with that count, and `_failure_of` writes only the count into the `StageFailure`. A reply that fails the schema never reaches the checks, so the refused-reply file of #4204 keeps nothing for it.

## What Changes

- New model `ViolationText` in `src/devops_cli/ai/schema_reflection.py`: the location, the pydantic error type and the message of one violation. Each field passes through `mask_secrets` and is cut at 200 characters when the model is made, so no use of the text can leak a secret or grow without a bound. The input value of the violation is never kept.
- `RunTrace` keeps `violation_texts`: the text of the first 3 errors of the last retry prompt of the output tool. The count stays in `violations`. `RunTrace.combined` carries both.
- `StructuredOutputValidationError` gets the fields `violation_texts` (the texts) and `stop_reason` (`validation` or `no tool call`). `_stopped` fills them from the trace. A reply with errors in its retry prompt broke the schema (`validation`); a reply with none held no call to a tool of the run (`no tool call`). The output limit and the invalid arguments keep their own errors with their own text (#4220, #4228).
- `_failure_of` writes the count, the stop reason and up to 3 violations (`loc (type): message`) into the `StageFailure`, so the failure line and the log name them.
- `_gated` in `stage.py` catches a schema failure of a plan ask, logs one line with the same text, and keeps it in `<n>.refused.json` with the refused replies of the same plan. The new field `schema_failure` of the record holds the stop reason, the count and the texts. The staging of the item deletes the file, as for a gate refusal.
- Constants `CONST_ROADMAP_STAGE_VIOLATIONS_SHOWN` (3) and `CONST_ROADMAP_STAGE_VIOLATION_TEXT_MAX_CHARS` (200).
- A plain `chat_structured` client (not the toolbox) fills no text: its message holds no model text by design. Its failure line keeps the count.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: adds the requirements `A schema failure names its violations` and `A schema failure is kept in the refused file`.

## Impact

- Code: `src/devops_cli/ai/schema_reflection.py`, `src/devops_cli/ai/client/models.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`.
- The refused file grows by at most 3 texts of 3 x 200 characters, a few KiB. No new setting, so no ConfigMap change and no rollout order.
- The log line and the file hold text from the model's reply (a field name the model invented, or the message of a validator). The masking helper runs on each field, and the input value is dropped.

## Feasibility

- Library: pydantic-ai builds the retry prompt of a failed output with `RetryPromptPart.from_error`, which sets `content` to `ValidationError.errors(include_url=False, include_context=False)`. Each error is a dict with `type`, `loc`, `msg` and `input`. So the location, the type and the message are in the messages of the run already (`.venv/lib/python3.14/site-packages/pydantic_ai/messages.py`).
- Checked with the real pydantic-ai run in `tests/roadmap/stage/test_roadmap_stage_toolbox.py`: a plan with a missing key and an empty list of changes gives the locations `why` and `groups.0.changes` with the types `missing` and `too_short`. A reply of plain text gives the location `root` and the type `json_invalid`. A call to a tool that the run does not have gives a retry prompt with no error list, so the stop reason is `no tool call`.
- Premise on origin/main: `RunTrace._add_violations` keeps `len(part.content)` only, `_stopped` passes `violations=trace.violations`, and `_failure_of` formats `stage_violations` with the count only (read in the code at `b46506d4`). The cut by length (#4220) and the invalid arguments (#4228) already raise a `RoadmapStageError` that names the cause, so criterion 2 of the issue holds on main already; its test exists in `test_roadmap_stage_toolbox.py`.
- First check, which fails on origin/main: `uv run devops ci fail-to-pass --base origin/main`.

## Existing Tool Considered

The `errors()` of pydantic `ValidationError` and the retry prompt of pydantic-ai carry the fields already. `mask_secrets` of the project masks the text. The change keeps the fields and builds no parser and adds no library.
