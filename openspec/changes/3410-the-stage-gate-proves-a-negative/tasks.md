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

Reads: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`. Changes: `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`.

- [ ] 3.1 Write tests/roadmap/test_roadmap_stage_eval_gates.py first: the replay of a case with a negative-search verify command reads the recorded paths from the case, reports a problem when the record holds no path, and reports no problem when a recorded path survives the change
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 3.2 Read the search evidence of the case in src/devops_cli/roadmap/stage_eval_gates.py and pass it to check_proposal as the search record. The replay starts no git process and reaches no network
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## 4. Add the case of the plan of the moved modules

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_eval_gates.py`. Changes: `tests/roadmap/test_roadmap_stage_negative_search.py` (new).

- [ ] 4.1 Add tests/roadmap/test_roadmap_stage_negative_search.py, which holds the plan of #3378 as a proposal with the move group of the stage modules, and asserts the refusal of a literal with no recorded hit, the refusal of the whole module prefix of the moved modules, and the acceptance of the literal with the trailing underscore whose recorded hit survives the change
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_negative_search.py` passes

## 5. Ask the planner for the hit count

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 5.1 Add to src/devops_cli/ai/tasks/roadmap_stage_change.md the rule that the planner calls search_code with the literal of each negative-search verify command on the staged commit and quotes the hit count in feasibility, and that a literal which a created module keeps is no whole-prefix check. Assert the rule in tests/roadmap/test_roadmap_stage_prompt_rules.py
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
