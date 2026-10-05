# Task: Switch from Dependabot to Renovate (#1219)

**Issue**: [#1219](https://github.com/dan-petty/devops-cli/issues/1219)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p2-medium
**Scope**: scope/ci

## Description
Retires Dependabot by removing `.github/dependabot.yml` and transitions to Renovate via `.github/renovate.json`. Automated Python package updating is disabled in Renovate so that Python and `uv` dependencies are updated deliberately as part of project/milestone workflows with synchronized `uv.lock`.

## Acceptance Criteria
- [x] `.github/dependabot.yml` removed.
- [x] `.github/renovate.json` created with schema, recommended presets, and taxonomy labeling rules for GitHub Actions and Docker.
- [x] Python package managers (`pep621`, `pip_requirements`, `pip-compile`, `setup-cfg`) disabled in Renovate configuration.
- [x] `docs/SDLC.md` updated to document Renovate and project-managed `uv` dependencies.
- [x] All local quality gates in `uv run devops ci` pass with 100% green status.
- [x] Changelog fragment `changelog.d/1219.md` present.
- [x] Task file `docs/agent/tasks/task-1219-switch-to-renovate.md` present.

## Deliverables
- [x] `.github/dependabot.yml` (removed)
- [x] `.github/renovate.json`
- [x] `docs/SDLC.md`
- [x] `changelog.d/1219.md`
- [x] `docs/agent/tasks/task-1219-switch-to-renovate.md`
