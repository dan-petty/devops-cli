# Tasks

## 1. Read the literal and the paths of a negative search

Reads: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/stage_form.py`, `tests/roadmap/test_roadmap_stage_form.py`. Changes: `src/devops_cli/roadmap/stage_form.py`, `tests/roadmap/test_roadmap_stage_form.py`.

- [ ] 1.1 Write tests/roadmap/test_roadmap_stage_form.py first: negative_search_parts gives the literal and the relative paths of a command that form_problems accepts, gives no literal for a command of another shape, record_search_evidence calls the search once for each literal, and search_problems refuses a literal with no hit, refuses a literal that a created source path keeps, and accepts a literal whose hit survives
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails on the base
- [ ] 1.2 Add to src/devops_cli/roadmap/stage_form.py the parser negative_search_parts, which reads the literal and the relative paths of a command from the option list that form_problems already uses, the function record_search_evidence, which runs the given search callable once for each literal of the negative-search verify commands of a group, and the function search_problems, which refuses a literal with no recorded hit and a literal that the import path of a created source path under src/devops_cli/ contains
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` passes

## 2. Pass the recorded evidence to the gate

Reads: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/plan_check.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 Write tests/roadmap/test_roadmap_stage_plan.py first: check_proposal refuses a negative-search literal with no recorded hit, refuses a literal that a created source path keeps, and accepts a literal whose recorded hit survives the change
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 Add the keyword search_evidence to check_proposal in src/devops_cli/roadmap/stage_change.py, with no record by default so plan_check keeps its behaviour, and call search_problems with the groups and the record. In src/devops_cli/roadmap/stage.py record the evidence in _Planner._settle from the search callable before check_proposal runs, and record it again for the groups that a split gives
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. Read the evidence from the eval case in the replay

Reads: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`. Changes: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`.

- [ ] 3.1 Write the tests first: tests/roadmap/test_roadmap_stage_eval_cases.py reads a case whose facts.json holds a search_evidence mapping and asserts that CaseFacts holds it and gives an empty mapping by default, and tests/roadmap/test_roadmap_stage_eval_gates.py replays a case with a negative-search verify command, reads the recorded paths from the case, reports a problem when the record holds no path, and reports no problem when a recorded path survives the change
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_cases.py tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 3.2 Add the search_evidence mapping to CaseFacts in src/devops_cli/roadmap/stage_eval_cases.py, with an empty mapping by default so the recorded cases keep their shape. Read the mapping in PlanUnderTest.of_case and pass it to check_proposal as the search record in the paths gate of src/devops_cli/roadmap/stage_eval_gates.py. The replay starts no git process and reaches no network
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_cases.py tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## 4. Add the case of a move of the stage modules

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_move_prefix.py`. Changes: `tests/fixtures/roadmap_eval/stage/3372-the-stage-plan-of-a-module/case.json` (new), `tests/fixtures/roadmap_eval/stage/3372-the-stage-plan-of-a-module/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3372-the-stage-plan-of-a-module/plan.json` (new), `tests/fixtures/roadmap_eval/stage/3372-the-stage-plan-of-a-module/facts.json` (new), `tests/roadmap/test_roadmap_stage_negative_search.py` (new).

- [ ] 4.1 Add the golden-set case of a move of the stage modules: plan.json holds the move group of the stage modules with a literal with no hit, the bare prefix `devops_cli.roadmap.stage` and the dotted prefix `devops_cli.roadmap.stage_`, and facts.json holds the recorded search evidence for each literal. Add tests/roadmap/test_roadmap_stage_negative_search.py, which loads the case through tests/fixtures/roadmap_eval/stage/, replays it with replay_case, and asserts the refusal of the literal with no recorded hit, the refusal of the bare prefix whose created `stage/` package keeps it, and the acceptance of the dotted prefix whose recorded hit survives the change
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_negative_search.py tests/roadmap/test_roadmap_stage_eval_cases.py` passes

## 5. Ask the planner for the hit count

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 5.1 Add to src/devops_cli/ai/tasks/roadmap_stage_change.md the rule that the planner calls search_code with the literal of each negative-search verify command on the staged commit and quotes the hit count in feasibility, and that a literal which a created module keeps is no whole-prefix check. Assert the rule in tests/roadmap/test_roadmap_stage_prompt_rules.py
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
