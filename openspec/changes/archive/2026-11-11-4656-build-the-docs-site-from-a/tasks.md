# Tasks

## 1. Workflows

Kind: workflows. Reads: `.github/workflows/ci.yml`. Changes: `.github/workflows/pages.yml`.

- [x] 1.1 Add `pages.yml`: a build job and a deploy job with the official Pages actions pinned by commit SHA, on a push to `main` that changes `docs/` or the workflow and on a manual run, with the least permissions, the concurrency group `pages` and nested timeouts
  - Verification: `$ uv run devops ci --only actionlint,zizmor`
- [x] 1.2 Keep every workflow contract (pinned actions, checkout credentials, no expression in a run block) true for the new file
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 2. Documents

Kind: documents. Changes: `docs/SDLC.md`, `docs/_config.yml`, `docs/adr/0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md`.

- [x] 2.1 Say in `docs/SDLC.md` and in the head of `docs/_config.yml` that `pages.yml` builds and deploys the site, and add the amendment of the Pages decision to ADR 0012
  - Verification: `$ uv run devops ci docs`

- Pending a person: the owner sets Settings > Pages > Build and deployment > Source to GitHub Actions. Then a push to `main` that changes no file under `docs/` starts no Pages job.
