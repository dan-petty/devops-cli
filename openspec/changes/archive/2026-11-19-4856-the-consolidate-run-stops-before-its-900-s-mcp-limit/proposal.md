# Proposal: #4856

## Why

The `roadmap_consolidate` MCP tool has a 900 s limit. Its analysis client can wait 3600 s for one model request. `run_consolidate` has no run budget. The outer limit stops the run with exit 124 and leaves a daemon thread that keeps judging and writing. The fix makes the request timeout shorter than a 780 s run budget and the run budget shorter than the 900 s tool limit. It also caps limit at 20 and adds an offline chain test.

## What Changes

- Add constants for the consolidate run budget (780 s), request timeout (300 s), margin (60 s), and maximum limit (20).
- Update the `roadmap consolidate` command `--limit` option to set `max=20`.
- Update the MCP tool schema for `roadmap_consolidate` to publish a maximum of 20 for `limit`.
- Enforce the 780 s run budget in `run_consolidate`: stop starting new judgements when the budget ends, write the plan with remaining shortlists unjudged, print a diagnostic to stderr, and exit 0.
- Enforce per-request timeout in `consolidate_judge.py`: calculate timeout as `min(300, remaining_budget - 60)`. Make no request if remaining budget minus margin is zero or less. Check the budget before each of the two model requests.
- Mark shortlists as unjudged when a judge request times out without aborting the run.
- Add an offline chain test that verifies `request_timeout < run_budget < 900s tool limit`.

## Capabilities

None. The change has no spec delta (skip_specs: true).

## Impact

Consolidate runs stay within the 900 s tool timeout. Partial plans write safely on budget exhaustion.

## Feasibility

All components exist in `devops_cli.roadmap.consolidate`, `consolidate_judge.py`, and `constants.py`. Tests use existing fake models and in-memory stores.

## Existing Tool Considered

No open tool covers the need. Tenacity and anyio enforce deadlines but cannot write partial plans or cap published tool schemas.
