# Tasks

## 1. Leave the chat personas out of the digest

Reads: `src/devops_cli/ai/personas/__init__.py`. Changes: the same file and `tests/ai/review/test_review_profile.py`.

- [x] 1.1 Hash only `ai/tasks/` and drop the `personas_dir` parameter.
- [x] 1.2 Update the digest tests.
  - Verification: `$ uv run devops ci test tests/ai/review/test_review_profile.py` passes
