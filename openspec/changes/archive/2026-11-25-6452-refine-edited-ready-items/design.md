# Design

## Decisions
- **Compare text outside the refine section against `refine.body_hash`**: `_ready_body_edited(item)` compares `body_hashes(item.body)[0]` against `item.job_record.get(RefineRecordKey.BODY_HASH)` when `refine.body_hash` is recorded. Requiring a non-None `refine.body_hash` keeps unrefined backlog `P2`/`P3` `Ready` items excluded when `unrefined_ready=False`.
- **Pass `comments_on` and `trusted` into `_refinable`**: Callers (`_select_round` and `refine_left_out`) own the `RoadmapStore` and pass a cached raw comment reader plus a trust predicate (`is_person_comment` with the run's actor). `_refinable` stays pure and checks only trusted person comments created after the last refine round (`refine.repeated_at` when set and newer than any refine marker comment, else the newest comment carrying `CONST_ROADMAP_REFINE_COMMENT_MARKER`). Items with `item.comments == 0` skip the store comment read in `_select_round` and `refine_left_out`.
- **Report due reasons in `devops roadmap explain`**: Add `explain_line_yes_reason` (`"{job} job: yes. {reason}"`) for verdicts where `takes` is `True` and `reason` is non-empty, keep `explain_line_yes` unchanged when `reason` is empty, and add `refine_due_reason` so `_refine_verdict` names the body edit or the new trusted comment on `Ready` items without changing `refine_left_out`'s `None` return contract.

## Rejected alternatives
- **Checking comments directly inside `_refinable` via a `RoadmapStore` parameter**: Adds store coupling to `_refinable` and makes isolated unit tests harder.
- **Triggering on any comment count increment (`refine.comments_seen`)**: `refine.comments_seen` is not written on `Ready` items and cannot distinguish bot or untrusted comments from trusted person comments.
- **Re-refining only person-filed `Ready` items**: Leaves bot-filed `Ready` items blind to follow-up trusted person comments even though `refine.body_hash` and refine comments exist on all refined items.
