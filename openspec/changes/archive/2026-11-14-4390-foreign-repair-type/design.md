# Design

## Context

`_extra_turn` returns `_Failure(foreign)` when `_foreign_change` names a path. `_failure_of` then classifies an untyped stop from the text and the check name.

## Goals

- One class for one cause.
- The wait action, because a retry gives the same stop.

## Decisions

- **Pass the class at the stop site.** The cause is a path outside the plan, which is what `outside_plan` names.
- **Keep the text.** The comment keeps the paths for a person.

## Risks

- A foreign path that another class describes better takes `outside_plan`. The stop is about a change outside the plan, which is the cause.

## Tests

- The repair-turn test asserts `FailureClass.OUTSIDE_PLAN`, also when the path holds a classifier word.
