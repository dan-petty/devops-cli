# Proposal: #6032

## Why
The first live Renovate run (#4909) left 4 updates undone. A run at `LOG_LEVEL=debug` (Job `renovate-debug-2033`, 2026-11-16) and the source of Renovate 44.239.1 give the causes:

- `renovate/trivy` and `renovate/uv` ("update failure") hold only `pinDigest` updates of the `version` inputs of trivy-action and setup-uv (dependency type `uses-with`). The preset pins the digests of every github-actions dependency, but a version input has no place for a digest. The autoreplace finds no digest to write and stops the branch.
- `renovate/pypi-mcp-vulnerability` and `renovate/pypi-opentelemetry-api-vulnerability` ("empty commit") are indirect dependencies of `src/devops_cli/tools_lock/semgrep.txt`. semgrep pins `mcp==1.29.0` and `opentelemetry-api~=1.37.0`, also in its newest release 1.185.0. `uv pip compile --upgrade-package=<name>==<fix>` finds no solution, the lock does not change, and the commit is empty.
- The mcp branch also held 2 updates (1.30.0 and 2.3.0), because the major and the minor are split but the branch name of a security fix has no major part. uv got both pins in one command.

Closes #6032.

## What Changes
- The preset pins no digest of a `uses-with` dependency of github-actions. The action references and the images keep their digest pins.
- The preset gives a security fix one update for each dependency: `vulnerabilityAlerts.separateMajorMinor` is false, so the branch takes only the newest fixed release.
- The repository config holds the security fixes of `mcp` and `opentelemetry-api` in the semgrep lock while the lock is below the fix, and the Dependency Dashboard footer says why. The hold ends when the lock takes the fix.

These are behaviors of the Renovate config that the repository and the Service repositories observe, so the change has a spec delta.

## Capabilities
- `release-concurrency-and-renovate`: 3 added requirements.

## Impact
- The next run opens the `trivy` and `uv` branches with no digest pin, or skips them when nothing is left to update. It makes no branch for the two held fixes.
- No manifest, command or code under `src/` changes. The change fits one pull request.

## Feasibility
- Debug Job `renovate-debug-2033` (Renovate 44.239.1): the `trivy` and `uv` branches are titled `pin aquasecurity/trivy to 3f6334d` and `pin astral-sh/uv to 316c827`. The only 12 `pinDigest` updates of the run are on `uses-with` dependencies. For mcp and opentelemetry-api, uv 0.13.8 ran `uv pip compile ... --upgrade-package=mcp==2.3.0 --upgrade-package=mcp==1.30.0` and `--upgrade-package=opentelemetry-api==1.45.2`, and found no solution.
- PyPI, 2026-11-16: semgrep 1.179.0 and 1.185.0 require `mcp==1.29.0` and `opentelemetry-api~=1.37.0`. OSV: mcp is fixed in 1.30.0, opentelemetry-api in 1.45.1 and 1.45.2.
- `renovate --platform=local` lookups with the base and the new config: the base gives mcp 2 updates in one branch; the new config disables the 2 held fixes and keeps the certifi fix; with the holds removed, mcp gets 1 update (2.3.0).

## Existing Tool Considered
Renovate itself: `pinDigests`, `matchDepTypes`, `separateMajorMinor`, `matchCurrentVersion` and `dependencyDashboard.footer`. Rejected: a uv `--override` file for the semgrep lock, see the design. The change deletes no internal code.
