# Design

## Decisions

- **The review keeps its own snapshot store under review-listing in the roadmap state directory.**: One writer for each snapshot file (#4854). A directory named listing-review would match the listing-<lane> prefix that `src/devops_cli/roadmap/run.py:2230:retired += [path for lane, path in lane_snapshot_dirs(state_dir).items() if lane not in running]` removes.
- **The review reads its own snapshot first, then the intake snapshot, then the window.**: A repository with an intake snapshot and no review snapshot reads the gap once more instead of the whole window.
- **The gap starts at the later of the snapshot watermark and the window start.**: A watermark 3 weeks before the window start reads about 40 listing pages for a 7-day window; the window start reads 19.
- **The review writes the earlier of the read start and the newest change, less the overlap, as its watermark.**: A record changed during the read stays at or after the watermark, and a local clock ahead of GitHub's skips no change: `src/devops_cli/roadmap/stores/listing_snapshot.py:66:_OVERLAP` is 60 seconds.
- **The review reads from the window start when the window starts before the first window that its snapshot covers.**: The review snapshot holds only the records of the windows it read, so a wider window would miss a change before its first window start; the full_at of the snapshot holds that first start.
- **A gap that starts after the watermark sets the full_at of the kept snapshot to the gap start.**: No change between the watermark and the gap start was read, so the snapshot holds each change only from the gap start. A later, wider window then reads from its own start, and gets the changes in that hole.
- **The runs reader reads the total of each created slice, then one count for each of four statuses.**: GitHub stops the total_count of a filtered runs list at 2,500. On 2026-11-22 a 30-day window gave the total 2,500 with 2,500 successful, 436 failed and 896 cancelled runs, and a 7-day window gave 1,853. So a slice at the cap splits in two halves by created time, and a 7-day window stays one slice of 5 requests in place of about 25 run pages.
- **Status counts above the total of a slice raise an error.**: A count that GitHub cut or changed then gives an error, not a wrong value.
- **The window counts the runs after its start second up to its end.**: GitHub reads both ends of a created range in whole seconds, so the start plus one second keeps a run of the start second out of two adjacent windows, as the listing facts do.
- **The fact's value is the map of the four statuses and its n is the total of the window.**: A run of another status appears in n and not in the map, and the catalog's definition says so.
- **The page cap of 1,000 goes, and the count cap of 2,500 takes its place.**: No code reads the page cap once the reader reads no page of runs; the limit table records the removal at `tests/roadmap/test_roadmap_limit_classes.py:50:REMOVED`. `CONST_ROADMAP_REVIEW_RUN_COUNT_CAP` holds the count cap with the class kept, and `review_runs_at_cap` names it when a one-second slice reaches it.

## Rejected alternatives

- **The intake store as the review's snapshot store.**: Two writers would write one file, which #4854 forbids; the review read ends at `src/devops_cli/roadmap/project_review/readers.py:112:return merged(held.issues, read_issues(changed_listing(held.watermark)))` and saves nothing.
- **A new snapshot class for the review.**: `src/devops_cli/roadmap/stores/listing_snapshot.py:91:class SnapshotStore` and `src/devops_cli/roadmap/stores/listing_snapshot.py:77:class ListingSnapshot` already hold the schema key, the watermark and the records.
- **The window start as the watermark of the next read.**: The next gap would cover the whole window again, and the snapshot would save nothing.
- **The window end with no overlap as the watermark.**: A local clock ahead of GitHub's would skip a change at the boundary; `src/devops_cli/roadmap/stores/listing_snapshot.py:66:_OVERLAP` keeps a 60-second overlap.
- **The watermark alone as the gap start.**: A stale watermark reads about 70 requests for a 7-day window, above the 45 of #4692.
- **The window start alone as the gap start.**: Each review would read the whole window again, and the snapshot would save nothing.
- **The review's own store only.**: A repository with an intake snapshot and no review snapshot would read the whole window once more.
- **The intake store only.**: The review writes no snapshot today, so each review reads the whole window again; that is the 49 requests of #6603.
- **The per-run pages and the split read.**: About 25 run pages leave no room under 45 for a 19-page listing.
- **One total count with no status filter for the value.**: It gives no count for each status, and the fact's definition asks for each status.
- **A directory named listing-review for the review store.**: `src/devops_cli/roadmap/run.py:2230:retired += [path for lane, path in lane_snapshot_dirs(state_dir).items() if lane not in running]` removes each listing-<name> directory that is no lane.
