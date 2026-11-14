# Proposal

## Why

Each lane of a repository that has a due rule reads `repos/<repo>/issues/events` in one poll. In a busy repository every read is a 200 answer and counts against the GitHub request budget. The request is the third largest source of requests that no job row sends (#3942).

## What Changes

- `PollCache` holds the issue changes of each repository for one poll, keyed by the time of the poll.
- The lanes of one repository share the cache through the lane partials that `service_jobs` builds.
- A lane with a later cutoff filters the one listing; a lane with an earlier cutoff replaces it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-lanes`: The lanes of one poll share one read of the issue events.

## Impact

- Code: `src/devops_cli/roadmap/run.py`
- Tests: `tests/roadmap/test_roadmap_run_github_requests.py`

## Feasibility

- `service_jobs` builds every lane partial and can share one `PollCache`.
- `TriggerBatch.first_at` names the poll, and a dict batch uses the round time.
- Verification commands: `uv run devops ci test tests/roadmap/test_roadmap_run_github_requests.py tests/roadmap/test_roadmap_run_lanes.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The store and the GitHub session already exist. The change adds one cache object with a lock, about 60 lines with tests. No library covers a per-poll request cache, and a library cache with a TTL can hide an event from the next poll (ADR 0003).
