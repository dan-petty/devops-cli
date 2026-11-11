# Proposal: #4656

## Why
GitHub Pages publishes the site with the legacy build of `main:/docs`. That build runs 3 jobs on each push to `main`, also when the push changes no file under `docs/`. The account runs at most 20 hosted jobs at one time, so each job that does no work makes the queue of each pull request longer. Owner decision O5 of the CI audit (2026-11-11): an agent adds a Pages workflow with a `docs/**` filter, and the owner switches the Pages source in the repository settings. Closes #4656.

## What Changes
- `.github/workflows/pages.yml` (new): a `build` job and a `deploy` job with the official Pages actions. The workflow runs on a push to `main` that changes `docs/` or the workflow, and on a manual run. A push that changes no site file starts no Pages job.
- `docs/SDLC.md`, the head of `docs/_config.yml` and an amendment line in ADR 0012 say that the workflow builds and deploys the site.
- The change alters only a CI workflow and documents, which no consumer of devops-cli observes, so it has no spec delta (`skip_specs: true`). The published site stays the same.

## Capabilities
- None.

## Impact
- `.github/workflows/pages.yml`, `docs/SDLC.md`, `docs/_config.yml`, `docs/adr/0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md`.
- The required checks (`Static Analysis`, `Tests & Coverage`, `Semantic PR title`) and the code scanning rule do not change. The `Docs Site Build` check of `ci.yml` does not change.
- The saving starts only after the owner sets the Pages source to GitHub Actions. Until then, the legacy build and the workflow both publish the same `docs/`.
- The change fits one pull request.

## Feasibility
- Pages API on 2026-11-11: `build_type` is `legacy` and the source is branch `main`, path `/docs`. The legacy build runs as the dynamic workflow `pages-build-deployment` with the jobs `build`, `report-build-status` and `deploy`.
- Actions API, 2026-11-04 to 2026-11-11: 606 runs of `pages-build-deployment` for 606 commits of `main` (471 success, 135 cancelled). `git diff-tree` of the head commits: 351 of the 606 pushes changed no file under `docs/`. Job times of 40 successful runs: `build` mean 25.3 s (max 32 s), `report-build-status` mean 4.1 s, `deploy` mean 10.0 s (max 18 s).
- GitHub workflow syntax reference (`on.push.paths`): a push that changes no file that matches the filter starts no run.
- `actions/jekyll-build-pages` v1.0.13 (`action.yml` at `44a6e6be`) runs `docker://ghcr.io/actions/jekyll-build-pages:v1.0.13`, the image that the `Docs Site Build` check runs by digest.
- README of `actions/deploy-pages` v5.0.1: with a branch source, the deployment must come from that branch. Environments API: the deployment branch policy of the `github-pages` environment allows the branch `main` only. So a run on `main` deploys before and after the owner switch.
- `uv run devops ci --only actionlint,zizmor` passes, and `zizmor` 1.30.1 reports no finding for `pages.yml`.

## Existing Tool Considered
- The official GitHub Pages actions (`actions/configure-pages`, `actions/jekyll-build-pages`, `actions/upload-pages-artifact`, `actions/deploy-pages`), in the form of the GitHub starter workflow for Jekyll, and the native `paths` filter. The change builds no tool.
- The change deletes no internal code.
