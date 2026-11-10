# Proposal: #4346

## Why

A stage plan run or review run has no call budget that the model can read. The prompt says "a limited number of tool calls", and the limits are 200 calls and the context window. A model that explores without end fills the window, loses its tools, and its forced reply is refused (`limit=window`, 113 calls, 2026-11-10). Each request sends the whole context again, so a long run costs the sum of its contexts. A live run of #3387 with `deepseek-v4.1-flash-1017` took 62 minutes: a plan run of 79 calls (6.5 million input tokens), a review run of 92 calls (5.6 million), a repair plan of 49 calls, and a second review of 97 calls (7.3 million). Closes #4346.

## What Changes

- The prompt of the plan run says that a plan needs about 30 tool calls, and the prompt of the review run says about 40.
- From call 40 of a plan run and call 60 of a review run, each tool answer ends with a notice to read no more and give the reply. The tools stay on, and the limits of the window and the counts stay.
- `StageTools` counts the calls of a run and `ToolboxClient` starts the count at each run.
- The prompt of the plan run tells the model that a request with `problem` needs no new reading beyond what the problem names.
- The change carries a spec delta because the answers of the tools and the prompts are observable by the model.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A run has a call budget

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_tools.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify_tools.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/test_roadmap_limit_classes.py`

## Feasibility

- Premise checked in Prometheus (`devops_cli_roadmap_tool_calls_per_run`, 2026-11-10): row `stage` over 7 days p50 33, p90 43; over 12 hours p50 37, p90 86, p99 113. Row `stage_verify` over 7 days p50 53, p90 107.
- Premise checked in a live trace of `devops roadmap stage --plan --item 3387` (scratch, not committed): plan run 79 calls, 58 requests, 790 s; gate return 4 calls; review run 92 calls, 52 requests, 1138 s; repair plan 49 calls, 34 requests, 625 s; second review 97 calls, 63 requests, 868 s, where the window ended its tools. Only 3% of the read lines of the plan run were read before, so a duplicate guard would not help.
- pydantic-ai 2.59.0 has `UsageLimits` (a hard stop) and no soft budget; a tool function can be wrapped with `functools.wraps`, and the schema of the tool stays that of the function.
- `uv run devops roadmap eval stage --replay` makes no tool call and keeps its result.

## Existing Tool Considered

pydantic-ai gives the hard limits that the job uses already, and no soft budget. The change adds a counter and a notice. Cost: about 40 000 tokens to build, 3 000 to keep and 3 hours.
