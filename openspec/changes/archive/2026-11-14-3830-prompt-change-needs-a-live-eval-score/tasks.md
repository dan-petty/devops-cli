# Tasks

## 1. The eval rule names the measure of each path

- [x] 1.1 Split the trigger paths and add the live command check in `eval_replay_problems`.
  Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gates.py`
- [x] 1.2 Add the messages `stage_problem_eval_live` and `stage_problem_eval_live_score`.
  Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gates.py -k live`

## 2. The prompt and the documents state the rule

- [x] 2.1 State the live command and the replay command in the stage prompt.
  Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
- [x] 2.2 State the rule in `docs/ROADMAP_WORKFLOW.md` and the command forms in `docs/TESTING.md`.
  Verification: `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
- [x] 2.3 Run the quality gate and the stage test tree.
  Verification: `uv run devops ci --check --only lint,format,typecheck && uv run devops ci test tests/roadmap/stage tests/invariants/test_roadmap_workflow_doc.py`
