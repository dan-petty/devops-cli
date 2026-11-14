# Design

## Context

`stop()` builds the stop text and sends it to the issue. `_comment` builds the table and the amendment and scoped-check lines for the pull request, and it posts or updates one comment keyed by the marker and the run id.

## Goals

- Put the stop text on the pull request at every stop that has one.
- Keep one comment for the run.

## Decisions

- **One renderer.** `_comment` takes an `extra` text, and the stop text goes there, above the table. The stop text loses its own marker line, and `_comment` adds the marker and the run id.
- **The pull request is read after the push.** A stop that publishes a Planned item's draft sets `self.pull`, so the comment reaches the new draft.
- **A stop with no pull request writes none.** The issue comment still goes out.

## Risks

- A pull request that GitHub cannot comment on stops the run with a GitHub error. The session already raises for a comment on a pull request that is gone.

## Tests

- A stop at a task group posts one comment to the pull request, and its body holds the stopped step and the failure class.
- The issue still gets its one comment.
- The existing stop tests pass.
