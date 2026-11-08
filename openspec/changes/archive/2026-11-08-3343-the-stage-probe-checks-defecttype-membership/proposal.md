# Proposal

## Why

The stage gates never read a finding-type reference in a plan. The model schema refuses a bad finding type only at validation. An earlier plan added a scan of the plan prose, but that scan refuses the sound plan of #3328 and finds no true hit in the 695 recorded plans. This change keeps the incident plan of pull request #3305 in the golden set and proves that the gates accept a plan that names a `DefectType` member (#3343). No new gate is built.

## What Changes

- Add the incident plan of pull request #3305 to `tests/fixtures/roadmap_eval/stage/good-3264-the-stage-marks-a-plan-ready/` as a good case.
- Record the `kind: placeholder` claim of the authoring run in one note of `case.json`.
- Add `test_the_incident_case_of_pull_3305_is_loaded_and_accepted` to `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` and update `test_each_good_plan_passes_every_gate` to five good plans.
- Update `test_the_set_holds_the_45_plans_and_four_good_ones` and `test_a_good_case_is_the_twin_of_a_reviewed_case_and_has_no_defect` in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`.
- Add `test_a_plan_that_names_a_defect_type_member_passes` to `tests/roadmap/stage/test_roadmap_stage_plan.py`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage-eval`: The golden set holds the incident plan
- `roadmap-stage`: A plan that names a defect type member passes

## Impact

- Code: none.
- Fixtures: `tests/fixtures/roadmap_eval/stage/good-3264-the-stage-marks-a-plan-ready/`
- Tests: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`

## Feasibility

- The path `tests/fixtures/roadmap_eval/stage/` holds the golden set cases.
- Pull request #3305 is merged at commit `7229a7d37162c5b5b8389218f4cefcded5ed3a2a` with base `ce4e32741aec507c2a76decdd7fa57bf7e280748`.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` confirms `replay_all` and the four replay gates.
- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_cases.py` confirms `DefectType` and `StageCase`.
- `uv run devops roadmap eval stage --replay` passes with 50 cases and 5 good plans.

## Existing Tool Considered

Pydantic covers the runtime enum check of `Finding.type` in `src/devops_cli/roadmap/stage_verify.py`. The change builds no check: it records the incident plan in the golden set, which the existing replay `uv run devops roadmap eval stage --replay` reads. The work costs about 2,000 tokens to write the case and the tests, and about 1 hour elapsed.
