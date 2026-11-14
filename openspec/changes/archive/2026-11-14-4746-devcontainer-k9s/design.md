# Design

## Context

The image build holds every locked tool. The sentence predates #4366.

## Goals

- State where the tools come from.

## Decisions

- **The image, not post-create.** The bullet names `/usr/local/bin` and the locked versions, as the bullet above does.

## Risks

- A later change that moves a tool updates the bullet. The spec `devcontainer-image-tools` states the rule.

## Tests

- `uv run devops ci docs` finds no stale text.
