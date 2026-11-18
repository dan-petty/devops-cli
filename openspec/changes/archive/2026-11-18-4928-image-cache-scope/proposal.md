# Proposal: #4928

## Why

All image builds of `ci.yml`, `release.yml` and `service-image-test.yml` read and write the
BuildKit `gha` cache with the default scope `buildkit`. Each `cache-to` replaces the cache index of
that scope, and the parallel release jobs write the Service, runner and MCP server images, so the
cache of a release holds the dependency stages of only the image that ended last. A later release
rebuilds the `runner-deps` or `service-deps` layers and gives them new digests. Closes #4928.

## What Changes

- Each image build writes and reads `scope=<target>`: `service`, `runner` or `mcp-server`, and a
  build with no target uses `service`.
- A `cache-to` entry keeps `mode=max`, so it exports the dependency stages.
- A new `test-tree` check fails when an image build cache entry lacks its target scope or its
  `mode=max`, and names the workflow file and line.
- `docs/CLUSTER.md` and the `container-image-layers` specification state the scopes.

## Capabilities

### Modified

- `container-image-layers`: each image build keeps its own `gha` cache scope.

## Impact

A release finds the dependency stages that the last build of the same image wrote on `main`, so
the `runner-deps` and `service-deps` layers keep their digests. The cache list of `main` holds one
index for each of `service`, `runner` and `mcp-server`.

## Feasibility

Confirmed against the issue and the code: `git grep -n "type=gha" .github/workflows` gives 19
entries with no `scope=`, and the parallel jobs of `release.yml` each run `cache-to: type=gha,mode=max`.
The BuildKit `gha` backend documents the default `buildkit` scope and the `scope` option. The
`test-tree` row holds the offline check; the `tests/invariants` pytest file cannot assert a workflow
value after #6060.

## Existing Tool Considered

The BuildKit `gha` cache backend is already in use, so the verdict is `in-use`. Its `scope` option
gives each image its own index; it does not set the option or check the workflows. No maintained
tool adds this check. The change edits the workflows and adds the `test-tree` check, at about
20,000 tokens to build and 2,000 to keep.
