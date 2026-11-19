# Design

## Decisions
- State the rule where the prompts define the `behavior` kind, in the same words as the validator message, and name the result (`other`) so the planner has a choice that passes.

## Rejected alternatives
- Let the validator turn a prompt-only `behavior` group into `other`: it would hide a wrong plan and keep a test that reads a value.
