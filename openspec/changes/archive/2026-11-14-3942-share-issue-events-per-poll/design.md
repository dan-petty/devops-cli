# Design

## Context

`run_due_jobs` reads the changes of its lane with `_fetch_filtered_changes`, which calls `store.changes_since` at the oldest cutoff of the lane's rows. Each lane builds its own store, so a cache on a store reaches one lane.

## Goals

- One issue-events request for one poll of a repository.
- One verdict for each lane, at its own cutoff.

## Decisions

- **`PollCache` in `run.py`, shared by `service_jobs`.** The lane partials hold the one object. The key is the repository and the poll time, which is `TriggerBatch.first_at` or the round time for a dict batch.
- **One entry for each repository.** A round of the next poll replaces the entry, so the cache never outlives the poll. This rule replaces a TTL, which can hide an event from the next poll.
- **The lock covers the read.** Two lanes of one poll cannot send the same request.
- **A later cutoff filters the cached list.** A lane with an earlier cutoff than the cached one reads again and replaces the entry, because the one listing must hold every event at or after its cutoff.

## Risks

- A lane that needs an earlier cutoff after the cache is filled sends a second request. The cache then covers that cutoff for the remaining lanes.

## Tests

- Three lanes of one poll send one request for `issues/events`.
- The next poll sends a new request.
- A later cutoff filters one cached listing.
- Two repositories keep one listing each.
