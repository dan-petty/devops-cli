# Design

## Decisions

- `run_step`, `run_fix_step` and `ToolboxClient` take one pydantic-ai `UsageLimits` as `usage_limits`, which is the name that `Agent.run_sync` uses. One value holds the request limit and the tool call limit, so the code adds no type of its own.
- The default of `usage_limits` is a module value that the signature shows, and not `None`. Thus one test reads the defaults of the three signatures and compares them with the constants, and no test reads a private name.
- The step passes `usage_limits` down to each run of the agent: the first turn, each send again and each extra turn. The extra turn continues the conversation, so it counts against the same limits as before.
- The tests that reach a limit keep their relative asserts and use small limits: 6 requests and 12 tool calls for a step, and 12 requests and 8 tool calls for a toolbox run. At four tool calls in each reply, the tool call limit of the step comes before its request limit. In a toolbox run, the call budget takes the tools before the request limit does, as with the constants (200 calls, 250 requests).
- Two tests keep the constants. Each sends one reply that holds one more tool call than the limit, so it makes one request and fails at once.
- The implement world sets `roadmap.implement.monitor_timeout_seconds` to three poll intervals (90 s). A watch that waits out the monitor polls the pull request 4 times and not 121. The longest wait of a test that settles is three intervals (`test_watch_progress_line_the_watch_writes_a_line_at_each_interval`).

## Rejected alternatives

- A `usage_limits` field on `ToolCallLog` or on `StepBudget`. The log holds the counts of a step, and `StepBudget` holds the token and time budgets of `roadmap.implement`. A field would carry the limits to the turn with fewer edits, but it would hide an input of the run in a value with another purpose.
- A setting for the limits. The limits are the loop guard of a job, and no person tunes them (`tests/roadmap/test_roadmap_limit_classes.py`, class `guard`). A setting would add a variable that no operator needs.
- A default of `None` that the code reads as the constants. The test of the defaults would then have to run a step to 500 requests, or read a private name.
- A probe tool through `mcp_toolset` that records `RunContext.usage_limits`. It proves the default of a step with two requests, but `ToolboxClient` takes only a `RoadmapMcpToolset`, so the toolbox would need a second method.
