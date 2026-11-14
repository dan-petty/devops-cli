# Design

## Context

The deleted test parsed the imports by hand. mypy now checks the `src/` imports, and pytest imports every test module that it collects.

## Goals

- Name only checks that run in the gate.
- Keep the requirement, because the move of #3187 is complete and the contract still holds for the code that runs.

## Decisions

- **The modified form.** The requirement keeps its name and its meaning, and its scenario names mypy and the pytest run.
- **The TYPE_CHECKING exclusion.** mypy reads `src/` only, so a test import in such a block is no check.

## Risks

- A new `tests/` import in a `TYPE_CHECKING` block that names no module goes unchecked. The block does not run, and the item records that.

## Tests

- `uv run devops openspec check` passes.
- The requirement names no deleted test.
