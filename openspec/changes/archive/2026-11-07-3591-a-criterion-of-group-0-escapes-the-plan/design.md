# Design

## Overview

`_criteria` catches the `ValidationError` of `StageCriterion` and raises `PlanReadError` for `tasks.md`. The reason names the criterion line and the problem. `read_change`, `plan-check` and `plan-recheck` are not changed: they already handle `PlanReadError`.

## Decisions

- **Convert in `_criteria`**: the conversion stays next to the constructor that raises, as `_read_group` does for a task group.
- **Reuse `_reasons`**: it renders each pydantic error on one line, with no input value and no link.

## Rejected Alternatives

- **Wrap the `_criteria` call in `read_change`**: `_criteria` could still raise a pydantic error for another caller, and the line of the criterion would be lost.
- **Relax `StageCriterion` to accept `Group 0`**: a criterion would point at no task group, and a malformed plan would pass the reader.
- **`str(exc)` as the reason**: it spans several lines and holds the input value and a documentation link.
