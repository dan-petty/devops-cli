# Tasks

## 1. Behavior

- [x] 1.1 Add failing behavior and contract tests in `tests/roadmap/intake/test_roadmap_intake_reason_comment.py`, `tests/roadmap/intake/test_roadmap_intake_sub_issues.py`, `tests/roadmap/refine/test_roadmap_refine_deferred.py`, and `tests/roadmap/test_roadmap_retitle.py`
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_reason_comment.py tests/roadmap/intake/test_roadmap_intake_sub_issues.py tests/roadmap/refine/test_roadmap_refine_deferred.py tests/roadmap/test_roadmap_retitle.py`
- [x] 1.2 Implement shared `issue_references`, `NewCandidate.apart`, Priority/Related comment filtering, and After-line removal in `body_hash.py`, `intake.py`, `refine.py`, `retitle.py`, and `messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/intake/ tests/roadmap/refine/test_roadmap_refine_deferred.py tests/roadmap/test_roadmap_retitle.py`

## 2. Documents

- [x] 2.1 Verify docs and OpenSpec checks pass with no stale references
  - Verification: `$ uv run devops ci docs && uv run devops openspec check`
