# Tasks

## 1. Map each criterion to a group and refuse an unmapped one

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_criteria.py` (new), `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_criteria.py` (new), `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 1.1 Tests in `tests/roadmap/test_roadmap_stage_criteria.py` and `tests/roadmap/test_roadmap_stage_plan.py` give an issue with three criteria and a reply that maps two, an issue with a refine block, an issue with no list, and a split; they assert the refusal that quotes the third criterion, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_criteria.py tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [x] 1.2 Add `StageCriterion`, `acceptance_criteria` and `criterion_problems` in `src/devops_cli/roadmap/stage_criteria.py`, the `criteria` lists of `StageProposal` and `StageSplit`, the keyword `issue_body` of `check_proposal`, the whole `item.body` in `src/devops_cli/roadmap/stage.py`, the criteria of the split request, and their messages, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_criteria.py tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. Render the Criteria section in tasks.md

Reads: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 2.1 A test in `tests/roadmap/test_roadmap_stage_plan.py` renders a change with a group number and a `pending-person` entry, and asserts that `tasks.md` holds a `## Criteria` section before `## Workflow follow-up`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [x] 2.2 Add `_criteria_section` and pass the criteria to `_tasks_file` in `src/devops_cli/roadmap/stage_change.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. State the criteria rule in the stage prompts

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 3.1 A test in `tests/roadmap/test_roadmap_stage_plan.py` asserts that both prompts name the `criteria` list, `pending-person` and the count from 1, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [x] 3.2 Add the `criteria` key to the reply of the change prompt and the split prompt, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 4. Add the criteria gate to the golden-set replay

Reads: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`. Changes: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`, `tests/roadmap/test_roadmap_stage_eval_command.py`, `tests/fixtures/roadmap_eval/stage/2147-the-volumes-of-grafana-the-prometheus/case.json`.

- [x] 4.1 Tests in `tests/roadmap/test_roadmap_stage_eval_gates.py` replay a plan with a `criteria` list that leaves one criterion out, a plan that maps all, and a recorded plan with no list, and assert the gate totals and the gate `none` of the dropped-criterion defects, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [x] 4.2 Add `GateName.CRITERIA`, the gate in `GATES`, the issue body in `PlanUnderTest`, remove `CRITERION_DROPPED` from `PENDING_GATES`, and set the gate `none` in the 11 case files with a dropped-criterion defect, and verify that `uv run devops roadmap eval stage --replay` exits 0

## 5. Document the criteria rule

Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/stage_criteria.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 5.1 State in the replay section that the reply maps each acceptance criterion to a group or to `pending-person`, what an acceptance criterion is, that `check_proposal` refuses an unmapped one, and that the `criteria` gate does not judge a recorded plan, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
