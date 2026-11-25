# container-image-layers Specification

## Purpose
The runner and Service images keep their dependencies in layers that a change of `src/` or a release does not change, so a node that holds the previous release pulls only the small project layer.

## Requirements

### Requirement: The lock stage writes the requirements of the lock without the project
The `lock` stage of `Dockerfile` SHALL copy only `pyproject.toml` and `uv.lock`, and SHALL write only the runtime requirements of `uv.lock` with the `review` extra, with `uv export --locked --no-dev --no-emit-project`. A release that changes only the project version then gives the same file, and the stages that copy it keep their cache.

#### Scenario: A version change gives the same requirement files
- **WHEN** a person runs `docker buildx build --target lock --output type=local,dest=<dir>` on two commits that differ only in the project version of `pyproject.toml` and `uv.lock`
- **THEN** the files `lock/runtime.txt` of the two outputs are equal, and no output holds another file under `lock/`

### Requirement: A change of the project keeps the dependency layers
Only the `builder` and `runner-builder` stages SHALL copy a file of `src/`, and no stage under the `runner`, `mcp-server` or `service` stage SHALL build on them. `deps` and `runner-deps` SHALL install only `/lock/runtime.txt` from the `lock` stage, with `--require-hashes`. Each `uv sync` and `uv pip` SHALL mount the uv cache of root as a cache mount.

#### Scenario: A change of src/ keeps the layers under the final stage
- **WHEN** a person builds the `runner`, `mcp-server` and `service` targets two times, and the second build follows a change of a file under `src/`
- **THEN** `docker image inspect --format '{{json .RootFS.Layers}}'` gives the same layer digests for the two builds of each image, except the one layer of the project

### Requirement: A final stage adds only the apt upgrade and the project
The `service` and `mcp-server` stages SHALL run `apt-get upgrade` and then copy from `builder` only the `devops_cli` package, its dist-info and `/app/.venv/bin/devops`, in one `COPY --link --parents`. The `runner` stage SHALL run no apt step, because the devtools image runs `apt-get upgrade` in its own build. It SHALL copy the same three paths from `runner-builder` in one `COPY --link --parents`. No final stage SHALL install an apt package.

#### Scenario: The final stage adds the upgrade and one copy of the project
- **WHEN** a person runs `docker history` on a `runner`, `mcp-server` or `service` image
- **THEN** the layers over those of `runner-deps`, `mcp-server-deps` or `service-deps` are the `apt-get upgrade` layer of the Service and MCP server images and the one `COPY` layer of `devops_cli`, its dist-info and `devops`

### Requirement: The Dockerfile takes its tools from the devtools image
The `Dockerfile` SHALL name `ghcr.io/dan-petty/devtools` in one `FROM` line, with a tag and a digest, as the stage `devtools`, and Renovate SHALL move the tag and the digest in the `devtools` group. The `runner-deps` stage SHALL build FROM `devtools`. The Service and MCP server images SHALL copy from `devtools` only gh, kubectl and helm. The `Dockerfile` SHALL hold no tool version, download URL or checksum.

#### Scenario: The Dockerfile installs no tool
- **WHEN** a person runs `git grep -n -e 'releases/download' -e 'sha256sum' -- Dockerfile`
- **THEN** the command prints nothing

### Requirement: The Service image runs OpenSpec of the root lockfile
The `openspec` stage SHALL build FROM the `node` stage, copy `package.json` and `package-lock.json`, run `npm ci --omit=optional --ignore-scripts`, keep only OpenSpec in the `package.json` of the tree and run `npm prune --offline --ignore-scripts`, so the tree holds OpenSpec at the version of `package-lock.json` and the packages that it needs, and no Style Dictionary. The official Node binary of the `node` stage SHALL run it, because the Service image is on trixie.

#### Scenario: OpenSpec runs in the Service image
- **WHEN** a person runs `docker run --rm --entrypoint openspec <service image> --version`
- **THEN** the command prints the `@fission-ai/openspec` version of `package-lock.json` and exits 0

#### Scenario: The stage holds no Style Dictionary
- **WHEN** a person builds `--target openspec` and lists `node_modules` of `/usr/local/lib/openspec` in the result
- **THEN** the list holds `@fission-ai` and no `style-dictionary`

### Requirement: Each image build keeps its own registry cache

The image builds of `./Dockerfile` in `ci.yml`, `release-image.yml` and `service-image-test.yml` SHALL set
`cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/<target>:buildcache`. A build with
no target SHALL use `service`. No cache entry of the three workflows SHALL use `type=gha`.

#### Scenario: The release reads three registry caches

- **WHEN** the release builds the Service, runner and MCP server images after an earlier release wrote their caches
- **THEN** the log of each build step shows the import of the `:buildcache` ref of its target

#### Scenario: The Service image test reads the service ref

- **WHEN** `service-image-test.yml` builds the Service image
- **THEN** the log of its build step shows the import of `ghcr.io/dan-petty/devops-cli/service:buildcache`

### Requirement: Only the release writes the image build cache

Only the `Build` job of `release-image.yml`, which pushes an image, SHALL write its cache, with
`cache-to: type=registry,ref=ghcr.io/${{ github.repository }}/<target>:buildcache,mode=max`. A pull
request job SHALL read the cache with no registry login and no `packages` permission.

#### Scenario: The release writes the full cache

