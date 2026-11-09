# Tasks

## 1. Trace facts of a kept plan

- [ ] 1.1 Write the failing tests for the facts, the revision after a hit, the old record, the bound and the model change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py`
- [ ] 1.2 Add `PlanFacts` and `StagePlanRecord.facts`, write the facts with the plan, and join them in `_trace_facts`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py tests/roadmap/stage/test_roadmap_stage_plan_record.py tests/roadmap/stage/test_roadmap_stage_trace_runs.py`

## 2. Documents

- [ ] 2.1 Check that no document names the content of the plan file
  - Verification: `$ uv run devops ci docs`
