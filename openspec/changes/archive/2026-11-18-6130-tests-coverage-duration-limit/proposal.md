# Proposal: #6130

## Why
The average execution time of the `Tests & Coverage` check of `ci.yml` on `main` is over the 360-second limit. The last 20 runs took 393 seconds on average. This duration violates AGENTS.md rule 5. The total test suite grew from 1,190 modules to 1,335 modules, which increased total recorded test time by 41 percent. Four shards can no longer complete in 360 seconds.

## What Changes
- Refresh the recorded module durations in `tests/module_durations.json` from the JUnit reports of the last 20 CI runs using `devops ci durations`.
- Add a fifth shard to the `test-shard` matrix in `.github/workflows/ci.yml`.
- Update the workflow comments and the documentation in `docs/SDLC.md` and `docs/TESTING.md` to describe the five test shards.

## Capabilities
None. The change alters no CLI command, option, model, or library API.

## Impact
- The CI test suite splits across five runner jobs instead of four.
- The average duration of each test shard decreases from approximately 360 seconds to approximately 280 seconds, keeping the total check duration safely below the 360-second limit.

## Feasibility
The workflow and test selection system natively support arbitrary shard counts. The comment in `.github/workflows/ci.yml` and `docs/SDLC.md` specifically identify adding a fifth shard to the matrix when test duration approaches the limit. All unit tests pass with five shards.

## Existing Tool Considered
`devops ci durations` and GitHub Actions job matrices provide the sharding mechanism. No new code or library is required.
