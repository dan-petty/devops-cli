# Tasks

## 1. Add the constant-claim field to the stage reply and the prompt

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_constants.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_constants.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 1.1 Write `test_the_stage_reply_holds_constant_claims` for `StageConstantClaim` and `constant_claims` in `tests/roadmap/stage/test_roadmap_stage_constants.py`; it fails on the base, where `StageProposal` ends its fields at `src/devops_cli/roadmap/stage/stage_change.py:699:security: Line = ""` and holds no `constant_claims`. Add `test_the_plan_check_accepts_the_plan_of_this_change`, which builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it. Add `StageConstantClaim` to the models of `test_each_list_of_keys_of_the_reply_is_the_fields_of_a_model` in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` for the key bullet of `src/devops_cli/ai/tasks/roadmap_stage_change.md`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_constants.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 1.2 Add `StageConstantClaim` with `name` and `value`, and the `constant_claims` list with an empty default, to `StageProposal` in `src/devops_cli/roadmap/stage/stage_change.py`, and refuse a `name` that is not a Python identifier. Add the `constant_claims` bullet with its key list to the reply keys of `src/devops_cli/ai/tasks/roadmap_stage_change.md`, with the rule that a claim names a constant of the staged tree and that a constant the plan creates is no claim. Run `uv run devops roadmap eval stage --replay` and record the score before and after the prompt change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_constants.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 1.3 Edit `src/devops_cli/ai/tasks/roadmap_stage_change.md`
  - Verification: `$ uv run devops ci docs` passes

## 2. Judge each structured claim in the plan check

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [ ] 2.1 Write `test_check_proposal_refuses_a_wrong_constant_claim`, `test_check_proposal_refuses_a_claim_the_tree_does_not_define`, `test_check_proposal_runs_the_prose_scan_only_with_no_claim_list` and `test_check_proposal_judges_no_claim_without_staged_values` in `tests/roadmap/stage/test_roadmap_stage_plan.py`. They fail on the base, where `check_proposal` judges only the prose of `src/devops_cli/roadmap/stage/stage_change.py:2440:ProposalGate.CONSTANTS: constant_problems(plan_texts(proposal), constants or {}),`. Keep `test_the_plan_check_accepts_the_plan_of_this_change` passing: it builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py tests/roadmap/stage/test_roadmap_stage_constants.py` fails on the base
- [ ] 2.2 Add `claim_problems` to `src/devops_cli/roadmap/stage/stage_change.py`: with no `constants` it judges no claim; otherwise it refuses a claim whose value differs with `stage_problem_constant_mismatch`, and a claim whose name the mapping lacks with the new `stage_problem_constant_undefined`. Run the prose scan only when `constant_claims` is empty. Add `stage_problem_constant_undefined` to `src/devops_cli/lang/en/messages.py`. Run `uv run devops roadmap eval stage --replay` and record the score before and after the gate change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py tests/roadmap/stage/test_roadmap_stage_constants.py` passes

## 3. Read the staged value of each claimed name

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_constants.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`. Changes: `src/devops_cli/roadmap/stage/stage_constants.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_constants.py`.

- [ ] 3.1 Write `test_claimed_names_adds_the_names_of_the_claims` for `claimed_names` in `tests/roadmap/stage/test_roadmap_stage_constants.py`; it fails on the base, where `src/devops_cli/roadmap/stage/stage_constants.py:287:__all__ = [` lists no `claimed_names`. Keep the stage job cases of `tests/roadmap/stage/test_roadmap_stage_apply.py` passing
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_constants.py tests/roadmap/stage/test_roadmap_stage_apply.py` fails on the base
- [ ] 3.2 Add `claimed_names(texts, claimed)` to `src/devops_cli/roadmap/stage/stage_constants.py`: the names that `candidate_names` finds in `texts`, with each claimed name. Call it at `src/devops_cli/roadmap/stage/stage.py:2230:constants = staged_constants(self._source, self._sha, candidate_names(plan_texts(proposal)))`, so the reader sees each claimed name
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_constants.py tests/roadmap/stage/test_roadmap_stage_apply.py` passes

## 4. Describe the claim list in the stage guide

Kind: other. Reads: `docs/roadmap/stage.md`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`. Changes: `docs/roadmap/stage.md`.

- [ ] 4.1 Describe the `constant_claims` key of the stage reply in `docs/roadmap/stage.md`: one entry for each constant that the plan relies on, with its staged value, the refusal of a claim that differs from the staged value, and the refusal of a claim that names no module-level integer of the staged tree
  - Verification: `$ uv run devops ci docs` passes
- [ ] 4.2 Edit `docs/roadmap/stage.md`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
