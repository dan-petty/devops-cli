# Tasks

## 1. The module-test check names every module of a group in one result

Kind: fix. Changes: `tests/roadmap/stage/test_roadmap_stage_module_tests.py`, `src/devops_cli/roadmap/stage/stage_paths.py`.

- [x] 1.1 Write the tests first: a group that changes two modules and names neither test gets one problem for each module (fails on `origin/main`, which names one), a group that names the first test gets one problem for the second module, and a test that the first problem asks for and that also runs the second module answers both.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_module_tests.py`
- [x] 1.2 Replace `_unnamed_module_test` with `_unnamed_module_tests`, which gives each module of the group with no named test, and count each asked test as named for the later modules. `existing_test_problems` gives one problem for each pair.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_module_tests.py tests/roadmap/stage/test_roadmap_stage_module_test_order.py tests/roadmap/stage/test_roadmap_stage_paths.py tests/roadmap/stage/test_roadmap_stage_findings.py`

## 2. Documents

- [x] 2.1 State in `docs/roadmap/plan-check.md` and `docs/ROADMAP_WORKFLOW.md` that the `paths` gate names each such module of the group in one refusal.
  - Verification: `$ uv run devops ci --check --only docs`
