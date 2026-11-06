# Tasks

## 1. Give the Plan Check job the tiktoken cache

Reads: `tests/conftest.py`, `src/devops_cli/ai/context_budget.py`. Changes: `.github/workflows/pr-title.yml`, `tests/invariants/test_workflow_contracts.py`.

- [x] 1.1 In `tests/invariants/test_workflow_contracts.py`, add a test that the `plan-check` job runs the step `Prepare the tiktoken cache` after the checkout and before `Check the Plan`, that both steps set the same `TIKTOKEN_CACHE_DIR`, and that the script copies both committed encodings under the SHA-1 of their blob URL, and add the variable to the `env` that the existing test expects for `Check the Plan`
  - Verification: `uv run devops ci test tests/invariants/test_workflow_contracts.py` fails on the base
- [x] 1.2 In `.github/workflows/pr-title.yml`, add the step `Prepare the tiktoken cache` to the job `plan-check`, and set `TIKTOKEN_CACHE_DIR` on the step `Check the Plan`
  - Verification: `uv run devops ci test tests/invariants/test_workflow_contracts.py` passes
- [x] 1.3 Check that the script of the step fills a cache that `count_tokens` reads, and that an empty cache still raises `TokenCountError`
  - Verification: `uv run devops ci test tests/ai/test_context_budget.py` passes
