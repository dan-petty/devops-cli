## ADDED Requirements

### Requirement: Each image build keeps its own gha cache scope

The image builds of `ci.yml`, `release.yml` and `service-image-test.yml` SHALL set
`cache-from: type=gha,scope=<target>` and, where they write the cache,
`cache-to: type=gha,scope=<target>,mode=max`. A build with no target SHALL use `service`. The
`test-tree` row SHALL fail when an image build cache entry of `./Dockerfile` lacks its target scope,
and when a `cache-to` entry does not set `mode=max`.

#### Scenario: The release builds three scopes

- **WHEN** the `test-tree` check reads the Service, runner and MCP server builds of `release.yml`
- **THEN** it finds `scope=service`, `scope=runner` and `scope=mcp-server`, and each `cache-to` entry sets `mode=max`

#### Scenario: A cache entry without a scope

- **WHEN** a workflow has `cache-to: type=gha` with no scope
- **THEN** the `test-tree` row fails and names the workflow file and the line

#### Scenario: The Service image test reads the service scope

- **WHEN** the check reads `service-image-test.yml`
- **THEN** it finds `cache-from: type=gha,scope=service` for the Service image build
