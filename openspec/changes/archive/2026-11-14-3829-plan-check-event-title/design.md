# Design

## Context

The `plan-check` job starts from `startsWith(github.event.pull_request.title, 'docs(openspec): plan #')`. The command reads the live title and body. The implement job edits both in one step.

## Goals

- Cancel the stale run when the pull request is edited.
- Keep the command on the live pull request.

## Decisions

- **A job-level group keyed to the pull request.** `${{ github.workflow }}-${{ github.event.pull_request.number }}` with `cancel-in-progress: true` cancels the earlier run of the same pull request. The later event reads the delivery title, so its condition is false and the job is skipped.
- **No content test in the command.** The earlier attempt let a malformed plan pass. The command keeps its rules.

## Risks

- Two jobs of the same workflow and pull request cancel each other. Only `plan-check` uses the group.

## Tests

- The contract test reads the job and asserts the group and the cancellation.
