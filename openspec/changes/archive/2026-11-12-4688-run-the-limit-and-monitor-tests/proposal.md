# Proposal: #4688

## Why

The tests of the run limits drive the limits of the jobs through a scripted model (#4688). A step stops at 500 requests or 1,500 tool calls, and a toolbox run of the stage job takes its tools at 197 of 200 tool calls. A scripted model reaches these limits only after hundreds of requests, and each request of a step runs real git. The CI and test audit of 2026-11-11 measured 5.3 to 11.6 s for each of the 12 slowest of these tests, 108.5 s together, with no coverage. Nine tests of the implement world also wait out the watch of the checks: 3,600 s at a poll of 30 s, which is 121 polls of the pull request, 48.9 s together.

## What Changes

- `run_step` and `run_fix_step` take `usage_limits`, a pydantic-ai `UsageLimits`. Each run of the agent uses it, extra turns included. Its default is `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests and `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` tool calls, as before.
- `ToolboxClient` takes `usage_limits` for each plan run and review run. Its default is `CONST_ROADMAP_STAGE_MAX_REQUESTS` requests and `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS` tool calls, as before.
- The 13 tests that reach a limit pass small limits and keep their relative asserts. One test proves that the three defaults equal the constants.
- The implement world of the tests sets `roadmap.implement.monitor_timeout_seconds` to `WATCH_SECONDS`, three poll intervals. The watch tests that name the timeout read `WATCH_SECONDS`.
- The jobs pass no limits, so no consumer sees a change: the change has no spec delta (`skip_specs: true`).

## Capabilities

None. The jobs run at the same limits, and the new parameters only let a caller set lower limits.

## Impact

- The tests of `tests/roadmap/implement/` and `tests/roadmap/stage/` take less CI worker time. The before and after times are in a comment of the pull request.
- The tests no longer run at the numbers of the jobs. The test of the defaults covers the wiring of the constants, and the limit tests cover the wiring of a given value.
- The change fits one pull request.

## Feasibility

- pydantic-ai 2.59.0 (`uv pip show pydantic-ai-slim`): `Agent.run_sync` takes `usage_limits`, and `UsageLimits` is a dataclass with `request_limit` and `tool_calls_limit` that compares by value. `RunContext.usage_limits` holds the limits of the run, and `_limit_reached` of `src/devops_cli/roadmap/refine/refine_investigation.py` reads it, so the toolbox takes its tools at the given limit less 4 calls.
- `_run_turn` of `src/devops_cli/roadmap/implement/implement_step.py` built the one `UsageLimits` of a step from the constants, and `ToolboxClient.chat_structured` built the one of a toolbox run. No other code builds these limits.
- `monitor_pr` of `src/devops_cli/github/pr_monitor.py` polls at 0 s and after each interval until the timeout, so a timeout of 90 s and an interval of 30 s give 4 polls. The `config` fixture merges each call, so the setting of the world stays when a test adds its own.

## Existing Tool Considered

`UsageLimits` of pydantic-ai, which the code already uses. No new tool and no new code of our own: the change passes the existing value through. Cost: about 30,000 tokens and 2 hours. The change deletes the two inline `UsageLimits` builds of the step and of the toolbox.
