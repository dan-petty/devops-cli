# Design

## Decisions

- **A snapshot for each lane that needs one.** `lane_listing(state_dir, lane)` returns `IncrementalListing(FileSnapshotStore(state_dir / "listing-<lane>"))`. The status lane of each repository runs on one worker, so each file has one writer, as in the design of #3670. The triage lane keeps `listing`, which intake and the scoped intake share.
- **A sibling directory.** `listing-status` is beside `listing`, not in it, so no file of one lane is in the tree of another lane.
- **The status lane only.** The burn that the issue measured is on the status lane. The model lane keeps the whole read in this change.
- **The retry answer keys to `updated_at`.** `retry_asked_on(store, item)` keeps, for each issue URL, the `updated_at` of the last listing and the answer of `retry_asked`. An equal `updated_at` gives the kept answer with no request. The memo is a module dictionary, as the label times of `metrics` (#2919), reset by the test floor. It holds one entry for each issue at most.
- **Both readers use it.** The stop pass and the implement judge call `retry_asked_on`, so the rule of a retry has one place.

## Rejected alternatives

- **One shared snapshot for the status and triage lanes:** rejected. The two lanes run in separate threads, so two writers would race on one file.
- **Keep a last page that is not full in the session cache, so the comment listings get a 304:** rejected for this change. The cache holds 64 answers for all lanes and repositories, so the 19 comment pages leave it between rounds. A larger cache changes the memory bound of the Service.
- **Narrow the `implement` trigger to `status/*` labels:** not needed. With the snapshot and the memo, an idle round costs about one request.
