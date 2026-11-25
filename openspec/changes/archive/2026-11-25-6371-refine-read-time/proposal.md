# Proposal: #6371

## Why
A refine round reads issue comments before its model calls and posts its comment afterward. When a person replies between the read and the comment, that reply is older than the new refine comment, so subsequent rounds never end the wait or send the reply to the model. PR `#6353` (`#6196`) fixed this only for rounds that post no comment (`refine.repeated_at`).

## What Changes
- Add `RefineRecordKey.READ_AT` (`"refine.read_at"`) in `src/devops_cli/roadmap/stores/store.py` and record the comment-read time on every written refine result (`_refine_marks` in `src/devops_cli/roadmap/refine/refine.py`), stopping writes to `RefineRecordKey.REPEATED_AT` while leaving failed rounds without a read-time write.
- Update wait start (`_wait_start`, `_since_wait_start`, `_question_ends_wait`) and model reply selection (`_replies_for_model`) in `src/devops_cli/roadmap/refine/refine.py` to use `refine.read_at` (excluding refine's own comments as wait-ending replies) and to fall back to refine's last comment when an item has no `refine.read_at`.
- Update `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/refine/test_roadmap_refine_event_comment.py`, and OpenSpec `roadmap-refine/comments` and `roadmap-refine/waits`.

## Capabilities

### Modified Capabilities
- `roadmap-refine/comments`: record `refine.read_at` on every written round instead of `refine.repeated_at`, send replies made between read and comment, ignore refine's own comment and at-or-before replies, keep failed rounds without `refine.read_at`, and fall back when absent.
- `roadmap-refine/waits`: anchor cited-code, named-cause, and reply wait checks at `refine.read_at` (falling back to `refine.commented_at`).
- `roadmap-job-comments`: record `refine.read_at` when the store refuses a repeated refine comment.

## Impact
- `src/devops_cli/roadmap/stores/store.py`
- `src/devops_cli/roadmap/refine/refine.py`
- `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`
- `tests/roadmap/refine/test_roadmap_refine_event_comment.py`

## Feasibility
Confirmed against `src/devops_cli/roadmap/refine/refine.py`: `_refine_marks` at line 4401 writes `REPEATED_AT` only when `r.repeated` is true, and `_since_wait_start` (line 2799) and `_replies_for_model` (line 3971) slice `comments[marked[-1] + 1:]` after refine's last comment.

## Existing Tool Considered
The alternatives check of 2026-11-19 recorded `none`. No external library provides per-item read watermarks inside the refine record; cost is about 25k tokens and half a day to build.
