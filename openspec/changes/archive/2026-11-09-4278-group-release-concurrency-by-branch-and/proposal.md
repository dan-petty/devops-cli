# Proposal: #4278

## Why
`.github/workflows/release.yml` used one static concurrency group, `release`. Runs on different branches waited on the same group or cancelled older waiting runs. In addition, `.github/renovate.json` lacked explicit rules for Terraform, devcontainer configurations, pre-commit hooks, GitHub Actions digest pinning, and disabled Helm values managers. Closes #4278.

## What Changes
1. Change `.github/workflows/release.yml` concurrency group to `release-${{ github.ref }}` with `cancel-in-progress: false`.
2. Update `.github/renovate.json` to:
   - Add a package rule for `terraform` with labels `type/chore` and `scope/infra`.
   - Add a package rule for `devcontainer` with labels `type/chore` and `scope/ci`.
   - Add a package rule for `pre-commit` with labels `type/chore` and `scope/ci`.
   - Add `pinDigests: true` for `github-actions`.
   - Add a package rule to disable `helm-values` and `helmv3` managers so that committed values remain deliberate edits.
   - Set `rebaseWhen: "behind-base-branch"`.
3. Update `tests/invariants/test_workflow_contracts.py` to assert the branch-scoped release concurrency group.
4. Update `tests/core/test_renovate_config.py` with invariant tests for the new package rules.
5. Update `docs/SDLC.md` to describe the extended Renovate rules.

## Capabilities
- Release workflow runs isolate by branch reference.
- Renovate proposes updates for Terraform, devcontainers, pre-commit hooks, and pinned action digests under proper taxonomy labels.

## Impact
- Workflow contracts and Renovate configuration tests assert these guarantees.
- No existing manifests or production configurations change behavior unexpectedly.

## Feasibility
Verified locally:
- `release.yml` concurrency group accepts `${{ github.ref }}`.
- `renovate-config-validator` validates `.github/renovate.json` with zero errors.
- `uv run devops ci test tests/invariants/test_workflow_contracts.py tests/core/test_renovate_config.py` verifies both behaviors.

## Existing Tool Considered
GitHub Actions native concurrency expressions and Renovate Bot built-in manager rules cover the requirements without custom code.
