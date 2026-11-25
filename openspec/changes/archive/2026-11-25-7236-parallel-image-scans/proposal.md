# Proposal: #7236

## Why
The `Runner Image` check ran its three image scans and its smoke tests one after the other. In 4 runs on 2026-11-25 it took 274 to 365 s, against a limit of 360 s, and the scans took 90 to 146 s of that.

## What Changes
- The three scan steps of the `Runner Image` job run as background steps, and the job waits for all of them at its end.
- `.github/actions/image-scan` gives each category its own Trivy cache directory.

## Capabilities
- `ci-image-scan`: new requirement for scans that run at the same time.

## Impact
The images, severities, exit codes, ignore file and SARIF categories do not change. A failed gate scan now fails the job at the wait step, and the later steps still run. Each scan downloads the vulnerability database for itself (about 138 MiB).

## Feasibility
- GitHub runs steps of one job in parallel since 2026-06-25, and a composite action can be a background step.
- `actionlint` 1.17.1, the pinned version, accepts `background`, `wait` and `wait-all`.

## Existing Tool Considered
GitHub parallel steps do this. No shell job control and no new job is necessary.
