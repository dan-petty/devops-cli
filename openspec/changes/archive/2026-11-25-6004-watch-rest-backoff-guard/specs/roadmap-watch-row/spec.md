## ADDED Requirements

### Requirement: REST fallback tests backoff before reading check runs
In the REST fallback path (`_process_rest_pulls`), `watch` SHALL test whether the pull request head and base match an active failed-head backoff entry in the watch ledger before calling `read_check_runs`, skipping check-run requests and recording the pull request in `failed_heads` while counting it in `watched`.

#### Scenario: Failed head in backoff under GraphQL hold triggers zero check-run reads
- **WHEN** GraphQL quota is on hold, `watch_round` falls back to REST for an open pull request whose ledger entry holds verdict `FAILED`, the same head SHA and base branch, and `next_read_at` in the future
- **THEN** zero REST requests are sent to `/check-runs`, the result includes the pull request number in `failed_heads`, and `watched` counts it
