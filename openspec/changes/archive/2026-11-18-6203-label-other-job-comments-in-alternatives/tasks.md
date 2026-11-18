# Tasks: #6203

- [x] 1. Tests for job comment classification and alternatives request
  - [x] 1.1 Add tests in `tests/roadmap/test_roadmap_item_comments.py` for job label retention, separating person replies, keeping every job marker, fitting comments, and reading indexed comments with `read_comment`.
  - [x] 1.2 Update tool list assertions in `tests/roadmap/test_roadmap_alternatives.py` to include `read_comment`.
- [x] 2. Implementation in `src/devops_cli/roadmap/`
  - [x] 2.1 Update `HeldComment` and `held_comments` in `item_comments.py` to label `job` using `comment_job`.
  - [x] 2.2 Add `job_comments()` filter and `AlternativesJobForm` in `item_comments.py`.
  - [x] 2.3 Update `_request` in `alternatives.py` to populate `job_comments` using `fit_comments` and export `alternatives_request`.
  - [x] 2.4 Add `read_comment` to `AlternativesTools` in `alternatives.py`.
  - [x] 2.5 Update `src/devops_cli/ai/tasks/roadmap_alternatives.md` for `job_comments` and `read_comment`.
- [x] 3. Quality gates and OpenSpec archiving
  - [x] 3.1 Run tests and verify all checks pass.
  - [x] 3.2 Update OpenSpec delta spec and archive the change.
