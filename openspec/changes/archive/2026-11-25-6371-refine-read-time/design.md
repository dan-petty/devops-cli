# Design

## Decisions
- Add `RefineRecordKey.READ_AT` (`"refine.read_at"`) in `src/devops_cli/roadmap/stores/store.py` and keep `RefineRecordKey.REPEATED_AT` in the enum only so existing job records parse. Write `READ_AT` on every non-failed refine result (`_refine_marks`), clear `REPEATED_AT` when present on an updated record, and write neither on `_failed_round` / `_record_failure` / `r.failure is not None`.
- Use `_read_at(item)` in `_wait_start`, `_since_wait_start`, and `_question_ends_wait`, falling back to refine's last comment (`marked[-1]` / `commented_at`) when `READ_AT` is absent (for example, legacy items holding only `REPEATED_AT`). Exclude refine's own comments (`comments_without_jobs`) when checking wait-ending replies so a comment posted at `T+2` after `read_at=T` never ends the wait.
- In `_replies_for_model`, pass `read_at=_read_at(item)` so when `READ_AT` is present the model receives every non-job comment that follows refine's last comment or has `created_at > read_at`, while legacy records without `READ_AT` receive replies following refine's last comment.

## Rejected alternatives
- Reuse `RefineRecordKey.REPEATED_AT`: the key name describes repeated results only and misleads readers when every written round sets it.
- Filter without excluding refine's own comments after `read_at`: refine's own comment posted at `T+2` is newer than `read_at=T` and would re-trigger rounds indefinitely.
- Read `REPEATED_AT` as the read time on legacy items: Issue `#6371` falls back to refine's last comment once so no round writes or reads `REPEATED_AT` going forward.
