# Tasks

## 1. Order the tests of a module

Reads: `src/devops_cli/roadmap/stage/stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`. Changes: `src/devops_cli/roadmap/stage/stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_module_test_order.py`.

- [x] 1.1 Write the failing tests: mirror test first, direct importer before package importer, mirror folder before package importer, path order for equal tests, test of another changed module last, the problem names the mirror test
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_module_test_order.py` fails on the base
- [x] 1.2 Return the importers with their names from `_importing_tests` and sort the record nearest first
  - Verification: `uv run devops ci test tests/roadmap/stage` passes
