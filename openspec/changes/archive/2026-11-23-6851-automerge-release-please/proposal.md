# Proposal: #6851

## Why
This change closes #6851. When release-please creates or updates a release pull request, auto-merge must be enabled so GitHub merges the release pull request automatically as soon as its required status checks pass.

## What Changes
In `.github/workflows/release.yml`, remove the restriction that limits auto-merge to urgent fixes. The step now turns on GitHub auto-merge unconditionally on every release pull request with the release App token (`gh pr merge "$RELEASE_PR" --repo "$REPOSITORY" --auto --squash`). Update `RELEASE_CYCLE.md` and `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md` accordingly.

This change alters CI workflows and documentation only. It changes no `devops` command, option, message, manifest, or service behavior. Thus, it has no spec delta and sets `skip_specs: true` in `.openspec.yaml`.

This change fits one pull request.

## Capabilities
None. The change alters CI workflow automation only and sets `skip_specs: true`.

## Impact
Release pull requests will squash-merge automatically upon passing all required checks, triggering the release publish jobs without manual human intervention.

## Feasibility
Confirmed against `.github/workflows/release.yml` lines 61-108. The step `Merge the Release Pull Request on an Urgent Fix` previously checked for `release-now`, `priority/p0-critical`, or `scope/security` with `priority/p1-high`, exiting with code 0 when non-urgent. Pull request #6845 in `dan-petty/devops-cli` is currently open with all CI checks passing (`devops gh pr checks 6845`) and `auto-merge: disabled` (`devops gh pr view 6845`). Verified in `dan-petty/infra#59` that `gh pr merge --auto --squash` executed with the release App token arms GitHub auto-merge and automatically squash-merges once checks pass.

## Existing Tool Considered
GitHub CLI (`gh pr merge --auto --squash`), which is already installed and utilized in `.github/workflows/release.yml` and `.github/workflows/release-merge.yml`. No custom tool is built. The internal GraphQL and REST query script that checked labels in the urgent-fix condition of `.github/workflows/release.yml` is deleted.
