# Tasks

## 1. Use _read_at for Ready item comment re-selection

> Kind: behavior

- [x] 1.1 Update `tests/roadmap/refine/test_roadmap_refine_ready_edits.py` to verify `RefineRecordKey.READ_AT` (`read_at`) and in-flight comments between `read_at` and refine's marker comment fail against the broken `refine.py`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_ready_edits.py tests/roadmap/refine/test_roadmap_refine_event_comment.py tests/roadmap/test_roadmap_explain.py`
- [x] 1.2 Replace `_repeated_at(item)` in `_has_trusted_comment_since_last_round` (`src/devops_cli/roadmap/refine/refine.py`) with `_since_wait_start` and `_read_at`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_ready_edits.py tests/roadmap/refine/test_roadmap_refine_event_comment.py tests/roadmap/test_roadmap_explain.py`

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
