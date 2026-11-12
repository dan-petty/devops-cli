# Tasks

## 1. A refused kept plan uses no gate return (behavior)

- [x] 1.1 Write failing tests: a kept plan that the gates refuse leads to 1 + `roadmap.stage.gate_returns` planner asks and a `stage gate returns:` line without the kept plan, the new first reply gets the kept plan and its problem, and no new first reply starts once the Service stops.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_record.py`
- [x] 1.2 In `_Planner._gated`, gate the kept plan before the return loop, and on a refusal ask the planner for a new first reply with the kept plan and its problem, after the stop check. Add `_Refused.returned` and use it in `_returned`. Give the facts test one scripted reply more.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_record.py tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py tests/roadmap/stage/test_roadmap_stage_repair_return.py`

## 2. Documents

- [x] 2.1 State in `docs/roadmap/stage.md` that a refused kept plan uses no return and that the new first reply does not start after the Service stops.
  - Verification: `$ uv run devops ci docs`
