# Proposal: #4646

## Why
The Service Image, Runner Image and MCP Server Image jobs of `ci.yml` export a `type=gha` BuildKit cache with `mode=max` on each push to a pull request. GitHub keeps the cache of a pull request in the scope of its merge ref, so no other pull request reads it. These exports fill the Actions cache past its 10 GB limit, and GitHub then evicts the layers that the release writes on `main`. The export takes about 2.6 runner-minutes on each push that builds the images. The `ci.yml` comment of the Runner Image job also says that the job shares the `builder` stage with the Service Image job through the cache, but each job builds that stage again. Closes #4646.

## What Changes
- The three image jobs of `ci.yml` keep `cache-from: type=gha` and lose `cache-to`. A pull request reads the cache of `main` and writes none.
- In `release.yml`, the Service, runner and MCP server jobs write the cache once each, from the `Build and Push` step of the published image. The `Build and Load` steps only read the cache. Six exports become three.
- The comment of the Runner Image job in `ci.yml` says that the job builds the shared stages again and reads only the cache of the release.
- No spec delta (`skip_specs: true`): the change alters only CI workflows, and no command, message, manifest or service changes.
- The change fits one pull request.

## Capabilities
- None. The change alters only CI workflows.

## Impact
- Each push to a pull request that builds the images saves the export: 67.7 s in the Service Image job, 38.5 s in the Runner Image job and 50.2 s in the MCP Server Image job (means of 6 jobs each, measured on 2026-11-12), about 2.6 runner-minutes in total.
- The Actions cache keeps only the layers of the release builds and the other caches, so the layers of `main` stay in the cache. A pull request then reads the `lock`, `deps` and `builder` layers that did not change.
- The cache of each release still uses the default scope `buildkit`, so the release job that ends last writes the index. #4928 gives each image its own scope.
- A release writes the cache only after the smoke test and the scan pass, because the `Build and Push` step comes after them.
- The required checks and the security scans do not change.

## Feasibility
- The Actions cache API on 2026-11-12 (`actions/cache/usage`): 10,705,664,218 bytes in 376 active entries. The cache list held 483 entries, 12.83 GB. The BuildKit entries of pull request refs held 11.24 GB in 415 entries. The BuildKit entries of `refs/heads/main` held 0.10 GB in 11 entries, only the index and small base layers. The oldest pull request BuildKit entry was 51 minutes old, so GitHub evicts an entry that nobody reads in less than one hour.
- The Actions API for the last 60 completed pull request runs of `ci.yml` (2026-11-12, 12:12Z to 14:49Z): 27 runs built each image. The Service Image job took 3.41 min on average, and its build step 142 s.
- The BuildKit logs of 18 jobs (6 runs) show the step `exporting to GitHub Actions Cache` with a mean of 67.7 s (Service), 38.5 s (Runner) and 50.2 s (MCP server), and a mean of 4.3, 7.8 and 10.0 `CACHED` steps for each build.
- GitHub documents that a workflow run can restore the caches of its own ref and of the base branch, and that a pull request cache is in the scope of `refs/pull/<n>/merge`. `release.yml` runs on a push to `main`, so a pull request can read its cache.
- The cache list shows that BuildKit stores each layer under `buildkit-blob-1-<digest>` and each index under `index-<scope>-1-...`, so the layers do not depend on the job that wrote them.

## Existing Tool Considered
The BuildKit `gha` cache backend of `docker/build-push-action` and the cache scope rules of GitHub Actions. No new tool. The change deletes six `cache-to` lines: three in the pull request jobs of `ci.yml` and three in the `Build and Load` steps of `release.yml`.
