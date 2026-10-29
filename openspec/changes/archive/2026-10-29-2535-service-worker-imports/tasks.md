# Tasks

## 1. The Service imports the refine job's dependencies before its worker threads start

- [x] 1.1 Write `test_the_refine_import_is_at_module_level_not_lazy_in_the_adapter` in `tests/test_roadmap_run.py`, and verify that `uv run devops ci test tests/test_roadmap_run.py -k module_level_not_lazy` fails on the base: the import was inside the adapter, and none was at module level
- [x] 1.2 Move the import of `devops_cli.roadmap.refine` from the body of `_run_refine_adapter` to module level in `src/devops_cli/roadmap/run.py`, and verify that `uv run devops ci test tests/test_roadmap_run.py tests/test_roadmap_refine.py tests/test_cli_startup_imports.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
