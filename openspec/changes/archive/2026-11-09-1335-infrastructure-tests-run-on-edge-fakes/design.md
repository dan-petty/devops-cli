# Design

## Decisions

- Complete tracker issue #1335 by verifying that all six split items landed on `origin/main`.
- Remove the last identifier that contains `memory_store` in test code so that the store reference scan passes cleanly.
- Keep changes minimal and focused strictly on the tracker acceptance criteria.
- Archive the OpenSpec change directory in the final commit per project rules.

## Rejected alternatives

- Close tracker #1335 without an OpenSpec change folder: rejected because AGENTS.md requires an OpenSpec change folder for every issue.
- Re-implement or modify merged child changes: rejected because all six child issues are already merged and tested on `origin/main`.
