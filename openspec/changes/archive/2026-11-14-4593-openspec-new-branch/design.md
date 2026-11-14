# Design

## Context

`scaffold_change` computes `branch_name(issue, type, slug)` from the title and returns it. `new_cmd` prints it. `current_branch` returns an empty string on a detached HEAD, and `parse_branch` reads `<type>/<issue>-<slug>`.

## Goals

- The output names the branch that holds the folder.
- The folder and the worktree branch share one slug.

## Decisions

- **Read the branch once.** `_checked_out_branch` catches a git error and returns None, so a checkout without a repository still scaffolds.
- **The branch slug wins for the same issue.** `_slug_for_issue` reads the slug from the branch of the checkout, and the title supplies it otherwise.
- **A computed name off the checkout is a suggestion.** One message states it.

## Risks

- A worktree branch that names the issue but a different slug renames the folder from the title. The folder and the branch then agree, which is the rule of CONTRIBUTING.md.

## Tests

- The output and the folder take the branch slug.
- A branch of another issue gives the suggestion.
- A detached HEAD names no branch.
- The dry run matches a real run.
