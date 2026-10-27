# Tasks

## 1. Task gateway URLs recording in configure-urls

- [x] 1.1 Write failing tests for task gateway URLs persistence and reporting in `tests/test_k8s_networking.py`, verified with `uv run devops ci test tests/test_k8s_networking.py`
- [x] 1.2 Update `_update_task_gateway_urls` to accept `configured` and record changed task gateway URLs, verified with `uv run devops ci test tests/test_k8s_networking.py`
- [x] 1.3 Regenerate documentation with `uv run devops docs generate --sync-readme`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
