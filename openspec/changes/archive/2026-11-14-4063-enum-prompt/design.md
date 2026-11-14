# Design

## Context

`tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` compares `GroupKind` and the prompt. A group that adds an enum value without the prompt text fails that test alone.

## Goals

- Keep an enum change and its prompt text in one group.
- Make the rule visible to the model.

## Decisions

- **One sentence before the group rules.** It names the co-location, the invariant test and the stop.
- **No validator.** The plan check cannot know which prompt text an enum value needs. The prompt guides the model, and the invariant test catches a split plan.

## Risks

- A plan that needs a prompt update but does not change an enum may put the two apart. The rule names the compared pair, which is the case that breaks a step.

## Tests

- The prompt holds the rule, and the test fails when it is removed.
