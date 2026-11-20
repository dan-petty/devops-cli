## REMOVED Requirements

### Requirement: Each image build keeps its own gha cache scope
**Reason**: The image builds move from the GitHub Actions cache to a registry cache for each image (#6404), so no build has a `gha` scope.
**Migration**: The requirement 'Each image build keeps its own registry cache' of this capability holds each build to the `:buildcache` ref of its target.

## ADDED Requirements

### Requirement: Each image build keeps its own registry cache

The image builds of `./Dockerfile` in `ci.yml`, `release.yml` and `service-image-test.yml` SHALL set
`cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/<target>:buildcache`. A build with
no target SHALL use `service`. No cache entry of the three workflows SHALL use `type=gha`.

#### Scenario: The release reads three registry caches

- **WHEN** the release builds the Service, runner and MCP server images after an earlier release wrote their caches
- **THEN** the log of each build step shows the import of the `:buildcache` ref of its target

#### Scenario: The Service image test reads the service ref

- **WHEN** `service-image-test.yml` builds the Service image
- **THEN** the log of its build step shows the import of `ghcr.io/dan-petty/devops-cli/service:buildcache`

### Requirement: Only the release writes the image build cache

Only the `release.yml` build that pushes an image SHALL write its cache, with
`cache-to: type=registry,ref=ghcr.io/${{ github.repository }}/<target>:buildcache,mode=max`. A pull
request job SHALL read the cache with no registry login and no `packages` permission.

#### Scenario: The release writes the full cache

- **WHEN** the release builds and pushes the Service, runner and MCP server images
- **THEN** the log of each build step shows the export of the cache to the `:buildcache` ref of its target

#### Scenario: A pull request reads the cache with no login

- **WHEN** the Service image job of `ci.yml` builds the image on a pull request
- **THEN** the log of its build step shows the import of `ghcr.io/dan-petty/devops-cli/service:buildcache`, and the job has no login step and no `packages` permission
