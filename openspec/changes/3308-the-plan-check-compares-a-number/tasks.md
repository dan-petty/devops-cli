# Tasks

## 1. Read the staged integer constants and pair them with a plan number

Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage_constants.py` (new), `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_constants.py` (new).

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_constants.py`, assert that a staged module with `SUMMARY_MAX_CHARS: Final[int] = 60` gives 60, that an alias resolves to its integer, that a value from a call is left out, and that a plan text with `SUMMARY_MAX_CHARS` and 40 in one sentence yields one problem that names the constant, 40 and 60, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/stage_constants.py` with a function that walks the staged Python files under `src/` with `ast.parse` and returns the module-level integer constants by name, an alias to another integer constant resolved, and no value for an assignment that is no integer literal. Add a function that splits a plan text into sentences, finds each known constant name beside a decimal integer, and returns one message for each pair whose number differs, naming the constant, the plan's number and the staged value. Add the message to `src/devops_cli/lang/en/messages.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py` passes

## 2. Refuse the plan in `check_proposal`

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_constants.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_plan.py`, assert that `check_proposal` over a staged tree that sets `SUMMARY_MAX_CHARS = 60` returns one problem for a proposal whose spec scenario says 40, returns none for one that says 60, and returns none for the text of a task group that holds 40, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 Call the new check from `check_proposal` in `src/devops_cli/roadmap/stage_change.py` over the texts of the reply that render to `proposal.md`, `design.md` and each spec delta, and never over the text of a group, and add its problems to the list that `check_proposal` returns. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. Ask the plan stage prompt for the staged value of a constant

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add one rule to `src/devops_cli/ai/tasks/roadmap_stage_change.md`: cite the staged value of each constant that the plan relies on, with the constant name and its value, as `feasibility` quotes the probe lines. Add the assertion of that rule to `tests/roadmap/test_roadmap_stage_prompt_rules.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## 4. Check the OpenSpec change against the base specs

Reads: `openspec/config.yaml`. Changes: `openspec/changes/3308-plan-check-constant-value/proposal.md` (new), `openspec/changes/3308-plan-check-constant-value/design.md` (new), `openspec/changes/3308-plan-check-constant-value/tasks.md` (new), `openspec/changes/3308-plan-check-constant-value/.openspec.yaml` (new), `openspec/changes/3308-plan-check-constant-value/specs/roadmap-stage/spec.md` (new).

- [ ] 4.1 Write the change folder `openspec/changes/3308-plan-check-constant-value/` with its proposal, its design, its `tasks.md` and the spec delta of `roadmap-stage`, then run the validation
  - Verification: `uv run devops openspec check` passes
- [ ] 4.2 The change folder is the record of the item, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 2: The plan check SHALL refuse a plan when a number beside a known integer constant in a requirement, a scenario or a decision differs from the staged value.
- Group 2: The plan check SHALL accept a plan when the number beside a known integer constant equals the staged value of that constant.
- Group 1: The plan check MUST ignore a constant name that the staged tree does not define as a module-level integer constant.
- Group 2: The plan check MUST NOT compare a number in `tasks.md` with a constant.
- Group 3: The plan stage prompt SHALL tell the model to cite the staged value of each constant that the plan relies on.
- Group 1: The plan check MUST read constant values with Python AST and MUST NOT import or execute staged code.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
