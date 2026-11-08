# Tasks

## 1. Record the incident case and verify replay

Reads: `tests/fixtures/roadmap_eval/stage`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`. Changes: `tests/fixtures/roadmap_eval/stage/good-3264-the-stage-marks-a-plan-ready/case.json` (new), `tests/fixtures/roadmap_eval/stage/good-3264-the-stage-marks-a-plan-ready/facts.json` (new), `tests/fixtures/roadmap_eval/stage/good-3264-the-stage-marks-a-plan-ready/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/good-3264-the-stage-marks-a-plan-ready/plan.json` (new), `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [x] 1.1 In `tests/fixtures/roadmap_eval/stage/good-3264-the-stage-marks-a-plan-ready/`, write `case.json`, `facts.json`, `issue.txt`, and `plan.json` for pull request #3305 with the `kind: placeholder` claim recorded in one note
  - Verification: `$ uv run devops roadmap eval stage --replay` passes
- [x] 1.2 In `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, add `test_the_incident_case_of_pull_3305_is_loaded_and_accepted` and update `test_each_good_plan_passes_every_gate` to assert five good plans
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes
- [x] 1.3 In `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, update `test_the_set_holds_the_45_plans_and_four_good_ones` to five good plans and update `test_a_good_case_is_the_twin_of_a_reviewed_case_and_has_no_defect`
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_eval_cases.py` passes
- [x] 1.4 In `tests/roadmap/stage/test_roadmap_stage_plan.py`, add `test_a_plan_that_names_a_defect_type_member_passes`
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_plan.py -k test_a_plan_that_names_a_defect_type_member_passes` passes

## Criteria

- Group 1: The golden set SHALL hold the plan of pull request #3305 as a case whose issue is 3264.
- Group 1: The case of pull request #3305 SHALL name the kind: placeholder claim of its authoring run in one note.
- Group 1: The replay SHALL accept the case of pull request #3305, so a gate that refuses the plan fails the replay.
- Group 1: check_proposal MUST NOT return a problem for a plan that names a DefectType member, including a member that the plan adds.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
