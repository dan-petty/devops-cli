# ci-devcontainer-image Specification

## Purpose
The DevContainer Image check proves that the devcontainer image builds and starts as its remote user. It runs where an image input changes, and daily for all other changes, so that a push to a pull request that changes only the CLI source does not wait for it.

## Requirements

### Requirement: The DevContainer image builds when an input of its build changes
The DevContainer Image workflow SHALL run on the daily schedule, on a manual run, and on a pull request that changes an input of the image other than `src/`: `.devcontainer/`, which holds the digest of the devtools image, `.dockerignore`, `pyproject.toml`, `uv.lock`, `README.md`, its two actions or the workflow file. A pull request that changes only `src/` files SHALL start no job of it.

#### Scenario: A pull request changes only src
- **WHEN** a pull request changes only files under `src/`
- **THEN** GitHub starts no DevContainer Image job for it

#### Scenario: A pull request changes an image input
- **WHEN** a pull request changes `.devcontainer/Dockerfile`, for example the digest of the devtools image
- **THEN** the DevContainer Image job builds the image and starts it as its remote user

#### Scenario: The daily run
- **WHEN** the daily schedule fires
- **THEN** the DevContainer Image job builds the image from `main` and starts it

### Requirement: The image actions use the Dev Containers CLI of the devtools image
The build action SHALL build the image with the Dev Containers CLI of the `devcontainers-cli` stage of `.devcontainer/Dockerfile`, and the smoke action SHALL start it with the CLI of the image that it starts. The step that calls the smoke action SHALL have `timeout-minutes`.

#### Scenario: A pull request run of the DevContainer Image job
- **WHEN** the `DevContainer Image` workflow runs on a pull request
- **THEN** the job exits with code 0 in less than 6 minutes, and its log shows the step `Copy the Dev Containers CLI from the devtools image`

#### Scenario: The workflows pass their checks
- **WHEN** a person runs `uv run devops ci --check --only actionlint,zizmor`
- **THEN** both rows pass for `devcontainer-image.yml`, `release.yml` and the two actions

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
