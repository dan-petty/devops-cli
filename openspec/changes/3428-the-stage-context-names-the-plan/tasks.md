# Tasks

## 1. Name the plan reader and gate in the stage context

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/plan_read.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [ ] 1.1 Add `test_the_request_context_names_the_plan_reader_and_the_gate` to `tests/roadmap/stage/test_roadmap_stage_plan.py`. It plans the sample item with the fake model client and asserts that `request["context"]` holds `plan_read.read_change`, `plan_read.tree_files`, `plan_read.files_at`, `plan_read.change_root`, `stage_change.check_proposal` and the path `src/devops_cli/roadmap/plan_read.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py` fails on the base
- [ ] 1.2 In `src/devops_cli/roadmap/stage/stage.py`, add a module constant after `_CHANGE_TASK` that holds the five lines of the section, each a name, a path and one line of purpose: `plan_read.read_change`, `plan_read.tree_files`, `plan_read.files_at` and `plan_read.change_root` with the path `src/devops_cli/roadmap/plan_read.py`, and `stage_change.check_proposal` with the path `src/devops_cli/roadmap/stage/stage_change.py`. Append a `### Plan reader and gate` section to the context in `_Planner._request`, after the `### Registry places` section, so every request holds it. The test of the group passes
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py` passes

## 2. Add the prompt rule that names the existing reader

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 2.1 Add one rule to the list of rules of `src/devops_cli/ai/tasks/roadmap_stage_change.md`, after the `existing_tool` rule: when the plan builds a reader that turns a change folder into a `StageProposal`, it names `plan_read.read_change` in `src/devops_cli/roadmap/plan_read.py` and `stage_change.check_proposal` in `src/devops_cli/roadmap/stage/stage_change.py`, and it cites them in `feasibility` instead of planning a second reader. Add `test_the_prompt_names_the_existing_plan_reader` to `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`; it loads the prompt and asserts that it holds `plan_read.read_change` and the instruction to cite it. Run `uv run devops roadmap eval stage --replay` and state the score of the same model before and after the change in the pull request body
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
