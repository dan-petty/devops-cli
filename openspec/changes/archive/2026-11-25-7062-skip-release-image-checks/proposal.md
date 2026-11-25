# Proposal: #7062

## Why

The `release_comments` row of `roadmap-service` calls `_run_release_comments_adapter` with cluster image digest checks and an HTTP registry client for every repository in `service.repos`.
`live_release` always queries `ghcr.io/dan-petty/devops-cli/service:<tag>` and `ghcr.io/dan-petty/devops-cli/runner:<tag>`.
When `dan-petty/devtools` or `dan-petty/infra` publishes a release, GHCR returns HTTP 404 after the 20-minute grace period, so every round fails and suspends the row. Closes #7062.

## What Changes

- Add `publishes_release_images(repo: str) -> bool` in `src/devops_cli/roadmap/release_roll.py` to match `RepoRef(repo).key` against the repository parsed from `CONST_ROADMAP_RELEASE_IMAGE_PREFIX`.
- Update `_run_release_comments_adapter` in `src/devops_cli/roadmap/run.py` to pass `roll` and `client` only when `publishes_release_images(repo)` holds, and pass `roll=None` and `client=None` for all other repositories.
- Update step 20 of `docs/CLUSTER.md` to state that `Live since <time>` image checks run only for the repository that publishes the Service and runner images.
- Update `tests/roadmap/test_roadmap_run_job_rows.py` and `tests/roadmap/test_roadmap_release_roll.py` with unit tests for `publishes_release_images` and unrelated repositories.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-release-comments`: Skip cluster and registry image checks on repositories that do not publish `CONST_ROADMAP_RELEASE_IMAGE_PREFIX`.

## Impact

- Code: `src/devops_cli/roadmap/release_roll.py`, `src/devops_cli/roadmap/run.py`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/roadmap/test_roadmap_release_roll.py`, `tests/roadmap/test_roadmap_run_job_rows.py`

## Feasibility

- Confirmed against source: `src/devops_cli/roadmap/run.py:1072-1080` (`_run_release_comments_adapter`) passes `roll=lambda: cluster_digests(ClusterJobs())` and `client=client` unconditionally, while `src/devops_cli/roadmap/release_roll.py:87` (`live_release`) formats `f"{CONST_ROADMAP_RELEASE_IMAGE_PREFIX}/{image}:{tag}"` where `CONST_ROADMAP_RELEASE_IMAGE_PREFIX = "ghcr.io/dan-petty/devops-cli"`.
- Confirmed in cluster Loki logs: `devops_cli.roadmap.release_comments` fails with HTTP 404 on `ghcr.io/dan-petty/devops-cli/service:v0.20.1` for `dan-petty/infra` and `v1.1.9`–`v1.1.12` for `dan-petty/devtools`.
- Offline tests double GitHub with `GitHubFake`, HTTP with `WebFake`/`RegistryFake`, and Kubernetes with `FakeCluster`.

## Existing Tool Considered

Extends the internal adapter and helper instead of adopting an external release tool, because `release_comments` uses this repository's `release_comments.json` ledger, Deployment `roadmap-service`, CronJob `devops-cli-runner`, and `CONST_ROADMAP_RELEASE_IMAGE_PREFIX`; estimated cost is ~20k tokens and 0.5 hours to build and verify, with no internal code deleted.
