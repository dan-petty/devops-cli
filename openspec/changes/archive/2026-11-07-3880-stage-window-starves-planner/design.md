# Design

## Decisions

- **The check reads the trace of the run.** `ToolboxClient.chat_structured` has the `RunTrace` of the run after `investigate` returns. If the first limit is `RunLimit.WINDOW` and the run made fewer than `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` calls, it raises `RoadmapStageError`. It does this before it reads the reply, because a reply of placeholders hides the cause.
- **Only a plan run is checked.** A review run has its own window (the task `verification`) and its own setting. The error of the plan run names the planner settings, so it must not fire for a review.
- **The least number of calls is 8.** The failed runs made 4 and 6 calls, and the run that staged made 40. A constant keeps the number in one place.
- **The test computes the least window.** The first request at its caps counts about 38,000 tokens. Each call adds at most one tool answer of `CONST_ROADMAP_REFINE_TOOL_MAX_CHARS` characters, about 2,000 tokens. The tools end at three quarters of the window. 38,000 + 8 x 2,000 = 54,000 tokens needs a window of 72,000 tokens, so 65,536 fails and 256,000 passes.
- **The comment case "offered no tool" is deleted.** With the new check, a plan run that offered no tool made fewer than 8 calls and hit the window, so it fails the item. The comment of a staged item cannot hold that case.

## Rejected alternatives

- **Raise the number of reply returns, or `ai.max_retries`.** The run at 262,144 tokens staged with `ai.max_retries` 1. The retry sends a reply of placeholders back to a model that still cannot read the code.
- **Check the window setting at the start of the run.** The first request size changes with the item (its body and context), so a check at the start would need a second estimate of the run. The trace has the exact fact.
- **Raise the window in code when the setting is low.** The job uses the setting, and a person sets it. A silent override would hide the cause.
