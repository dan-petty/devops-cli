# Design

## Decisions

- **Set `branch = true` in [tool.coverage.run] rather than passing `--branch` on the command line**: The configuration file is the single source of truth for coverage settings. Both the local gate and CI read it, so one change covers both.
- **Pin `actions/upload-artifact` by commit SHA**: Every other action in ci.yml is pinned by SHA. This matches the existing pattern and prevents a silent version change.
- **Set retention-days to 7**: The artifact is for review of a recent run. A short retention keeps storage low while covering the review window.
- **Do not change `fail_under`**: The owner dropped the fail_under raise from this issue per the decision on #2356. The 85% floor and 90% changed-line gate stay as they are.

## Rejected alternatives

- **Raise `fail_under` to the measured total with branches on**: The owner struck this from the issue on 2026-10-27, deferring it to #2356 which sets a lower global floor of 85% and a gate on changed lines.
- **Build a custom artifact upload script**: `actions/upload-artifact` already uploads a file by path with a retention period. The project uses it for the SARIF report in the same workflow. Building a custom script adds tokens to build, keep and fix with no benefit.
