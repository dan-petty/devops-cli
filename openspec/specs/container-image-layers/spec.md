# container-image-layers Specification

## Purpose
The runner and Service images keep their dependencies in layers that a change of `src/` or a release does not change, so a node that holds the previous release pulls only the small project layer.

## Requirements

### Requirement: The lock stage writes the requirements of the lock without the project
The `lock` stage of `Dockerfile` SHALL copy only `pyproject.toml` and `uv.lock`, and SHALL write the runtime requirements and the dev requirements of `uv.lock` with `uv export --locked --no-emit-project`. A release that changes only the project version then gives the same files, and the stages that copy them keep their cache.

#### Scenario: A version change gives the same requirement files
- **WHEN** a person runs `docker buildx build --target lock --output type=local,dest=<dir>` on two commits that differ only in the project version of `pyproject.toml` and `uv.lock`
- **THEN** the files `lock/runtime.txt` and `lock/dev.txt` of the two outputs are equal

### Requirement: A change of the project keeps the dependency layers
Only the `builder` and `runner-builder` stages SHALL copy a file of `src/`, and no stage under the `runner`, `mcp-server` or `service` stage SHALL build on them. `deps` SHALL install `/lock/runtime.txt`, and `runner-deps` SHALL install `/lock/runtime.txt` and `/lock/dev.txt`, from the `lock` stage, with `--require-hashes`. Each `uv sync` and `uv pip` SHALL mount the uv cache of root as a cache mount.

#### Scenario: A change of src/ keeps the layers under the final stage
- **WHEN** a person builds the `runner`, `mcp-server` and `service` targets two times, and the second build follows a change of a file under `src/`
- **THEN** `docker image inspect --format '{{json .RootFS.Layers}}'` gives the same layer digests for the two builds of each image, except the one layer of the project

### Requirement: A final stage adds only the apt upgrade and the project
The `service` and `mcp-server` stages SHALL run `apt-get upgrade` and then copy from `builder` only the `devops_cli` package, its dist-info and `/app/.venv/bin/devops`, in one `COPY --link --parents`. The `runner` stage SHALL run no apt step, because the devtools image runs `apt-get upgrade` in its own build. It SHALL copy the same three paths from `runner-builder` in one `COPY --link --parents`. No final stage SHALL install an apt package.

#### Scenario: The final stage adds the upgrade and one copy of the project
- **WHEN** a person runs `docker history` on a `runner`, `mcp-server` or `service` image
- **THEN** the layers over those of `runner-deps`, `mcp-server-deps` or `service-deps` are the `apt-get upgrade` layer of the Service and MCP server images and the one `COPY` layer of `devops_cli`, its dist-info and `devops`

### Requirement: The Dockerfile takes its tools from the devtools image
The `Dockerfile` SHALL name `ghcr.io/dan-petty/devtools` in one `FROM` line, with a tag and a digest, as the stage `devtools`, and Renovate SHALL move the tag and the digest in the `devtools` group. The `runner-deps` stage SHALL build FROM `devtools`. The Service and MCP server images SHALL copy from `devtools` only gh, kubectl, helm and the OpenSpec package tree. The `Dockerfile` SHALL hold no tool version, download URL or checksum, and SHALL not run `devops install-tools`.

#### Scenario: The Dockerfile installs no tool
- **WHEN** a person runs `git grep -n -e 'install-tools' -e 'releases/download' -e 'sha256sum' -- Dockerfile`
- **THEN** the command prints nothing

### Requirement: The Service image runs OpenSpec of the devtools image
The `openspec` stage SHALL keep only OpenSpec in the `package.json` of the npm tree of the devtools image and run `npm prune --offline --ignore-scripts`, so the tree holds OpenSpec and the packages that it needs. The official Node binary of the `node` stage SHALL run it, because the Service image is on trixie.

#### Scenario: OpenSpec runs in the Service image
- **WHEN** a person runs `docker run --rm --entrypoint openspec <service image> --version`
- **THEN** the command prints the OpenSpec version of the devtools image and exits 0

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
