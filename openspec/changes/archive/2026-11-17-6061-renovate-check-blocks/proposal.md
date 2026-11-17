# Proposal: #6061

## Why
Renovate pull requests stall when a check fails although the update breaks no project code. The audit of every Renovate pull request since 2026-11-16 20:00Z (design.md) finds four causes: the hang of `test_sigterm_export` in `Service Image Tests` (#6048), tests and one gate case that compare a pin with a constant (#6060, #6069), a `ty` update that renames two rules (a real change of the project), and the `Semantic PR title` check, which refuses `chore(deps)` when an update changes a file under `src/devops_cli/`. #6057 gave the prefix `fix(deps):` to chart updates only. The Dependency Dashboard already holds seven branches that change such a file with the title `chore(deps)`: `patch-uv`, `tools`, `major-openspec`, `lock-file-maintenance`, `pip-compile-refresh`, the `python runtime` minor and the `node` major. Each one would fail the title check.

Closes #6061.

## What Changes
- `.github/renovate.json` gives each update of a file under `src/devops_cli/` the prefix `fix(deps):`. Such files are the tools lock with its npm and pip-compile files, the runner tools table and `DEFAULT_PYTHON_VERSION`.
- A group takes the prefix of its first update, so the groups `uv`, `node`, `python runtime` and `bandit`, which mix such a file with other files, set the prefix for each of their updates. Lock file maintenance sets it too, because it writes the npm lockfiles of the tools lock.
- `docs/SDLC.md` names the new prefix rule, and says that no check other than the Fail-to-Pass Check skips a Renovate pull request.
- No workflow changes. `Service Image Tests` and the `k8s` row keep running on Renovate pull requests: a base image or a Python update is the change that the image test must see, and the hang and the pin comparisons have their own fixes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release-concurrency-and-renovate`: 1 added requirement.

## Impact
- The next Renovate run gives the seven branches above the title `fix(deps): ...`, and release-please releases each of them when it merges.
- An update of the `node` or `python runtime` group that changes no file under `src/devops_cli/`, such as a patch of a node image, now also has `fix(deps)` and adds a changelog line. The `dcgm-exporter` group of #6057 already works this way.
- No code, test, workflow or manifest changes.

## Feasibility
- Renovate 44.239.1, the version of the CronJob, builds a branch from the first update after a sort (`dist/workers/repository/updates/generate.js:230`). It uses `semanticCommitType` only when no `commitMessagePrefix` is set (`:55`), and `.github/renovate/base.json` sets one for every update.
- `matchFileNames` compares the package file and its lock files (`dist/util/package-rules/files.js`), and lock file maintenance takes the package rules (`dist/workers/repository/updates/flatten.js:117-119`).
- Renovate's own `applyPackageRules` on one update of each member of the affected groups gives `chore(deps):` with the config of `main` and `fix(deps):` with this change. Updates that change no file under `src/devops_cli/` keep `chore(deps):`.
- `renovate-config-validator --strict --no-global` of Renovate 44.239.1 accepts both configuration files.

## Existing Tool Considered
Renovate, the dependency tool of the project (ADR 0027), sets the prefix per package rule, as the Dockerfile and chart rules already do. The change builds no tool. Cost: about 250k tokens and 1.5 hours, most of it for the audit.
