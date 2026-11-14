# Tasks

## 1. Refuse a new scenario that no behavior task covers

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_specs.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_recheck.py`. Changes: the same paths, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py`.

- [x] 1.1 Add the scenario names to `BaseSpec` and to the callers of the gates in the stage job, `plan-check` and `plan-recheck`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py` passes
- [x] 1.2 Refuse a scenario that names no code and no behavior group covers, with the scenario and its requirement in the problem, and exempt a base-spec scenario
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py` passes
- [x] 1.3 Keep the existing plan tests true, where the new rule refuses a plan that another rule already refuses
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/test_roadmap_plan_check.py tests/roadmap/test_roadmap_plan_recheck.py` passes

## 2. State the rule in the stage prompt

Kind: other. Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: the same paths.

- [x] 2.1 Add the sentence of the rule to the prompt, beside the rule of #3321
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## 3. Run the gates

Kind: other. Reads: `tests/roadmap/`. Changes: none.

- [x] 3.1 Run the gate of the branch
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes
  - Verification: `$ uv run devops ci docs` passes
