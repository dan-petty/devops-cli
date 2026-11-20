# Tasks

## 1. Make the tree check require the registry ref

Kind: other (test-only edit of a gate row). Changes: `tests/gate/tree_checks/image_cache.py`.

- [x] 1.1 Change `check_each_image_build_cache_entry_names_a_scope` into `check_no_cache_entry_uses_the_actions_cache`, which names each `type=gha` cache entry of the three workflows with its file and line. Change `check_each_image_build_cache_entry_uses_its_target_scope` into `check_each_image_build_cache_entry_uses_its_target_ref`, which names each image build cache entry that is not `type=registry` with `ref=ghcr.io/${{ github.repository }}/<target>:buildcache`, and keeps the `mode=max` check of a write
  - Verification: `$ uv run devops ci --check --only test-tree`

## 2. Move the image build cache to the registry

Kind: other (workflows). Changes: `.github/workflows/release.yml`, `.github/workflows/ci.yml`, `.github/workflows/service-image-test.yml`, `.github/workflows/cleanup-devcontainer.yml`.

- [x] 2.1 Set `cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/<target>:buildcache` in the six image builds of `release.yml`, the three image builds of `ci.yml` and the build of `service-image-test.yml`, and set `cache-to: type=registry,ref=ghcr.io/${{ github.repository }}/<target>:buildcache,mode=max` in the three builds of `release.yml` that push an image. Keep each `no-cache-filters` entry and each job permission
  - Verification: `$ ! git grep -n 'type=gha' -- .github/workflows`
- [x] 2.2 Add `buildcache` to the tags that `cleanup-devcontainer.yml` keeps
  - Verification: a run with `dry_run: true` prints `buildcache` in the line `Protected tags:` of the step 'Resolve Target Cleanup and Exclusion Tags'
- [x] 2.3 Validate the changed workflows
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor,test-tree`

## 3. Name the registry cache in the cluster document

Kind: other (documents). Changes: `docs/CLUSTER.md`.

- [x] 3.1 In the item **Image** of `docs/CLUSTER.md`, replace the sentence about the `gha` cache scope with the registry ref of each target, the one writer and the read with no login
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the first release that follows the merge, check that the step 'exporting cache to registry' of each of the three image builds takes less time than the `gha` export of release run 44415593173 (140.6, 61.3 and 140.2 s).
- Pending a person: after the old entries of the Actions cache expire, check that `uv run devops gh api repos/dan-petty/devops-cli/actions/cache/usage` shows less than 10.5 GB.
- Pending a person: after that release, check that the log of an image build of a pull request shows `CACHED` steps from the registry ref.
