## MODIFIED Requirements

### Requirement: The image actions use the Dev Containers CLI of the devtools image
The build action SHALL build the image with the Dev Containers CLI of the `devcontainers-cli` stage of `.devcontainer/Dockerfile`, and the smoke action SHALL start it with the CLI of the image that it starts. The step that calls the smoke action SHALL have `timeout-minutes`.

#### Scenario: A pull request run of the DevContainer Image job
- **WHEN** the `DevContainer Image` workflow runs on a pull request
- **THEN** the job exits with code 0 in less than 6 minutes, and its log shows the step `Copy the Dev Containers CLI from the devtools image`

#### Scenario: The workflows pass their checks
- **WHEN** a person runs `uv run devops ci --check --only actionlint,zizmor`
- **THEN** both rows pass for `devcontainer-image.yml`, `release.yml` and the two actions
