# Tasks

## 1. Behavior

- [x] 1.1 Record the base worktree that `git worktree add` makes, and identify a base gate run by that recorded path, not by the folder name
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`
- [x] 1.2 Add the tests for a recorded base worktree, a subfolder of it, an unrecorded folder named `tree`, and a checkout root named `tree`
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`

## 2. Documents

- [x] 2.1 Mark the change as a test-only change with `skip_specs`
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
