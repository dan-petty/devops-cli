## MODIFIED Requirements

### Requirement: The CI job checks a pull request that changes the pins
The job `image-pins` of `.github/workflows/image-pins.yml` SHALL run `devops k8s image-pins` with read-only permissions and the pinned helm. The workflow SHALL run only for a pull request that changes `k8s/`, the command's modules, the registry module `src/devops_cli/docker/registry.py` or the workflow file.

#### Scenario: The job's steps
- **WHEN** `image-pins.yml` is read
- **THEN** its `pull_request` trigger has the paths `k8s/**`, `src/devops_cli/**/image_pins.py`, `src/devops_cli/docker/registry.py` and `.github/workflows/image-pins.yml`, the job has the permission `contents: read`, and its last step runs `uv run devops k8s image-pins`

#### Scenario: A pull request that changes no pin
- **WHEN** a pull request changes only `README.md`
- **THEN** the `paths` filter starts no run of the workflow
