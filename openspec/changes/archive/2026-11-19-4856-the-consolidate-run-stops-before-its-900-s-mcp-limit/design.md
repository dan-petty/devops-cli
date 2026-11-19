# Design

## Decisions

- Set the consolidate run budget to 780 s (`CONST_ROADMAP_CONSOLIDATE_RUN_BUDGET_SECONDS`). This leaves a 120 s margin below the 900 s MCP tool limit.
- Set the per-request timeout to 300 s (`CONST_ROADMAP_CONSOLIDATE_REQUEST_TIMEOUT_SECONDS`), capped by remaining budget minus 60 s (`CONST_ROADMAP_CONSOLIDATE_MARGIN_SECONDS`).
- Pass the run deadline to the shortlist judge. The judge checks the budget before the proposal request and before the rebuttal request.
- When remaining budget minus 60 s is zero or less, or when a model request times out, record the shortlist as unjudged and continue if budget permits.
- Bound `--limit` to a maximum of 20 in the Click/Typer option, which publishes `maximum: 20` in the MCP input schema.
- When the run budget ends, print a diagnostic to stderr that names the unjudged count and exit 0.
- Add an offline test asserting `request_timeout < run_budget < tool_limit`.

## Rejected alternatives

- Use a 900 s run budget: this equals the MCP tool limit and lets the outer limit stop the run first.
- Check budget only between shortlists: the second model request could cross the budget.
- Abort the run on request timeout: this discards completed work and causes repeated runs.
- Retry timed-out requests: retries consume remaining budget and can cross the deadline.
