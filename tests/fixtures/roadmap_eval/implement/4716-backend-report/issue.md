### Problem Description

The backend breakdown of the lifetime spend report (`_QUERY_BACKEND_BREAKDOWN` in `src/devops_cli/ai/spend/ledger.py`) keeps only rows with `served_by IS NOT NULL`. The spend hook of `build_agent` (`src/devops_cli/ai/client/factory.py`) passes `server` and `served_model` to `track_request_spend`, but not `served_by`. So the stage, refine and alternatives requests are not in the backend breakdown, and its `mean_duration_seconds` ignores them, even after #4504 records the duration of each request.

### Reproduction Steps

1. Run an agent of `build_agent` on a model with a `served_by` URL.
2. Run `get_lifetime_report()` on the ledger.
3. `report.backends` has no entry for the request.

### Expected vs Actual Behavior

Expected: the backend breakdown counts every request that a backend served, as the implement step does through `record_run_spend`.
Actual: the rows of the hook have `served_by` NULL.

### Environment Diagnostics

origin/main after #4504. Found during #4504. Passing the value changes how the pricing registry reads local and hosted calls (`calculate_request_cost(served_by=...)`), so the fix needs a test of the price of a gateway request.

### Pre-Submission Checklist

- [x] I searched open issues.

<!-- devops-roadmap-alternatives:start -->
Alternatives check of 2026-11-14: none.
Tool: none found.
<!-- devops-roadmap-alternatives:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium", "alternatives.adr_hash": "a1cd29eb2588913c344a50dcec7edc599fc9cc39aed976ed694194eb1398099a", "alternatives.body_hash": "eb41771d582e5a4540e7752cb5e47150eaaeabc0c876aa05770f0474eac03a3d", "alternatives.checked_at": "2026-11-14T05:23:21.329599+00:00", "alternatives.failed_at": null, "alternatives.failed_error": null, "alternatives.tool": null, "alternatives.tool_id": null, "alternatives.verdict": "none"} -->
