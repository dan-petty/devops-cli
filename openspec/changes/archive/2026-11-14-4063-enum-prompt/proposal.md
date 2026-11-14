# Proposal

## Why

The stage planner can put a schema enum or constant change in one group and the prompt update it requires in a later group. An invariant test compares the two, so the first group fails its own check and the implement step stops (#4063).

## What Changes

- `src/devops_cli/ai/tasks/roadmap_stage_change.md` tells the model to put a prompt or document update in the same group as the schema enum or constant change that the update describes.
- A prompt-rule test holds the rule.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Prompt: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The prompt already owns the group formation rules.
- The invariant test of the prompt already exists.
- Verification commands: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

No tool covers a grouping rule for a prompt. The change adds one sentence and one test.
