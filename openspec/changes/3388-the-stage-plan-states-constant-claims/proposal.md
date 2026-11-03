# Proposal

## Why

The plan check parses constant claims from prose, so a plan that states two numbers in one sentence or renames an existing bound passes with a wrong claim (#3388).

## What Changes

- Add `constant_claims`, a list of `StageConstantClaim` entries with a name and an integer value, to `StageProposal`
- Add the new module `src/devops_cli/roadmap/stage_constants.py` with `StageConstantClaim` and `staged_constants`, which reads the staged value of a claimed name with git grep, git show and ast
- Compare each claim with the staged value in `check_proposal`, and refuse a wrong value or a name the staged tree does not define
- Keep the prose scan of constant claims as the fallback for a reply whose claim list is empty
- List `constant_claims` among the reply keys of `src/devops_cli/ai/tasks/roadmap_stage_change.md` and ask for each constant the plan relies on
- Add the messages of a wrong claim and of an unknown claim name, and the tests of the reader, the check and the prompt key
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The plan states a constant claim as a name and a value, A claim name is an identifier, The prompt lists the claim key, The reader gives the staged value, A correct claim passes, A wrong claim is refused, A claim with no staged definition is refused, The prose scan stays as the fallback, The replay judges no claim

## Impact

- Code: `src/devops_cli/roadmap/stage_constants.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_constants.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probes confirm the premise: "The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit."
- The probes confirm the prompt: "The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit."
- The probes confirm that the new test module does not exist yet: "The path `tests/roadmap/test_roadmap_stage_constants.py` is no file of the staging commit. No commit in the history deleted or renamed it."
- The context of `src/devops_cli/roadmap/stage_change.py` shows the prose check today: `_TOKEN_COST` and `_TIME_COST` are read from `existing_tool`, and `_PLAN_KEYS` names the required keys.
- The context of `src/devops_cli/ai/tasks/roadmap_stage_change.md` shows the reply keys listed under `The reply has these keys and no other`, with no `constant_claims` among them.
- First check after the change: `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py`.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`.
- Third check: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py`.

## Existing Tool Considered

No open, maintained tool compares a plan constant with a staged Python constant. The change builds its own reader: 12k tokens to build, 3k tokens per month to keep and fix, and 16 hours of work. It deletes no internal code.
