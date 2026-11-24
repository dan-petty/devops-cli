# Proposal: #6963

## Why
The devcontainer base stage in `.devcontainer/Dockerfile` lacks `# hadolint ignore=DL3066` on `USER vscode`.
The `hadolint` pre-commit hook and CI gate fail with `.devcontainer/Dockerfile:45 DL3066 info: Non-numeric user-id may not be resolvable by host system`.
This failure stops the `Static Analysis` quality gate on pull requests, including release pull requests.

## What Changes
Add `# hadolint ignore=DL3066` above `USER vscode` in the `base` stage of `.devcontainer/Dockerfile`.
The change alters no behavior a consumer observes, so it sets `skip_specs: true` in its `.openspec.yaml`.
The change fits in one pull request.

## Capabilities
- Lint the Dockerfiles cleanly with hadolint in pre-commit and CI.

## Impact
- `Static Analysis` passes on pull requests and allows automated release merges.

## Feasibility
Confirmed against the real system.
Running `uv run devops ci --only hadolint` fails with `.devcontainer/Dockerfile:45 DL3066 info: Non-numeric user-id may not be resolvable by host system`.

## Existing Tool Considered
Used hadolint through `shenxianpeng/hadolint-pre-commit` v2.15.1.3.
The change uses the native hadolint inline ignore directive `# hadolint ignore=DL3066`.
The change deletes no internal code.
