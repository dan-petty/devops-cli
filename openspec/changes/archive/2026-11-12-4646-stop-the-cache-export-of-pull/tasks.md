# Tasks

## 1. Workflows

- [x] 1.1 Remove `cache-to` from the Service Image, Runner Image and MCP Server Image jobs of `ci.yml`, so that a pull request reads the cache of `main` and writes none, and correct the comment of the Runner Image job
  - Verification: `$ ! git grep -n cache-to .github/workflows/ci.yml .github/workflows/service-image-test.yml .github/workflows/devcontainer-image.yml`
- [x] 1.2 Remove `cache-to` from the three `Build and Load` steps of `release.yml`, and keep one `cache-to` in the `Build and Push` step of each image job
  - Verification: `$ uv run devops ci --only actionlint,zizmor`

## Workflow follow-up

- #4928 gives the cache of each image its own scope.
- One day after the merge, a comment on #4646 gives the size of the Actions cache, the mean time of the Service Image job and the `CACHED` count of the `builder` stage. #4649 builds on these numbers.
