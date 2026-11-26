## ADDED Requirements

### Requirement: A check that read no image fails
`devops k8s image-pins`, of a folder or of the environment tree, SHALL exit non-zero when the renders name no image, also with `--managed`. A dry run renders nothing and counts no image.

#### Scenario: A build with no image
- **WHEN** `devops k8s image-pins <folder> --managed ghcr.io/example/product` runs and `kubectl kustomize` gives no object
- **THEN** the command exits non-zero and says that the renders name no image

## MODIFIED Requirements

### Requirement: The CI job checks a pull request that changes the pins
The job `image-pins` of `.github/workflows/image-pins.yml` SHALL run `devops k8s image-pins k8s/devops` with `--managed` for each image of devops-cli, with read-only permissions and the kubectl of the devtools image. The workflow SHALL run only for a pull request or a push to `main` that changes `k8s/devops/`, a module of the command, `.devcontainer/Dockerfile`, `.github/actions/devtools-commands` or the workflow file.

#### Scenario: The job's steps
- **WHEN** `uv run devops ci --check --only actionlint,zizmor` checks `image-pins.yml`, and the live check reads the log of the `Image Pins` job of a pull request
- **THEN** the check passes, the job has the permission `contents: read`, the step `Copy kubectl from the devtools image` restores or builds kubectl, the step `Put kubectl on PATH` puts it first on the path, and the last step runs `uv run devops k8s image-pins k8s/devops` with `--managed` for the Service, runner and MCP server images

#### Scenario: A pull request that changes no pin
- **WHEN** a pull request changes only `README.md`
- **THEN** the `paths` filter starts no run of the workflow