- **WHEN** the release builds and pushes the Service, runner and MCP server images
- **THEN** the log of each build step shows the export of the cache to the `:buildcache` ref of its target

#### Scenario: A pull request reads the cache with no login

- **WHEN** the Service image job of `ci.yml` builds the image on a pull request
- **THEN** the log of its build step shows the import of `ghcr.io/dan-petty/devops-cli/service:buildcache`, and the job has no login step and no `packages` permission

### Requirement: Build context drops bytecode and root Dockerfile enables build checks
The root `.dockerignore` SHALL exclude `__pycache__` directories and loose `.pyc` and `.pyo` files from the build context. The root `Dockerfile` SHALL set `# check=error=true` as a parser directive directly under the syntax directive.

#### Scenario: The root build enforces build checks
- **WHEN** a person reads line 2 of `Dockerfile`
- **THEN** line 2 holds `# check=error=true`

#### Scenario: The build context excludes bytecode
- **WHEN** `.dockerignore` is inspected
- **THEN** it excludes `**/__pycache__`, `**/*.pyc`, and `**/*.pyo` after `!src/**`

### Requirement: The uv-seed image pre-populates the dev dependency cache
The `Dockerfile` SHALL define, before `service`, a `uv-seed-build` stage `FROM devtools` that fills `/cache` from the dev requirements and the stub project that the `lock` stage gives, and a `uv-seed` stage `FROM scratch` that holds `/cache` and a `/seed.json` matching `_seed_fits`. A change of the project version MUST NOT change the cache layer.

#### Scenario: The seed target builds and a default build still builds service
- **WHEN** `uv run devops ci --check --only hadolint` runs after adding `uv-seed-build` and `uv-seed` before `service` in `Dockerfile`
- **THEN** `hadolint` exits 0 and reports no warning or error for `Dockerfile`, and `test_service_dockerfile_base_images_pinned_by_digest` passes with `FROM scratch AS uv-seed`

#### Scenario: A checkout syncs from the seed with no network
- **WHEN** the stage `uv-seed-smoke` of `smoke.Dockerfile` runs on the seed
- **THEN** `uv sync --locked --group dev --offline` exits 0, and `ruff`, `pytest` and `mypy` run

#### Scenario: A release keeps the cache layer
- **WHEN** a person builds `--target uv-seed`, changes only the project version in `pyproject.toml` and `uv.lock`, and builds it again
- **THEN** the build takes the cache layer from cache, and the digest of that layer is the same

### Requirement: CI validates the uv-seed target
The `mcp-server-image` job of `.github/workflows/ci.yml` SHALL bake `uv-seed` with `cache-from` pointing at `uv-seed:buildcache` and `push: false`, verify `seed.json` and an offline `--network none` sync against `devops-cli-runner:local`, and scan `devops-cli-uv-seed:local` under `trivy-image-uv-seed`.

#### Scenario: CI workflow checks accept the uv-seed bake and smoke steps
- **WHEN** `uv run devops ci --check --only actionlint,zizmor` runs after editing `.github/workflows/ci.yml`
- **THEN** the command exits 0 and reports no finding in `.github/workflows/ci.yml`

### Requirement: Release publishes and verifies the uv-seed image
`.github/workflows/release.yml` SHALL include `uv-seed` in its `image` matrix (`category: trivy-image-uv-seed`, `scan-exit-code: "1"`), and `.github/workflows/release-image.yml` SHALL smoke-test `seed.json` and offline `--network none` sync in `verify` when `inputs.image == 'uv-seed'`.

#### Scenario: Release workflow checks accept the uv-seed matrix entry and smoke test
- **WHEN** `uv run devops ci --check --only actionlint,zizmor` runs after editing `.github/workflows/release.yml` and `.github/workflows/release-image.yml`
- **THEN** the command exits 0 and reports no finding in `.github/workflows/release.yml` or `.github/workflows/release-image.yml`

### Requirement: The image checks that need no container are build stages
`smoke.Dockerfile` SHALL define the stages `service-smoke`, `mcp-server-smoke`, `runner-smoke` and `uv-seed-smoke`, each of which starts from the image that a build argument names, by default the local tag of the target. The image jobs of `ci.yml` and the `Verify` job of `release-image.yml` SHALL build the stage of each image that they check, and a failed check SHALL fail the build. A release MUST NOT publish a stage of this file.

#### Scenario: The stage runs on the image under test
- **WHEN** a developer builds the `service` target and tags it `devops-cli-service:local` and runs `docker build -f smoke.Dockerfile --target service-smoke .`
- **THEN** the build exits 0

#### Scenario: A forbidden tool fails the stage
- **WHEN** the image that `SERVICE_IMAGE` names holds `uv`
- **THEN** the build of `service-smoke` exits non-zero

#### Scenario: The release tests the pushed digest
- **WHEN** the `Verify` job of an image runs
- **THEN** it builds the stage of that image with the pushed digest as its build argument

### Requirement: A pull request builds the images in the Docker Engine of the runner
The image jobs of `ci.yml` SHALL build with the Docker Engine of the runner, with no builder container, and SHALL read the registry cache that the release writes.

#### Scenario: The build reads the cache and transfers no tar file
- **WHEN** a person reads the log of the `Runner Image` job of a pull request that changes no dependency
- **THEN** the dependency stages show as `CACHED`, and the log holds no `sending tarball` line
