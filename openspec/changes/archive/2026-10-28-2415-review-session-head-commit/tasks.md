# Tasks

## 1. A review session records the checkout it read

- [x] Add failing tests: a path review of a clean tree, of a tree with a changed tracked file and of a tree with an untracked file records the head and the clean state; a target outside any checkout and a checkout with no commit record none; a head that is not a full commit name is refused; `review verify` keeps the checkout
  - Verification: `uv run devops ci test tests/review/test_review_on_merged_code.py`
- [x] Add `ReviewCheckout` and `ReviewSessionPayload.checkout`, read the checkout in `review/checkout.py` when the review starts, and write it into findings.json and candidates.json
  - Verification: `uv run devops ci test tests/review/test_review_on_merged_code.py tests/test_review_history.py tests/test_review_verification.py`
- [x] Describe the checkout in `docs/SELF_IMPROVEMENT.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. A session says whether it is on merged code

- [x] Add failing tests: only a clean path session at a commit on `origin/main` is on merged code; a session with no checkout is not; a commit that the repository does not hold raises `GitOperationError`
  - Verification: `uv run devops ci test tests/review/test_review_on_merged_code.py`
- [x] Add `is_on_merged_code`
  - Verification: `uv run devops ci test tests/review/test_review_on_merged_code.py`

## 3. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2415-review-session-head-commit`

## Workflow follow-up

- The fingerprint marker that keeps a finding from being filed twice: #2419.
- The `devops review intake <session>` hand-off, which calls `is_on_merged_code`: #2420.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
