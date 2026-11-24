# Tasks

## 1. Behavior

- [x] 1.1 Add test cases verifying test-first stops produce `FailureClass.PLAN_DEFECT`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/implement/test_roadmap_implement_step_fail_to_pass.py`
- [x] 1.2 Update `_Failure` instantiations and `_repair_ask` in `implement_step.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_fail_to_pass.py`
- [x] 1.3 Update `_PLAN` regex pattern in `failure.py` to match test-first messages
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py`

## 2. Documents

- [x] 2.1 Update spec delta for roadmap-failure-taxonomy
  - Verification: `$ uv run devops openspec check`
