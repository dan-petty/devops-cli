# Tasks

## 1. The live run reads the runner facts in the checkout

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_eval_run.py`, `src/devops_cli/roadmap/stage/stage_context_facts.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_eval_run.py`, `tests/roadmap/stage/test_roadmap_stage_eval_facts_context.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_eval_facts_context.py`, assert that a case whose commit lacks `failure.py`, `runner_tools.py` or both reaches the model, that a file which the checkout lacks too ends the case `refused` with its path, that the job still raises `RoadmapStageError` when a fact file is absent at the staged commit, and that one golden case of each missing shape reaches the model. Verify that the test fails on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_facts_context.py` fails on the base
- [x] 1.2 Add `facts_source` to `plan_item`, `_planner_of` and `_Planner`, and make `_request` read the facts files from the staged commit and then from `facts_source` at `HEAD`. Pass the repository as `facts_source` in `run_case`. The job passes none
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_facts_context.py` passes
- [x] 1.3 Run the other tests of the stage package
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_run.py` passes

## 2. Documents

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 State in `docs/ROADMAP_WORKFLOW.md` that the live run of the golden set reads the runner facts at the case commit and then in the checkout of the run, and that the job reads the staged commit only
  - Verification: `$ uv run devops ci docs`
- [x] 2.2 Check the change folder
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
