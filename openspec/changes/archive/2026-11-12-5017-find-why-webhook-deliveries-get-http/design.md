# Design

## Decisions
- **The cause stays with the owner.** Cloudflare Access answers the 403 (Feasibility of the proposal). The fix is a change of the Bypass policy of `hooks.<domain>/webhooks/github`: include Everyone on that path, or add the 3 missing ranges of `api.github.com/meta`. Both change a security control at the edge, which is owner decision O3. The comment on #5017 holds the evidence and the two options.
- **The metrics row reads the deliveries.** The row runs every 13 minutes for each repository of `service.repos`, and it already reads GitHub through `gh api`. The window of 15 minutes is longer than the interval, so each delivery is in at least one read. The gauge is a snapshot, so a delivery that two reads find does not count twice in the alert.
- **One page for each hook.** At the peak of agent work on 2026-11-12, 100 deliveries came in 13 minutes, so a page can hold less than 15 minutes. Then the count is lower than the true count, but a refusal rate as on that day (39 of 100) still passes the limit of 5. More pages cost more requests in each round.
- **A Service gauge.** The gauge is on the Service's `/metrics` with the other `devops_cli_service_` series, by `repo` and `code`, so the alert names the repository. A code that the last read set and this read does not find goes to 0, because the metrics hold no call that removes a series.
- **A failed read fails the row.** The counter of failed rows, the failure ledger and `RoadmapServiceJobsFailing` show it. The gauge keeps the value of its last read, because no read gives no new count.
- **The token asks for `repository_hooks: read`.** The list of hooks and of deliveries needs the permission Webhooks (read). The App has read and write on every repository permission (ADR 0015), so the installation grants it.

## Rejected alternatives
- **A status lane row of its own.** #4052 gives each status page a row, so that a failed page fails only its row. The issue asks for the metrics row, and a new row changes the due table, its tests and the row list of the README for one read of GitHub, which the metrics row already does.
- **A token with its own permission set for this read.** The process keeps one installation token, and every gh and git child gets it from `core.process`. A second token needs a second pin and a second client for two reads.
- **The `last_response` of each hook.** `GET /repos/{owner}/{repo}/hooks` gives only the answer of the last delivery, so it shows no count, and a 202 after a 403 hides the 403.
- **The Access logs of Cloudflare.** The Service has no Cloudflare token, and the logs show only the refusals of Access, not a 502 of a Service that does not answer.
- **Change the Access policy in this change.** Only the owner changes an Access, WAF or DNS rule (O3).
