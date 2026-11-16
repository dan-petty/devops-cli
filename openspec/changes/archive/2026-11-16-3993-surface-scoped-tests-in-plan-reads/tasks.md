# Tasks

## 1. Scoped tests adapter and integration

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_scoped_ci.py`, `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/roadmap/stage/stage_scoped_tests.py` (new), `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_scoped_tests.py` (new).

- [x] 1.1 Write tests for scoped tests adapter and stage integration
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_scoped_tests.py`
- [x] 1.2 Implement scoped tests adapter and wire into stage planning
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_scoped_tests.py`
- [x] 1.3 Verify stage plan reads contain scoped tests and missing test warnings
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scoped_tests.py`
