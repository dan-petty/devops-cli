# Proposal: #4854

## Why

#4854: on 2026-11-11 at 20:45Z the roadmap Service used all of its GitHub budget (3,000 requests an hour), and no round started from 20:01Z to 20:48Z. In that hour the row `implement` sent 820 requests for devops-cli and the row `metrics` sent 611, although no runner Job ran and no item was Staged.

- The status lane (`metrics`, `implement`, `stage_ready`, `pr_conflicts`, `release_comments`) reads the whole `state=all` listing in each round: 49 pages. Only the triage lane reads through the listing snapshot of #4448 and #3670. ETags do not help, because each new issue changes every page of the listing.
- The stop pass lists the comments of each Blocked stop in each round: 19 stops in 15 rounds give 285 requests an hour. The comments change only when the issue changes.

## What Changes

- `service_jobs` gives the status lane its own `IncrementalListing`, with `FileSnapshotStore` in `listing-status` of the state directory (`lane_listing`). A round with a kept snapshot reads only the issues changed since the watermark, and the whole listing once in 24 hours. The model lane keeps the whole read.
- `retry_asked_on` lists the comments of a stopped item only when its `updated_at` is not the one of the last listing that the process holds for the issue. The stop pass and the implement judge use it. A new comment moves `updated_at`, so a retry still clears at the next round.
- The behavior of the Service changes, so the change carries deltas of `roadmap-intake-listing` and `roadmap-implement-job`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-intake-listing`: the status lane reads through a snapshot of its own.
- `roadmap-implement-job`: a stop lists its comments again only when its issue changed.

## Impact

- `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/implement/implement.py`, `tests/conftest.py`
- `k8s/README.md`, `docs/roadmap/intake.md`
- A second snapshot file for each repository on the volume of the Service: about 24 MB for this repository. Each status round parses and writes it, about 2 s (measured for the triage lane in #3670).
- Expected saving at the measured hour: about 720 requests an hour from the listing (`implement` 528, `metrics` 192) and about 285 from the stop comments. The row `implement` goes from 820 to about 20 requests an hour.

## Feasibility

- Source at `origin/main` (7f099217): `service_jobs` passes `listing=intake_listing(state_dir)` to the triage lane only (`src/devops_cli/roadmap/run.py`). `_clear_one` calls `store.comments_on(item.number)` for each stop before it checks a rule (`src/devops_cli/roadmap/stop_clear.py`).
- Prometheus `devops_cli_github_requests_total`, 1 hour to 2026-11-11 20:45Z: `implement` 820, `metrics` 611 for devops-cli. Per round, `implement` sent 55 to 57 requests: 49 listing pages and 19 comment listings (11 x 68 + 4 x 19 = 824). The 304 share of `implement` fell from 34% (24 hours) to 6% (1 hour), with 37 new issues and pull requests in the hour.
- Loki: each `implement` round of the hour reported 0 Jobs, cleared 0 stops and created none.
- `IssueRecord` documents that any write to an issue, a comment included, moves `updated_at`. The snapshot reads changes by `updated_at`, so the `updated_at` of a status-lane item is current at each round.
- The new tests fail on the base: the second status round reads `state=all&per_page=100` again, and a later stop pass lists the comments of each stop again.

## Existing Tool Considered

- The `since` parameter of the GitHub REST issue listing, and `IncrementalListing` with `FileSnapshotStore` of #4448: reused. The change adds no library and no new mechanism.
- Conditional requests through the session cache: rejected for the listing (each new issue changes the ETag of every page, #4552). For the comments, the session keeps no last page, and its 64 answers serve all lanes and repositories, so the comment pages leave the store between rounds.
- #4668 can later keep the snapshot in Valkey, and #4415 can make a retry comment an event.
- Cost: about 150,000 tokens and 2 hours to build; about 5,000 tokens a month to keep and fix.
