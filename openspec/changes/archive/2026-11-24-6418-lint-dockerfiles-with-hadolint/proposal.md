# Proposal: #6418

## Why
No linter checks `Dockerfile` and `.devcontainer/Dockerfile`. Developers can add common Dockerfile mistakes without detection. Adding hadolint as a pre-commit hook and quality gate catches Dockerfile defects early. Closes #6418.

## What Changes
- Add the `hadolint` pre-commit hook (`shenxianpeng/hadolint-pre-commit` rev `v2.15.1.3`) to `.pre-commit-config.yaml`.
- Add `.hadolint.yaml` that ignores rule DL3008 with a recorded reason.
- Add `# hadolint ignore` comments in `Dockerfile` and `.devcontainer/Dockerfile` for intentional settings.
- Add `hadolint` as a `devops ci` quality gate row that runs the pre-commit hook.
- Add `ci:hadolint` to `RUNNER_TOOLS` under `pre-commit`.
- Add test coverage in `tests/commands/test_ci_row_commands.py`.

## Capabilities
- Run hadolint over project Dockerfiles with `devops ci --only hadolint` and in `Static Analysis`.
- Run hadolint automatically in pre-commit git checks.

## Impact
- `Static Analysis` runs hadolint over Dockerfiles.
- The gate blocks pull requests that introduce invalid Dockerfile syntax or unapproved practices.

## Feasibility
Confirmed against real system. `pre-commit run hadolint --all-files` runs clean on Linux x86_64 in the devcontainer and runner image.

## Existing Tool Considered
Used `shenxianpeng/hadolint-pre-commit` v2.15.1.3. Upstream `hadolint/hadolint` uses `language: system` and lacks a packaged binary.
