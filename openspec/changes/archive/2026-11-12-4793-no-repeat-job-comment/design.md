# Design

## Decisions

- The guard reads the comments of the item and keeps no hash in the job record. A hash in the record needs a second write for each comment, and a stop between the two writes either posts the comment again or keeps a hash of a comment that GitHub never got. The comments on GitHub are the truth (ADR 0021).
- A repeat counts only in the trailing run of comments that hold the same marker. The readers of "the comments after the job's last comment" (`retry_asked`, `replies_after_marker`, `_stage_return`) then read the same comments as when the repeat posted, so a person's reply is never read twice. Replayed on open items, the plan's rule (any comment of the job in 7 days) refuses 29 comments and this rule 9: the other 20 follow a person's reply (12) or a stage comment (8), and the job's answer to these posts.
- The window is 7 days, as the issue asks. A wait that lasts longer gets one comment each week.
- The fingerprint leaves out each run of 7 or more lower-case hexadecimal digits that holds a digit: commit SHAs, image digests and run IDs. A number with fewer digits, such as an issue number, stays, so a changed blocker posts.
- Refine records `refine.repeated_at` after the store refused its comment, not with the marks before the comment. A stop between the marks and the comment then leaves no mark, so the next round looks at the item again and posts the comment. The time is the clock of refine, as for `refine.failed_at`.
- The start of a wait is the later of `refine.repeated_at` and refine's last comment. A later comment of refine moves the start past an old mark, so no write clears the mark.
- The label is `row`, with 6 values: retitle, refine, alternatives, intake, stage and implement, the names of the rows of these jobs in the Service. The issue asks for `job`, but the collector sets `job` from the resource, so an attribute `job` never reaches Prometheus (#3240, `test_no_emit_sends_an_attribute_that_the_resource_sets`).

## Rejected alternatives

- A hash in the job record (the plan of the issue): one more write for each comment, and wrong after a stop between the writes.
- A per-job guard in each caller: 34 call sites, and a new job could forget it.
- `refine.repeated_at` in the marks that refine writes before its comment: a stop after the marks leaves the item waiting with no comment.
