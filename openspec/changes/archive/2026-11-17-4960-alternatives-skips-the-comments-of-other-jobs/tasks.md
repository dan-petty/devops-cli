# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests for an intake comment and a person reply, and for a refine
      comment after a check.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py`
- [x] 1.2 Share refine's job-marker filter and apply it to the alternatives request before the cap.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py`

## 2. Documents

- [x] 2.1 Update the `roadmap-alternatives` specification.
  - Verification: `$ uv run devops openspec check`
- [x] 2.2 Archive the change into the main specification.
  - Verification: `$ uv run devops openspec archive 4960-alternatives-skips-the-comments-of-other-jobs`
