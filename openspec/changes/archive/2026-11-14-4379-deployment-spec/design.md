# Design

## Context

The template moved `analysis` and `stage` to DeepSeek on 2026-11-10, and the spec did not follow because the changing pull request skipped the specs.

## Goals

- State the values of the template.
- Keep the record of the Sonnet trial in the comment requirement.

## Decisions

- **One MODIFIED requirement.** The change replaces the requirement and its scenarios, so no other requirement changes.
- **The comment keeps Sonnet.** A scenario reads the `analysis` comment, which names the later trial.

## Risks

- A comment change that removes the trial text breaks the scenario. That change would name a new decision and update the requirement.

## Tests

- The existing runtime test pins the DeepSeek slots, the 256000 windows and the `stage` key.
- `uv run devops openspec check` passes.
