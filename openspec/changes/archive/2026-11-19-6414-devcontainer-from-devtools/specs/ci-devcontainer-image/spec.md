## REMOVED Requirements

### Requirement: The DevContainer image builds on its own inputs
**Reason**: Its list named the tool lock, which is no input of the image now, and its last scenario named an invariant test that the repository no longer has. OpenSpec refuses a MODIFIED block that drops a scenario, so the requirement goes and comes back with a new name.
**Migration**: The requirement "The DevContainer image builds when an input of its build changes" holds the same rule with the inputs of the image FROM devtools.

## ADDED Requirements

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
The build action SHALL build the image with the Dev Containers CLI of the `devcontainers-cli` stage of `.devcontainer/Dockerfile`, and the smoke action SHALL start it with the CLI of the image that it starts. Neither action SHALL run `devops install-tools`, and the step that calls the smoke action SHALL have `timeout-minutes`.

#### Scenario: A pull request run of the DevContainer Image job
- **WHEN** the `DevContainer Image` workflow runs on a pull request
- **THEN** the job exits with code 0 in less than 6 minutes, and its log shows the step `Copy the Dev Containers CLI from the devtools image` and no `devops install-tools` step

#### Scenario: The workflows pass their checks
- **WHEN** a person runs `uv run devops ci --check --only actionlint,zizmor`
- **THEN** both rows pass for `devcontainer-image.yml`, `release.yml` and the two actions
