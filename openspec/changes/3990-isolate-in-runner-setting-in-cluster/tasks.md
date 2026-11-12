# Tasks

## 1. The floor removes the runner variable from each test

Kind: behavior. Changes: `tests/invariants/test_hermetic_floor.py`, `tests/conftest.py`, `tests/roadmap/implement/test_roadmap_implement_records.py`.

- [x] 1.1 Write a failing test: in a pytester run whose outer environment sets `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER` to `true`, the inner test sees no such variable, and `roadmap.implement.in_runner` is false.
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py`
- [ ] 1.2 Remove the variable in `isolate_devops_cli_config` of `tests/conftest.py`. Delete the removal in `test_the_job_runs_no_step_unless_the_setting_says_it_is_in_a_runner`.
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py tests/roadmap/implement/test_roadmap_implement_records.py`
- [ ] 1.3 Run the tests that failed in the runner pod with the variable set.
  - Verification: `$ env DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER=true uv run devops ci test tests/roadmap/implement/test_roadmap_implement_outside.py tests/roadmap/implement/test_roadmap_implement_command.py tests/roadmap/implement/test_roadmap_implement_job.py`

## 2. Documents

Kind: documents. Changes: `docs/TESTING.md`.

- [ ] 2.1 Name the removal of the runner variable in the hermetic floor of `docs/TESTING.md`.
  - Verification: `$ uv run devops ci --check --only docs`
