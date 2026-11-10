# Proposal: #4313

## Why

84 of 161 failures of the stage job in 7 days that the checks caused hold a plan reply in which every text is a placeholder, and nothing records why (#4313). The log line `stage reply refused` gives the request number, the input size and whether a tool was offered. It does not give the stop reason of the reply, the number of tool calls, the limit that ended the tools, or the model that answered. Closes #4313.

## What Changes

- `RunTrace` in `src/devops_cli/roadmap/agent_run.py` keeps the stop reason (`finish_reason`) and the model name of the last reply of the run.
- `_note_refused` in `src/devops_cli/roadmap/stage/stage.py` adds `tool_calls`, `limit`, `finish_reason` and `answered` to the log line, for the results `refused` and `degenerate`. `none` stands for a fact that the run does not hold.
- The scripted model of the tests (`tests/support/scripted_model.py`) gives the model name and the finish reason of a scripted reply to its streamed reply, as a provider does.
- The change carries a spec delta because it changes the content of a logged line.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A refused reply is logged

## Impact

- Code: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`, `tests/support/scripted_model.py`
- Log consumers: a query that reads `result=` at the end of the line keeps working, because the new fields come before it.

## Feasibility

- Premise checked in Loki (`service_name=roadmap-service`, 2026-11-04 to 2026-11-10): the placeholder failures are 86 item failures of 50 distinct items, up to 4 times for one item, in 52 failure lines. The last one is from 2026-11-09 16:24Z. Since the line `stage reply refused` exists (first line 2026-11-09 22:55Z), Loki holds 16 refused replies and no degenerate one.
- The cause is not shown by the old lines, so the log gets the facts first. The facts exist in the run: `ModelResponse.finish_reason` and `ModelResponse.model_name` of pydantic-ai 2.59.0, the tool calls and the limit of `RunTrace`.
- Findings from the metrics, to read with the new line: `devops_cli_ai_model_answers_total` shows only `asked == answered` (no gateway fallback) since it exists; the placeholders began before the Sonnet trial (2026-11-04) and none fell in the trial hours (11:00Z to 12:25Z on 2026-11-09); `devops_cli_roadmap_tool_limit_hits_total{limit="window"}` fell from 20 to 37 hits per 3 hours to 2 to 8 hits per 3 hours after #4238 (merged 2026-11-09 16:57Z), the same hours in which the placeholder replies stopped.
- Check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_refused_reply.py`, and `uv run devops roadmap eval stage --replay` keeps its result.

## Existing Tool Considered

`RunTrace` and `ModelResponse` already hold the facts, and `logging` prints them. No library is needed. The change adds two fields and four log fields. Cost: about 25 000 tokens to build, 2 000 to keep and 1 hour.
