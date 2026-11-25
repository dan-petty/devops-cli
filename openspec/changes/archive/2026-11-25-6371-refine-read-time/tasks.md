# Tasks

## 1. Behavior (RED -> GREEN)

- [x] 1.1 Add failing tests in `tests/roadmap/refine/test_roadmap_refine_event_comment.py` covering a reply between read and comment (`T+1`), at-or-before read (`<= T`), refine's own comment (`T+2`), a failed round not setting `READ_AT`, and legacy `REPEATED_AT` fallback.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_event_comment.py`
- [x] 1.2 Add `RefineRecordKey.READ_AT` in `src/devops_cli/roadmap/stores/store.py` and update `src/devops_cli/roadmap/refine/refine.py` (`_read_at`, `_wait_start`, `_since_wait_start`, `_question_ends_wait`, `_replies_for_model`, `_refine_marks`, `_apply_refined`).
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_event_comment.py`

## 2. Documents

- [x] 2.1 Update `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`, and OpenSpec deltas for `refine.read_at` and run `devops ci docs` + static checks + `fail-to-pass`.
  - Verification: `$ uv run devops ci docs`
