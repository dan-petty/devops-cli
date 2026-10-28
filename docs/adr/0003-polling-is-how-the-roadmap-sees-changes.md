# Polling is how the roadmap sees changes; webhooks only cut latency

Amended on 2026-10-28 by [ADR 0016](0016-labels-hold-the-roadmap-items-fields.md). Labels hold Status, Priority, Value and Effort, so a change of a field is a `labeled` or `unlabeled` issue event. The poll reads those events, and the repository webhook sends them. No roadmap job reads a board.

The service finds changes by polling GitHub on a short tick, using conditional requests so an unchanged answer costs nothing, and treats a repository webhook only as a hint that makes a job due sooner. GitHub sends no webhook when a board owned by a personal account changes, so edits to status, priority, Value and Effort can only be found by polling, and GitHub never retries a failed delivery. Polling is needed anyway, and making it the source of truth means a missed webhook only delays a job until the next tick.

## Considered Options

- **Webhooks as the source of truth, plus GitHub's recommended job that redelivers failed deliveries**: rejected because board changes would still need polling, leaving two paths to the same result.
- **Polling only**: rejected because issue and pull request events would wait for the next tick.

## Consequences

- The webhook endpoint is exposed through the existing Cloudflare Tunnel on a single path; every other route of the service stays private.
- Removing the poll "because we have webhooks" would silently stop board changes from triggering anything.
- Every poll and every webhook goes to both of a repository's lanes, the release lane (close, reprioritize, metrics) and the model lane (intake, refine) (#1532). Each lane judges only its own rows against the shared `schedule.json`, so a release-lane round never waits for a model-bound one, and the shared round pause holds both.
