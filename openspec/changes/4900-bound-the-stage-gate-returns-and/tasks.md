# Tasks

## 1. The returns of a refused stage reply have a ceiling and stop with the Service (behavior)

- [x] 1.1 Write failing tests: a `gate_returns` value of 4 fails the settings load, and a refused reply gets no return once the Service stops.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_repair_return.py`
- [x] 1.2 Add `CONST_ROADMAP_STAGE_GATE_RETURNS_CEILING` (3) as the `le` of `roadmap.stage.gate_returns`, call `raise_if_service_stops` before each return in `_Planner._returned`, and add the constant to the table of limit classes.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_repair_return.py tests/roadmap/test_roadmap_limit_classes.py`

## 2. Documents

- [x] 2.1 Regenerate the settings documents, and state the ceiling and the stop in `docs/roadmap/stage.md`, `k8s/README.md` and the module docstring of `src/devops_cli/roadmap/service_stop.py`.
  - Verification: `$ uv run devops ci docs`
