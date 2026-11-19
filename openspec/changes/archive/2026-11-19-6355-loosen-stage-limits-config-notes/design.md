# Design

## Decisions
- `gate_returns` 8, not 12. 8 is the next step of the owner rule for a job under 80%. The settings allow 12, so a later step stays possible.
- `backlog_interval_minutes` 4. Each poll of 5 minutes then finds the stage row due. With `jobs` 1, a round that finds no free slot starts no Job, so the cost of a round with no slot is its GitHub reads.
- `ai.tasks.fix_checks` names its model, as each other task of the template does. The model is the same as the code default (`ai.model`).
- The comments keep each number with its date, so a reader can check it again.

## Rejected alternatives
- Remove keys that equal the code default: no gain in behavior, and a later lower code default could then tighten a stage limit with no template change.
- `ai.decision_model` as `openrouter/typesafe/jev-1.14`: the validator refuses it, so the Service would not start. The gateway sends the Jev name unchanged to OpenRouter.
- A second stage Job (`jobs` 2): it waits for the shared GitHub budget (#4563) and an instance id per stage Job.
