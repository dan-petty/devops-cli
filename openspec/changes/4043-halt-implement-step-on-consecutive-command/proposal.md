# Proposal: Halt the implement step on consecutive command refusals

## Why
The shell policy returns a refusal to the model as a tool result. A model can repeat a refused command in every reply. Each reply holds the whole history, so one request can pass 150,000 tokens. The only stop is `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` (30), and the token budget often ends the run first. Issue #3247 spent 8,022,108 tokens in 77 model calls on 4 refused `uv` commands, and pull request #3981 failed in the same way. Closes #4043.

## What Changes
- Add `CONST_ROADMAP_IMPLEMENT_MAX_CONSECUTIVE_REFUSALS` with the value 3.
- `ToolCallLog` counts the refusals in a row, over the whole step. A tool call that the shell policy does not refuse resets the count. At the third refusal in a row the log ends the run with `UnexpectedModelBehavior`, as it does for the total limit.
- The total limit of 30 stays: it stops a model that alternates refused and accepted calls.
- The stop text holds "refused by policy", so `classify_failure` gives `refused_tool` and the wait action. No new class.

## Capabilities
- Modified: `roadmap-implement-step`.

## Impact
A step that loops on a refused command stops after 3 refusals, not 30 or the token budget. A model that mixes refused and accepted calls is not affected until 30 refusals in total. The change keeps out of the push code of the implement and stage jobs.

## Feasibility
Checked on the code of `origin/main` (0.112.1). `ToolCallLog.wrap_tool_execute` in `src/devops_cli/roadmap/implement/implement_tool_log.py` sees each tool result, and knows a refused call by `refusals`. It raises on the total limit only. `ShellRefusal` returns a refusal as a result, with no retry (#3271), so pydantic-ai tool retries cannot stop the loop. `classify_failure` matches "refused by policy" in `failure.py`. The premise holds.

## Existing Tool Considered
The alternatives check of 2026-11-10 found none. pydantic-ai has caps on total requests, tool calls and tokens, but no count of consecutive refusals from the project shell policy. Cost to build: about 8,000 tokens and 1 hour; to keep: about 1,000 tokens a year. A new dependency would cost more.
