# Tasks

## 1. The section and the event line (behavior)

- [x] 1.1 Write the failing tests: the section holds the watched files and the new items, the comment holds no line of the section, the frame names the section, and the stage and implement frames keep the question text.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_event_comment.py tests/roadmap/test_owner_question.py tests/roadmap/refine/test_roadmap_refine_next_step.py`
- [x] 1.2 Write the section parts and the event line in `refine.py`, `owner_question.py` and `messages.py`, and delete `_with_block_paths`, `_with_notice`, `_with_deferrals` and the old comment texts.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_event_comment.py tests/roadmap/test_owner_question.py tests/roadmap/refine/test_roadmap_refine_next_step.py tests/roadmap/refine/test_roadmap_refine_cited_paths.py tests/roadmap/refine/test_roadmap_refine_deferred.py tests/roadmap/refine/test_roadmap_refine_owner_question.py tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py tests/roadmap/refine/test_roadmap_refine_selection.py`

## 2. The gate on a changed result and the start of a wait (behavior)

- [x] 2.1 Write the failing tests: an unchanged round posts no comment and records `refine.repeated_at`, a changed step or section posts, the wait starts at the round with no comment, the wait text comes from the section and the replies, a closed frame holder moves the frame, and the dry run names the gate.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_event_comment.py tests/roadmap/refine/test_roadmap_refine_person_wait.py tests/roadmap/test_roadmap_dry_runs.py`
- [x] 2.2 Add the gate, `refine.frame`, the anchor of the wait at `refine.repeated_at`, the wait text from the section and the question hash in the fingerprint of the repeat guard in `refine.py`, `store.py`, `comment_repeat.py` and `request_plan.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/ tests/roadmap/stores/test_comment_repeat.py tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_repair.py tests/roadmap/test_owner_question.py`

## 3. Documents

- [x] 3.1 Describe the section, the event line, the gate and `refine.frame` in `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/inbox.md`, and regenerate the generated documents.
  - Verification: `$ uv run devops docs generate --check`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
