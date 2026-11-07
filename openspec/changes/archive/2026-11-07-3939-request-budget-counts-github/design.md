# Design

## Decisions

- **Refund after the answer, not skip before it.** The gate runs before the request, so no status exists. A request must also hold its place while it is in flight, so the budget stays hard. The refund runs at the one place that reads the status (`count_request`). Rejected: reading the status in the gate. It does not exist there. Rejected: counting at `count_request` only. The place would then be taken after the send, and a round could pass the budget while requests are in flight.
- **The newest request leaves.** The window keeps requests by their time only, and the refund of a request cannot name its own entry without a ticket through `acquire`, `pace_request` and `count_request`. The newest entry differs from the exact one by the time between two requests of one round, at most minutes, in an hour window. Rejected: a ticket for each request. It changes four signatures for a gain of seconds.
- **A request with no answer stays.** Evidence: all 264 requests with status `none` in the last hour are GETs of the `core` resource, and the metric gives a gh command and a lost attempt the same status. A timed-out request may have reached GitHub. Rejected: refunding `none`. It would hide requests that GitHub counts, and the budget exists to protect the limit.
- **The metric keeps all requests.** The dashboards and the `status` label stay true. Rejected: a second counter. The `status` label already splits the request count, and the alert reads it.
- **The alert follows the budget.** `RoadmapServiceGitHubRequestsHigh` compares the hour with 90% of the budget, so it must count what the budget counts. The fixtures with no `status` label still match `status!="304"`.

## Largest sources of requests

By counted requests in the hour (status other than 304), from `devops_cli_github_requests_total` by `row`: `metrics` 288, `refine` 286, `other` 236. The row `other` is the work outside a row: `changes_since` (the issue events listing) for each lane that reads changes, and the comment listing of `_person_comment_stamps`. The pull request cuts none of them: each cut changes a job, and the budget no longer starves without it. The follow-ups are #3941 (`metrics`), #3942 (`other`) and #3866 (`refine`).
