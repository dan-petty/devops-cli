## ADDED Requirements

### Requirement: Base stage without the project
The `.devcontainer/Dockerfile` SHALL define a `base` stage that holds the base image, the tools and the dependencies, and SHALL keep the project package and its install out of that stage.

#### Scenario: The base stage builds without the project
- **WHEN** a person runs `docker buildx build --target base --load -t devcontainer-base -f .devcontainer/Dockerfile .`
- **THEN** the build succeeds and `docker run --rm --entrypoint python devcontainer-base -c 'import devops_cli'` exits non-zero

### Requirement: Project stage on the base image
The `.devcontainer/Dockerfile` SHALL define a `project` stage that starts `FROM ${BASE_IMAGE}` and SHALL put the project `COPY` and its install in that stage.

#### Scenario: The project stage builds on a base image
- **WHEN** a person runs `docker buildx build --target project --build-arg BASE_IMAGE=devcontainer-base --load -t devcontainer-project -f .devcontainer/Dockerfile .`
- **THEN** the build succeeds and `docker run --rm --entrypoint devops devcontainer-project --version` exits zero

### Requirement: Action builds the Feature image first
The `.github/actions/devcontainer-image/action.yml` SHALL run the Dev Containers CLI build with the `base` target, push the Feature image by digest, and run `docker buildx build --target project --build-arg BASE_IMAGE=<feature digest>` after that build.

#### Scenario: The action runs the Feature build before the project build
- **WHEN** a person runs the `DevContainer Image` job with `workflow_dispatch` on the changed branch
- **THEN** the job succeeds, the Feature build step completes before the project build step, and the smoke step starts the digest of the project build

### Requirement: Project build keeps push-by-digest and metadata
The project build SHALL push with `push-by-digest=true` and SHALL write the final digest to a metadata file that the action reads for its `digest` output.

#### Scenario: The action reads the final digest from the metadata file
- **WHEN** the `DevContainer Image` job runs on a pull request that changes `.github/actions/devcontainer-image/**`
- **THEN** the `image` step output equals the `containerimage.digest` value in the project build metadata file, and the push uses `push-by-digest=true`

### Requirement: Release tags the smoke-tested project digest
`release.yml` SHALL pass the digest of the project build to the smoke test, the attestation and the tag, and SHALL NOT tag the Feature build digest.

#### Scenario: The release tags the smoke-tested project digest
- **WHEN** a person runs `docker buildx imagetools inspect ghcr.io/dan-petty/devops-cli/devcontainer:<release-tag> --format '{{json .Manifest}}'` after a release
- **THEN** the tag resolves to the digest that the `Smoke-Test DevContainer Image` job started and the `Attest & Tag DevContainer Image` job attested

### Requirement: Feature build keeps the registry cache
The action SHALL pass `cache-from` to both builds and `cache-to` to the Feature build, so a release that changes only `src/` reads the Feature layers from the registry cache.

#### Scenario: A source-only release reads the Feature layers from the cache
- **WHEN** the `Build DevContainer Image` job runs on a release that changes only files under `src/` with the registry cache populated
- **THEN** the Feature build reports a cache hit for the Feature layers and the job completes in under 5 minutes plus 1 minute
