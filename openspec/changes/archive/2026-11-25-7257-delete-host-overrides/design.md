# Design

## Decisions
- Delete the override path. The rule on host fields moves into the gate, its one other user.

## Rejected alternatives
- Keep `deploy-stack` writing overrides: `cluster` puts the values of git back, so the write has no effect and misleads.
