# k8s-image-pins Specification

## Purpose
Before a merge, each image that an Argo CD Application of the repository pins resolves in its registry, so a wrong tag fails the pull request and not the sync.

## Requirements

### Requirement: The image pins are the images of the rendered Applications
`devops k8s image-pins` SHALL render each Argo CD Application of the repository, a path source with `kubectl kustomize` and a chart source with `helm template` and the value files of the repository, and SHALL take each `image` value of the rendered objects. It SHALL NOT resolve an image whose repository an `ImageUpdater` object names, or an image of a registry that only the cluster or the host reaches.

#### Scenario: A path Application and a chart Application
- **WHEN** a path Application's Deployment runs a Docker Hub image, an image that the chart's `ImageUpdater` names and an image of a `.svc` registry, and the chart renders a StatefulSet with a tab after a value
- **THEN** the pins are the Docker Hub image and the StatefulSet's image, the managed repository is listed apart, and the `.svc` image is listed as local

#### Scenario: A chart that does not render
- **WHEN** `helm template` of a chart Application exits 1
- **THEN** the command stops with an `ImagePinError` that names the chart command and gives helm's error

### Requirement: Each pin resolves in its registry as an anonymous client
The command SHALL resolve each pinned image once with `docker buildx imagetools inspect`, with an empty Docker configuration, and SHALL exit 1 when an image does not resolve, naming the image, its Applications, its registry and the resolver's error.

#### Scenario: A tag that its registry does not hold
- **WHEN** the registry answers an inspect of a pinned image with `not found`
- **THEN** the command exits 1 and names the image, its Application, its registry and the resolver's error line

#### Scenario: Each pin resolves
- **WHEN** each pinned image resolves to a digest
- **THEN** the command exits 0 and reports the number of resolved images

### Requirement: A dry run renders and resolves nothing
`devops k8s image-pins --dry-run` SHALL start no render and no resolve, and SHALL name the resolve command that a run sends for each image.

#### Scenario: A dry run
- **WHEN** a person runs `devops k8s image-pins --dry-run`
- **THEN** the resolver receives no request and the output names `docker buildx imagetools inspect <image>`

### Requirement: The CI job checks a pull request that changes the pins
The `image-pins` job of `ci.yml` SHALL run `devops k8s image-pins` on a pull request that changes `k8s/`, the command's modules or `ci.yml`, with read-only permissions and the pinned helm, and SHALL skip the check on any other pull request.

#### Scenario: The job's steps
- **WHEN** `ci.yml` is read
- **THEN** the job `image-pins` has a paths filter on `k8s/**`, `src/devops_cli/**/image_pins.py` and `.github/workflows/ci.yml`, the permissions `contents: read` and `pull-requests: read`, and runs `uv run devops k8s image-pins` only when the filter matches
