# Tasks

## 1. Behavior

- [x] 1.1 Write the failing guard: the timeout test asserts that `clock.waits` is not empty
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_failure_class.py`
- [x] 1.2 Replace the module `clock` fixture with an autouse wrapper over the shared `ClockFake`, and use `_waited` for the recorded failure times
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_failure_class.py`
