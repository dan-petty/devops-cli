# Proposal: #6404

## Why

#6404: the release writes the build cache of the Service, runner and MCP server images to the GitHub Actions cache (`type=gha`). In release run 44415593173 the three exports took 140.6, 61.3 and 140.2 s, and the Actions cache of the repository holds 10.5 GB. The devcontainer release writes a registry cache instead, and its export took 14.4 s.

## What Changes

- The image builds of `release.yml`, `ci.yml` and `service-image-test.yml` read `ghcr.io/${{ github.repository }}/<target>:buildcache` with `cache-from: type=registry`. The two `release.yml` builds of each image read it, and the build that pushes the image writes it with `mode=max`. The release stays the only writer (#4646). The `no-cache-filters` entries do not change.
- The pull request jobs get no new permission. The packages are public, so a read needs no login.
- `tests/gate/tree_checks/image_cache.py` fails on a `type=gha` cache entry and on an image build cache entry that does not name the `:buildcache` ref of its target. It keeps the `mode=max` check of a write.
- `cleanup-devcontainer.yml` adds `buildcache` to the tags that it keeps, so a manual run that names the tag does not delete the cache of the devcontainer package. The workflow deletes no tag of the three other packages. #4816 keeps `buildcache` when it makes the workflow cover the four packages.
- The change is a CI change, but the requirement 'Each image build keeps its own gha cache scope' of `container-image-layers` names the `gha` scope. So the delta removes it and adds a requirement for the registry ref, and the spec stays true.
- `docs/CLUSTER.md` names the registry cache in place of the `gha` scope.

The change fits one pull request.

## Capabilities

- `container-image-layers`: REMOVED requirement 'Each image build keeps its own gha cache scope'. ADDED requirements 'Each image build keeps its own registry cache', 'Only the release writes the image build cache' and 'The GHCR retention workflow keeps the build cache tag'. OpenSpec refuses a MODIFIED block that drops a scenario, and the three scenarios of the old requirement name the `gha` scope.

## Impact

- The first release after the merge finds no `:buildcache` tag and builds each image with no cache. A pull request that builds an image before that release also builds with no cache. The import error of a missing tag does not stop a build.
- After the old entries of the Actions cache expire, the Actions cache of the repository holds less than 10.5 GB.
- Each of the three packages gets one `buildcache` tag. Image Updater follows the digest of `latest`, so it does not read the new tag.
- #5942 (verify the per-image `gha` scopes after two releases) loses its premise. Its comment of 2026-11-19 says so.

## Feasibility

- The devcontainer release already reads and writes `ghcr.io/${{ github.repository }}/devcontainer:buildcache` with `type=registry` and `mode=max` (`.github/workflows/release.yml`, job `devcontainer-image`), and #4816 counted the `buildcache` tag in that package on 2026-11-19.
- The packages are public: the runner Jobs pull `ghcr.io/dan-petty/devops-cli/runner` with no `imagePullSecrets`, and the admission policy `roadmap-service-jobs` refuses a Job that sets one (`docs/CLUSTER.md`). So a pull request job reads the cache with no login.
- BuildKit reports a cache import that fails as a warning and builds on (the `docker/build-push-action` log of a cold cache shows `failed to configure registry cache importer`), so the first run with no tag does not fail.

## Existing Tool Considered

The BuildKit registry cache backend (`type=registry`), which `docker/setup-buildx-action` and `docker/build-push-action` already give, covers the need. The change builds nothing and deletes the `gha` cache entries of the three images. The backend removes no old cache blob and keeps no tag on its own, so the retention workflow keeps the `buildcache` tag, and GHCR keeps one tagged cache index for each image.
