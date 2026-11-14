# Design

## Context

#4275 added the requirement and the template together, and the two never agreed. The owner wants no new deny lists.

## Goals

- State the template.
- Keep the scenarios.

## Decisions

- **One MODIFIED requirement.** It names the allowlist, the two deny rules and the environment keys that the template holds.
- **The trial variable stays out.** `PYDANTIC_AI_NO_BANNER` is not in the scaffold.

## Risks

- A template change that adds a deny rule or a variable must update this requirement. The drift of #4478 is the reason.

## Tests

- `uv run devops openspec check` passes.
- The scaffold test already checks the file that the template writes.
