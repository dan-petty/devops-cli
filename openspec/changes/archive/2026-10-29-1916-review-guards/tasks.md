# Tasks

## 1. Retire the review guards file

- [x] Add failing tests: a corpus holds no `.devops/review.md`, a pull request checkout takes none from its base, and a generated `AGENTS.md` names none
  - Verification: `uv run devops ci test tests/test_review_defects.py tests/test_review_scope.py tests/test_agents_md_claims.py`
- [x] Delete `.devops/review.md`, `nearest_review_conventions`, `CONST_REVIEW_CONVENTIONS_FILE`, the `devops ai agents` route, the prompt-class entry, and the copies in the corpus and the pull request checkout; move the tests that used the file as an example to `AGENTS.md`, and delete the guard tests and their snapshot
  - Verification: `uv run devops ci test tests/test_review_project_conventions.py tests/test_review_defects.py tests/test_review_scope.py tests/test_batch_2_review_defects.py tests/test_git_operations.py tests/test_review_profile.py tests/test_agents_md_claims.py`
- [x] Remove the file from `ai/tasks/review.md` and from the current guidance in `docs/SELF_IMPROVEMENT.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1916-review-guards`

## Workflow follow-up

- #2594: no review prompt reads the target's `AGENTS.md`, and the profile's conventions digest is never set.
- Pending a person: in `AGENTS.md`, the row "run a review, or work on verdicts and suppressions" says "review guards are in `.devops/review.md`". Change it to "suppressions are in `.devops/review.toml`".
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
