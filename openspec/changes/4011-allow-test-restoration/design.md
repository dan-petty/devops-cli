# Design

## Context

`_foreign_change` stages the checkout and lists the paths that differ from `tree`. It keeps the paths outside `ask.may_change` and `tasks.md`. `tree` is the state at the start of the extra turn, and `keeper.base` is the last commit before the step.

## Goals

- Allow a restoration of the step's own work.
- Stop on a new edit or on a deletion of a base file.

## Decisions

- **One git question for each path.** `git diff --cached --quiet <base> -- <path>` exits 0 when the staged content equals the base content. The comparison covers an edit, a deletion and a mode change.
- **The base of the step.** `keeper.base` is the commit whose content the step started from. A path that matches it is no foreign change.

## Risks

- A path that existed at base and the step deleted is restored by the turn: the staged content differs from `tree`, matches `base`, and the turn may change it. The restoration returns the tree to a state the step did not intend, and the exit checks judge the result.

## Tests

- A direct check of `_foreign_change` with a file restored to its base content gives None.
- The existing foreign edit test still stops the step.
