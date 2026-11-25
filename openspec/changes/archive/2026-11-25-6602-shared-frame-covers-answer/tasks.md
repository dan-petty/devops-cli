# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests for shared-frame replies, local replies preserved, and bot/job replies ignored (`tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/refine/test_roadmap_refine_covers_check.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/refine/test_roadmap_refine_covers_check.py`
- [x] 1.2 Add `linked_frame_item` to `src/devops_cli/roadmap/owner_question.py` and pass shared frame replies via `answer_of` in `covers_question` and `refine_one_item` (`src/devops_cli/roadmap/refine/refine.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/refine/test_roadmap_refine_covers_check.py tests/roadmap/test_owner_question.py`

## 2. Documents

- [x] 2.1 Validate OpenSpec change and static quality gates
  - Verification: `$ uv run devops openspec check`
