# Tasks

## 1. Light check of the decision modes

Kind: behavior. Reads: `src/devops_cli/roadmap/decision_registry.py`, `src/devops_cli/roadmap/stage/stage_jev_screen.py`, `tests/config/test_decision_point_settings.py`. Changes: `src/devops_cli/roadmap/decision_table.py`, `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/roadmap/decision_registry.py`, `src/devops_cli/config/settings.py`, `tests/gate/startup_imports.py`, `tests/roadmap/test_roadmap_decision_table.py`, `tests/roadmap/test_roadmap_decision_point.py`, `tests/roadmap/stage/test_roadmap_stage_jev_screen.py`, `tests/config/test_decision_point_settings.py`.

- [x] 1.1 Add the decisions probe to `tests/gate/startup_imports.py` and the tests of `tests/roadmap/test_roadmap_decision_table.py`, and watch them fail on the base: the probe gives `[true, {"stage.verify_screen": "shadow"}]`
  - Verification: `$ uv run devops ci --only startup-imports`
- [x] 1.2 Add `POINT_CUTS` and `check_modes` in `decision_table.py`, call `check_modes` from `RoadmapConfig._check_decisions`, and delete `Registry.check` and `DecisionPoint.fitted`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_table.py tests/roadmap/test_roadmap_decision_point.py tests/config/test_decision_point_settings.py tests/roadmap/stage/test_roadmap_stage_jev_screen.py`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
