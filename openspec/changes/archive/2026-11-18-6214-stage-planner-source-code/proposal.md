# Proposal: #6214

## Why
#6207 made a `behavior` stage group change source code: a `.py` file under `src/` outside the knowledge base. The validator refuses a `behavior` group that changes only a prompt or other data under `src/`, but the stage prompts still said that a `behavior` group "changes a path under `src/`". In the 24 hours to 2026-11-18, 2 of 20 graded stage runs (#4075, #4113) failed on that refusal after 3 returns to the model, because the planner kept planning a prompt change as `behavior`. Closes #6214.

## What Changes
- `roadmap_stage_change.md` and `roadmap_stage_split.md` say that a `behavior` group changes a Python file under `src/`, that a prompt, a pin, a template or other data under `src/` is no code, and that a group that changes only such files is `other`.
- The prompt-rule test reads the new sentence.

## Capabilities
- None: the validator rule and its spec came with #6207; the prompts now state it.

## Impact
- The planner plans a prompt-only group as `other`, so the kind rule does not return the plan.
- The live stage eval score at the base and the head is in the pull request body.

## Feasibility
- Loki, 2026-11-18: `StructuredOutputValidationError` on #4075 (0.175.0) and #4113 (0.176.0) names the group and the kind rule of #6207.

## Existing Tool Considered
- No tool applies: the change is the text of two prompts of this project.
