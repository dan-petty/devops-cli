# Tasks

## 1. Refuse a plan that deletes a guard check

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_weakened_checks.py` (new), `tests/roadmap/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/test_roadmap_plan_read_weakened.py`.

- [ ] 1.1 Write `tests/roadmap/test_roadmap_stage_weakened_checks.py` with a reply whose task deletes `test_all_cli_commands_are_either_exposed_or_excluded` and no entry, and assert that `check_proposal` names it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_weakened_checks.py` fails on the base
- [ ] 1.2 Add `_guard_deletions` and the check that calls it from `check_proposal`, with the texts in `MESSAGES.roadmap`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_weakened_checks.py` passes
- [ ] 1.3 Remove `SkipJsonSchema` from the field `weakened_checks` of `StageProposal`, so the reply schema shows it, and delete `test_the_reply_schema_of_the_stage_model_does_not_show_the_field` from `tests/roadmap/test_roadmap_plan_read_weakened.py`. Add the `weakened_checks` key and its rule to `src/devops_cli/ai/tasks/roadmap_stage_change.md`, and add `WeakenedCheck` to the models of `tests/roadmap/test_roadmap_stage_prompt_rules.py` that must list their keys
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## 2. Write the weakened checks into the proposal file

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_weakened_checks.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_weakened_checks.py`.

- [ ] 2.1 Add a case to `tests/roadmap/test_roadmap_stage_weakened_checks.py` that renders one entry, asserts the `## Weakened checks` section and reads the entry back with `read_change`, and one that renders none and asserts no section
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_weakened_checks.py` fails on the base
- [ ] 2.2 Render the section in `_proposal_file` between `## Impact` and `## Feasibility` when `weakened_checks` is not empty, with `stage_weakened_checks_title` and `stage_weakened_entry` of `MESSAGES.roadmap`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_weakened_checks.py` passes

## 3. Ask for the section in the proposal rules

Reads: `openspec/config.yaml`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `openspec/config.yaml`.

- [ ] 3.1 Add one rule to `rules.proposal` that asks a plan which deletes a guard check to give a `## Weakened checks` entry with the check, what it stopped and the safeguard
  - Verification: `$ uv run devops openspec check` passes

## 4. Replay a plan that deletes a guard check

Reads: `src/devops_cli/roadmap/stage_eval_cases.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/roadmap/stage_eval_cases.py`.

- [ ] 4.1 Add the case of a plan that deletes `test_all_cli_commands_are_either_exposed_or_excluded` and records no weakened check, with its defect of the new gate
  - Verification: `$ uv run devops roadmap eval stage --dry-run` passes

## 5. State the score of the stage gate

Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/stage_eval_run.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 5.1 Update `docs/ROADMAP_WORKFLOW.md` with the weakened-check gate, the new replay case and the model score before and after the change, then run `uv run devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: ### Requirement: A deleted guard check needs an entry `check_proposal` SHALL refuse a plan whose work texts delete a test or a `CONST_*` entry when no `weakened_checks` entry names it.
- Group 1: ### Requirement: An entry that names the check satisfies the rule `check_proposal` MUST accept a plan whose `weakened_checks` entry names each guard check that the plan deletes.
- Group 2: ### Requirement: The proposal file shows each weakened check `render_change` SHALL write a `## Weakened checks` section that gives the check, what it stopped and the safeguard of each entry.
- Group 2: ### Requirement: A plan that weakens no check keeps its proposal file `check_proposal` MUST report no weakened-check problem for a plan that deletes no guard check, and `render_change` MUST write no `## Weakened checks` section for it.
- Group 3: ### Requirement: The proposal rules ask for the weakened check The `proposal` rules in `openspec/config.yaml` SHALL ask a plan that deletes a guard check to give the `## Weakened checks` entry.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
