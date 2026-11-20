## REMOVED Requirements

### Requirement: Each image build keeps its own gha cache scope
**Reason**: The image builds move from the GitHub Actions cache to a registry cache for each image (#6404), so no build has a `gha` scope.
**Migration**: The requirement 'Each image build keeps its own registry cache' of this capability holds each build to the `:buildcache` ref of its target.

## ADDED Requirements

### Requirement: Each image build keeps its own registry cache

The image builds of `./Dockerfile` in `ci.yml`, `release.yml` and `service-image-test.yml` SHALL set
`cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/<target>:buildcache`. A build with
no target SHALL use `service`. No cache entry of the three workflows SHALL use `type=gha`. The
`test-tree` row SHALL fail on a `type=gha` entry and on an image build cache entry that does not
name the ref of its target.

#### Scenario: The release reads three registry caches

- **WHEN** `uv run devops ci --check --only test-tree` reads the Service, runner and MCP server builds of `release.yml`
- **THEN** it finds the `:buildcache` refs of `service`, `runner` and `mcp-server`, and the row exits 0

#### Scenario: A cache entry uses the Actions cache

- **WHEN** a workflow has `cache-from: type=gha,scope=service`
- **THEN** `uv run devops ci --check --only test-tree` fails and names the workflow file and the line

#### Scenario: The Service image test reads the service ref

- **WHEN** `uv run devops ci --check --only test-tree` reads `service-image-test.yml`
- **THEN** it finds `cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/service:buildcache` for the Service image build

### Requirement: Only the release writes the image build cache

Only the `release.yml` build that pushes an image SHALL write its cache, with
`cache-to: type=registry,ref=ghcr.io/${{ github.repository }}/<target>:buildcache,mode=max`. A pull
request job SHALL read the cache with no registry login and no `packages` permission. The
`test-tree` row SHALL fail when a `cache-to` entry does not set `mode=max`.

#### Scenario: The release writes the full cache

- **WHEN** `uv run devops ci --check --only test-tree` reads the builds of `release.yml` that push an image
- **THEN** each `cache-to` entry sets `mode=max`, and the row exits 0

#### Scenario: A pull request reads the cache with no login

- **WHEN** the Service image job of `ci.yml` builds the image on a pull request
- **THEN** the log of its build step shows the import of `ghcr.io/dan-petty/devops-cli/service:buildcache`, and the job has no login step and no `packages` permission

### Requirement: The GHCR retention workflow keeps the build cache tag

The GHCR retention workflow SHALL keep the `buildcache` tag of each package that it cleans.

#### Scenario: A run that names the cache tag

- **WHEN** a person runs `cleanup-devcontainer.yml` with `tag: buildcache` and `dry_run: true`
- **THEN** the step 'Resolve Target Cleanup and Exclusion Tags' prints `buildcache` in the line `Protected tags:`, and the dry run of the cleanup action lists no version for deletion
