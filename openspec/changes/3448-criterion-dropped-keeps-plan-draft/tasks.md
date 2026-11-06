# Tasks

## 1. Keep a quoted dropped criterion in draft

Reads: `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/roadmap/refine_judge.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `docs/roadmap/stage.md`, `tests/roadmap/test_roadmap_stage_verify.py`, `tests/roadmap/test_roadmap_refine_trust.py`. Changes: `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/roadmap/refine_judge.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `docs/roadmap/stage.md`, `tests/roadmap/test_roadmap_stage_verify.py`, `tests/roadmap/test_roadmap_refine_trust.py`.

- [x] 1.1 Write tests/roadmap/test_roadmap_stage_verify.py first: OPEN_TYPES holds criterion_dropped, a criterion_dropped finding of a test-only group whose quote is in the issue is open, one whose quote is not in the input is advice, none of them returns the plan, and the prompt line of criterion_dropped names the group that changes only test files and the earlier group that changes the code. Write tests/roadmap/test_roadmap_refine_trust.py first for the review of refine: a criterion_dropped finding that quotes the input is advice and the item is Ready
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py tests/roadmap/test_roadmap_refine_trust.py` fails on the base
- [x] 1.2 Add criterion_dropped to OPEN_TYPES in src/devops_cli/roadmap/stage_verify.py, define the criterion whose group changes only test files while no group changes the code that it needs in src/devops_cli/ai/tasks/roadmap_stage_verify.md, and say there that a test-only group which tests code of an earlier group is no criterion_dropped. Remove criterion_dropped from JUDGE_OPEN_TYPES in src/devops_cli/roadmap/refine_judge.py
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py tests/roadmap/test_roadmap_refine_trust.py` passes
- [x] 1.3 Edit docs/roadmap/stage.md and the module text of src/devops_cli/roadmap/stage.py to list criterion_dropped as an open finding type
  - Verification: `uv run devops ci docs` passes

## 2. Add the pair of cases to the golden set

Reads: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_cases.py`. Changes: `tests/fixtures/roadmap_eval/stage/3410-the-eval-field-group-is-dropped/case.json` (new), `tests/fixtures/roadmap_eval/stage/3410-the-eval-field-group-is-dropped/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3410-the-eval-field-group-is-dropped/plan.json` (new), `tests/fixtures/roadmap_eval/stage/3410-the-eval-field-group-is-dropped/facts.json` (new), `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/case.json` (new), `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/plan.json` (new), `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/facts.json` (new), `tests/roadmap/test_roadmap_stage_criterion_dropped.py` (new), `tests/roadmap/test_roadmap_stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_command.py`.

- [x] 2.1 Add the reviewed case 3410-the-eval-field-group-is-dropped, which holds the merged plan of #3410 without the group that adds the search_evidence field and one criterion_dropped defect with the gate none, and the good case good-3410-the-stage-gate-proves-a-negative, which holds the merged plan and is the twin of the reviewed case. Add tests/roadmap/test_roadmap_stage_criterion_dropped.py, which replays both cases, asserts that no gate refuses either plan, asserts that the last group of each plan changes only test files, and asserts that the plans differ by the group that changes stage_eval_cases.py. Update the counts of the set in the three test files that hold them
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_criterion_dropped.py tests/roadmap/test_roadmap_stage_eval_cases.py tests/roadmap/test_roadmap_stage_eval_gates.py tests/roadmap/test_roadmap_stage_eval_command.py` passes

## 3. Remove the count of the good plans from the workflow document

Reads: `docs/ROADMAP_WORKFLOW.md`, `tests/invariants/test_roadmap_stage_measure_doc.py`. Changes: `docs/ROADMAP_WORKFLOW.md`, `tests/invariants/test_roadmap_stage_measure_doc.py`.

- [x] 3.1 Edit docs/ROADMAP_WORKFLOW.md to name the good plans of the golden set with no count, and read the words and not the number in tests/invariants/test_roadmap_stage_measure_doc.py
  - Verification: `uv run devops ci test tests/invariants/test_roadmap_stage_measure_doc.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
