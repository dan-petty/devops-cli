# Task: Required CI Checks Bind Merges into Release and Main (#842)

**Issue**: [#842](https://github.com/dan-petty/devops-cli/issues/842)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/github

## Description

GitHub repository rulesets enforce required CI status checks for merges into `release/*` and `main` branches. ADR 0004 formally documents the verification policy, pinning the authoritative check jobs (`Static Analysis` and `Tests & Coverage`), strict status checks mode, the `devops pr update --dispatch-ci` route with least-privilege `actions: write` isolation, the cluster-managed machine-account token, and owner decisions on Copilot reviews and branch creation.

In this deliverable:
1. Deleted deprecated `.github/branch-protection.yml` which declared an inert `ci` context.
2. Updated help text across `devops gh branch-protection` CLI subcommands (`audit`, `sync`, group) to clarify that they manage classic branch protection policies and do not cover repository rulesets.
3. Added CliRunner tests in `tests/test_github_branch_protection.py` verifying that help text mentions `classic` and `rulesets`, and that auditing with a missing policy file cleanly reports an error without a traceback.
4. Authored `docs/adr/0004-ci-is-the-authoritative-gate.md` in ADR 0001–0003 format documenting the CI verification policy, required checks, strict mode, dispatch route, machine-account token location, and owner decisions (D6 Copilot review and rejected options #704, #405, #406).
5. Added glossary definitions for `Gate`, `Check`, and `Required check` with `_Avoid_:` lines to `CONTEXT.md`.
6. Regenerated documentation via `devops docs generate` and verified that `devops docs check` passes.
7. Added changelog fragment `changelog.d/842.md`.

## Acceptance Criteria

- [x] `rg -n 'branch-protection.yml' --glob '!CHANGELOG.md' --glob '!docs/ROADMAP.md' --glob '!docs/agent/tasks/task-114-*'` matches only allowed code defaults and reference documentation.
- [x] `devops gh branch-protection --help` specifies that the command manages classic branch protection policies and does not cover rulesets; tested via CliRunner in `tests/test_github_branch_protection.py`.
- [x] `devops gh branch-protection audit --repo dan-petty/devops-cli` reports `Branch protection policy file not found` with no traceback when policy file is absent; tested via CliRunner in `tests/test_github_branch_protection.py`.
- [x] `docs/adr/0004-ci-is-the-authoritative-gate.md` exists in ADR 0001–0003 format recording the required checks, strict mode, dispatch route, token boundary, D6 Copilot review policy, and rejected options.
- [x] `CONTEXT.md` contains `Gate`, `Check`, and `Required check` entries with `_Avoid_:` lines conforming to lifecycle property invariants.
- [x] Documentation regenerated and verified via `devops docs check`.
- [x] Changelog fragment `changelog.d/842.md` created.
- [x] Task file `docs/agent/tasks/task-842-required-ci-checks.md` passes `tests/test_agent_task_files.py`.
- [x] `git diff origin/release/v0.2.27...HEAD --stat -- .github/workflows/ci.yml tests/test_architectural_invariants.py` makes no edits to CI workflow or architectural invariants.
- [x] All unit, CLI, and invariant tests pass offline via `uv run devops ci`.
- Pending a person (after #984 merges): A bot update after a release-branch merge produces fresh `Static Analysis` and `Tests & Coverage` runs on the PR head.
  - `gh pr view <n> --json headRefOid --jq .headRefOid`
  - `gh api repos/dan-petty/devops-cli/commits/<sha>/check-runs --jq '.check_runs[].name'`
  - `gh run list --workflow ci.yml --event workflow_dispatch --branch <head> --limit 3`
- Pending a person (owner settings): Rulesets 21466414 and 23059172 each show `required_status_checks` with `Static Analysis` and `Tests & Coverage` in strict mode, without `code_coverage`, and with `do_not_enforce_on_create: true` on release.
  - `gh api repos/dan-petty/devops-cli/rulesets/21466414`
  - `gh api repos/dan-petty/devops-cli/rulesets/23059172`
- Pending a person: A throwaway PR with a failing test shows `gh pr view <n> --json mergeStateStatus --jq .mergeStateStatus` as `BLOCKED`.
- Pending a person: The `main` ruleset's Copilot rule sets `review_on_push: false`.
  - `gh api repos/dan-petty/devops-cli/rulesets/21466414`

## Deliverables

- [x] `.github/branch-protection.yml` removed.
- [x] `src/devops_cli/lang/en/help.py` and `src/devops_cli/commands/gh.py` updated with classic branch protection help text.
- [x] `tests/test_github_branch_protection.py` updated with CliRunner tests for help text and missing policy file.
- [x] `docs/adr/0004-ci-is-the-authoritative-gate.md` created.
- [x] `CONTEXT.md` updated with `Gate`, `Check`, and `Required check` entries.
- [x] `docs/CLI_REFERENCE.md` and `docs/commands/gh.md` regenerated.
- [x] `changelog.d/842.md` changelog fragment created.
- [x] `docs/agent/tasks/task-842-required-ci-checks.md` task record created.
