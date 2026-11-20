## MODIFIED Requirements

### Requirement: The CI job checks a pull request that changes the pins
The job `image-pins` of `.github/workflows/image-pins.yml` SHALL run `devops k8s image-pins` with read-only permissions and the kubectl and helm of the devtools image. The workflow SHALL run only for a pull request or a push to `main` that changes `k8s/`, the command's modules, `src/devops_cli/docker/registry.py`, `.devops/project.toml`, `.devcontainer/Dockerfile`, `.github/actions/devtools-commands` or the workflow file.

#### Scenario: The job's steps
- **WHEN** `uv run devops ci --check --only actionlint,zizmor` checks `image-pins.yml`, and the live check reads the log of the `Image Pins` job of a pull request
- **THEN** the check passes, the job has the permission `contents: read`, the step `Put kubectl and helm on PATH` restores or builds the commands of the devtools image, and the last step runs `uv run devops k8s image-pins`

#### Scenario: A pull request that changes no pin
- **WHEN** a pull request changes only `README.md`
- **THEN** the `paths` filter starts no run of the workflow
