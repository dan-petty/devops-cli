# Proposal: #6404

## Why

#6404: the release writes the build cache of the Service, runner and MCP server images to the GitHub Actions cache (`type=gha`). In release run 44415593173 the three exports took 140.6, 61.3 and 140.2 s, and the Actions cache of the repository holds 10.5 GB. The devcontainer release writes a registry cache instead, and its export took 14.4 s.

## What Changes

- The image builds of `release.yml`, `ci.yml` and `service-image-test.yml` read `ghcr.io/${{ github.repository }}/<target>:buildcache` with `cache-from: type=registry`. The two `release.yml` builds of each image read it, and the build that pushes the image writes it with `mode=max`. The release stays the only writer (#4646). The `no-cache-filters` entries do not change.
- The pull request jobs get no new permission. The packages are public, so a read needs no login.
- `tests/gate/tree_checks/image_cache.py` goes: it read the workflows and asserted cache values, which the owner rule of 2026-11-16 forbids (owner decision of 2026-11-20 on this pull request). actionlint, zizmor and the build logs prove the change.
- The change is a CI change, but the requirement 'Each image build keeps its own gha cache scope' of `container-image-layers` names the `gha` scope. So the delta removes it and adds a requirement for the registry ref, and the spec stays true.
- `docs/CLUSTER.md` names the registry cache in place of the `gha` scope.

The change fits one pull request.

## Capabilities

- `container-image-layers`: REMOVED requirement 'Each image build keeps its own gha cache scope'. ADDED requirements 'Each image build keeps its own registry cache' and 'Only the release writes the image build cache'. OpenSpec refuses a MODIFIED block that drops a scenario, and the three scenarios of the old requirement name the `gha` scope.

## Impact

- The first release after the merge finds no `:buildcache` tag and builds each image with no cache. A pull request that builds an image before that release also builds with no cache. The import error of a missing tag does not stop a build.
- After the old entries of the Actions cache expire, the Actions cache of the repository holds less than 10.5 GB.
- Each of the three packages gets one `buildcache` tag. Image Updater follows the digest of `latest`, so it does not read the new tag.
- #5942 (verify the per-image `gha` scopes after two releases) loses its premise. Its comment of 2026-11-19 says so.

## Feasibility

- The devcontainer release already reads and writes `ghcr.io/${{ github.repository }}/devcontainer:buildcache` with `type=registry` and `mode=max` (`.github/workflows/release.yml`, job `devcontainer-image`), and #4816 counted the `buildcache` tag in that package on 2026-11-19.
- The packages are public: the runner Jobs pull `ghcr.io/dan-petty/devops-cli/runner` with no `imagePullSecrets`, and the admission policy `roadmap-service-jobs` refuses a Job that sets one (`docs/CLUSTER.md`). So a pull request job reads the cache with no login.
- BuildKit builds on when a cache import fails, so a run with no tag does not fail. The four image builds of the pull request of this change ran before any `buildcache` tag of the three packages existed. Each log shows `ERROR: failed to configure registry cache importer: ghcr.io/dan-petty/devops-cli/<target>:buildcache: not found`, and each build passed in 118 to 185 s. The answer is `not found` and not `denied`, so the read with no login reaches the package.

## Existing Tool Considered

The BuildKit registry cache backend (`type=registry`), which `docker/setup-buildx-action` and `docker/build-push-action` already give, covers the need. The change builds nothing and deletes the `gha` cache entries of the three images. GHCR keeps one tagged cache index for each image. No workflow of the repository cleans the service, runner or mcp-server packages, so nothing deletes their `buildcache` tags.
