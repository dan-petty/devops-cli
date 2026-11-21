# Tasks

## 1. Behavior

- [x] 1.1 Write the failing test that the replay of a step starts the Python of the venv of the checkout
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_fail_to_pass.py`
- [x] 1.2 Pass `checkout_python(root)` from `replay_group_tests` to `replay_on_base`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_fail_to_pass.py tests/ci/test_fail_to_pass.py`

## 2. Documents

- [x] 2.1 Name the interpreter of the base replay in the `roadmap-implement-runner` spec
  - Verification: `$ uv run devops openspec check`
