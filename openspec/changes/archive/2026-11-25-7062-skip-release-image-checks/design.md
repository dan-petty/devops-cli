# Design

## Decisions

- **Match `RepoRef(repo).key` against the repository extracted from `CONST_ROADMAP_RELEASE_IMAGE_PREFIX` inside `src/devops_cli/roadmap/release_roll.py`.**: `CONST_ROADMAP_RELEASE_IMAGE_PREFIX` already defines the single image prefix (`ghcr.io/dan-petty/devops-cli`) used by `live_release`, `Deployment` `roadmap-service`, and `CronJob` `devops-cli-runner`. Deriving the repository name from that constant avoids introducing a duplicate constant or setting.
- **Gate `roll` and `client` in `_run_release_comments_adapter` before opening `http_client`.**: `comment_releases` already skips `_live_pass` when `roll is None` or `client is None`. Skipping `http_client` and `ClusterJobs` for unrelated repositories avoids both HTTP 404 failures and unnecessary Kubernetes and GHCR requests while preserving `Released in <tag>` comments and `release_comments.json` updates.

## Rejected alternatives

- **Add a new per-repository config setting under `roadmap.release_comments`.**: No other repository in `service.repos` publishes Deployment `roadmap-service` or CronJob `devops-cli-runner` (`admissionpolicy.yaml:150` pins `ghcr.io/dan-petty/devops-cli/runner`), so adding configuration would create unused knobs without benefit.
- **Ignore HTTP 404 for all releases on all repositories.**: `live_release` checks missing tags after `CONST_ROADMAP_RELEASE_IMAGE_GRACE_MINUTES` specifically to detect broken `devops-cli` image builds (#3507); suppressing 404 globally would hide real release image failures on `dan-petty/devops-cli`.
