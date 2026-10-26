# Tasks

## 1. Failing test

- [x] 1.1 Add failing tests in `tests/test_review_group_analysis.py` proving that `run_review_plan_job` rejects unparseable and invalid replies without caching, and does not retry empty replies: `uv run devops ci test tests/test_review_group_analysis.py -k "plan_reply"`

## 2. Implementation

- [x] 2.1 Implement `_judge_plan_reply` and shared `_chat_and_judge` in `src/devops_cli/review/analysis.py`: `uv run devops ci test tests/test_review_group_analysis.py`
- [x] 2.2 Update `_execute_single_group_job` and `run_review_plan_job` to execute through `_chat_and_judge`: `uv run devops ci test tests/test_review_group_analysis.py`

## 3. Verification and static checks

- [x] 3.1 Verify fail-to-pass check run passes against base: `uv run devops ci fail-to-pass --base origin/main`
- [x] 3.2 Verify full static checks pass: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
