# Tasks

## 1. Workflow: one test run per merge

- [x] 1.1 Change the workflow contracts to the new conditions: the shard job skips the release branch of this repository, the job `Tests on Main` reads the tests of main with `actions: read`, `Tests & Coverage` needs both and skips the coverage steps when no shard passed, the push group holds the commit, and a fork branch with a release name fails the contract
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py tests/commands/test_ci.py tests/github/test_ci_job_time.py`
- [x] 1.2 Change `.github/workflows/ci.yml`: the concurrency group of a push is its commit, the shards skip the release pull request, the new job `Tests on Main` waits for the push run of the base commit, and `Tests & Coverage` reads its result
  - Verification: `$ uv run devops ci --only actionlint,zizmor`

## 2. Documents

- [x] 2.1 Amend ADR 0014 with decision O3, its evidence, the rejected options and the consequences, and state in `RELEASE_CYCLE.md` and `docs/SDLC.md` how the release pull request reads the tests of main
  - Verification: `$ uv run devops ci docs`
