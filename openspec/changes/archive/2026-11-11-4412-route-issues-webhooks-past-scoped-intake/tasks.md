# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests of the keys and the wake
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_webhook_keys.py tests/server/test_server_service.py`
- [x] 1.2 Declare the batch keys, add the wake rule and the lane of `enqueue_trigger`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_webhook_keys.py tests/server/test_server_service.py`

## 2. Documents

- [x] 2.1 Correct the lane in step 8 of `k8s/README.md` and state the model-lane wake
  - Verification: `$ uv run devops ci docs`
