# Tasks

## 1. Behavior

- [ ] 1.1 Write the failing test that the replay of a step starts the Python of the venv of the checkout
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_fail_to_pass.py`
- [ ] 1.2 Pass `checkout_python(root)` from `replay_group_tests` to `replay_on_base`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_fail_to_pass.py tests/ci/test_fail_to_pass.py`

- [ ] 1.3 Write the failing test for a step in the current folder, then make the path absolute in `checkout_python`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_fail_to_pass.py`

## 2. Documents

- [ ] 2.1 Name the interpreter of the base replay in the `roadmap-implement-runner` spec and in `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops openspec check`
