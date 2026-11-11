# Tasks

## 1. Read test paths only from the specs of the plan
kind: behavior

- [x] 1.1 Write a failing test: a plan changes `src/devops_cli/sample.py`, whose base docstring names `tests/test_x.py`, the commit does not hold that file, and `check_proposal` returns no missing test path problem.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py`
- [x] 1.2 Remove the base docstring scan from `_stale_test_path_problems` in `src/devops_cli/roadmap/stage/stage_change.py` and delete `_docstrings_in`. Delete the tests of the docstring scan, and make the same-name hint tests use a spec path.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py tests/roadmap/stage/test_roadmap_stage_registry.py`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
