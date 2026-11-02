# Tasks

## 1. Add the criteria list and the refusal to the stage reply

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 1.1 A test in `tests/roadmap/test_roadmap_stage_plan.py` gives an issue body with three acceptance criteria and a reply that maps two, and asserts that `check_proposal` returns a problem that names the third, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 1.2 Add `StageCriterion` with `criterion`, `group` (an integer or `pending-person`) and `reason`, and a `criteria` list on `StageProposal`. Add `criterion_problems(criteria, issue_body)` that collects the acceptance bullets of the issue and reports each text that no entry maps. Give `check_proposal` the issue body as an argument and call the function from it, and pass the body of the item from `stage.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. Render the Criteria section in tasks.md

Reads: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 A test in `tests/roadmap/test_roadmap_stage_plan.py` renders a change with two mapped criteria and asserts that `tasks.md` holds a Criteria section with each criterion text and its group number or `pending-person` with the reason, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 Add a `_criteria_section` that lists each criterion on one line with its group number or `pending-person` and reason, and append it to `_tasks_file` after the groups, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. State the criteria rule in the stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`.

- [ ] 3.1 Add a line to the prompt that the reply holds a `criteria` list, that every acceptance criterion of the issue appears in it, and that an entry gives a group number or `pending-person` with a reason, and verify that `uv run devops ci docs` passes

## 4. Add the criteria gate to the golden-set replay

Reads: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`. Changes: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`.

- [ ] 4.1 A test in `tests/roadmap/test_roadmap_stage_eval_gates.py` replays a case whose recorded plan drops a criterion and asserts that the `criteria` gate catches it, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 4.2 Add the `criteria` gate that runs `criterion_problems` on the recorded plan and the issue body of the case, and mark the known dropped-criterion defects of the cases with that gate, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## 5. Document the criteria rule

Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/stage_change.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 5.1 State in the Plan step and the stage-eval section that the reply maps each acceptance criterion to a group or to `pending-person`, that `check_proposal` refuses an unmapped criterion, and that the `criteria` gate is part of the replay, and verify that `uv run devops ci docs` passes
- [ ] 5.2 docs/ROADMAP_WORKFLOW.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
