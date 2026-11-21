# Design

## Decisions

- The record key goes with the step. The stage job keeps an App-only branch of a Ready item by its `stage.pending` mark, which the stage job writes, so the rule of the orphan cleanup stays.
- `GitHubClient.create_ref` goes too: after the step, no code calls it.

## Rejected alternatives

- Keep the step for a person to run: no flow needs a branch with no commit, and the first push of a job makes the branch.
