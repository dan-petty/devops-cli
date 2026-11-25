## ADDED Requirements

### Requirement: Own-write issue deliveries refresh the cached issue without waking a lane
When `roadmap_consumer` refuses an `issues` delivery with `CONST_SERVICE_STATUS_OWN_WRITE` because its sender is the App bot, it SHALL refresh the `brain-issue` entry from `payload.issue` whenever no entry exists, the stored entry has no `updated_at`, or `payload.issue.updated_at` is strictly greater than the stored `updated_at`, while still returning `CONST_SERVICE_STATUS_OWN_WRITE`, counting outcome `self`, making no GitHub request, and waking no lane or scoped update.

#### Scenario: A newer own-write issue webhook updates the brain entry
- **WHEN** `valkey-devops` holds an issue cached at `T0` with `Status: In Progress`, and an App-bot `issues` webhook arrives for that issue with `updated_at` at `T1 > T0` and `Status: In Review`
- **THEN** the route answers HTTP 200 with `{"status": "ignored_own_write"}`, counts outcome `self`, wakes no lane, and updates `valkey-devops` to `Status: In Review`

#### Scenario: A stale or same-second own-write webhook does not clobber a fresher cached entry
- **WHEN** `valkey-devops` holds an issue cached at `T1`, and an App-bot `issues` webhook arrives with `updated_at <= T1` (or with `comment` present or `pull_request` set)
- **THEN** the route answers HTTP 200 with `{"status": "ignored_own_write"}` and keeps the existing brain entry unchanged
