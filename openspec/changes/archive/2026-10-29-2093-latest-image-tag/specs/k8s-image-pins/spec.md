## MODIFIED Requirements

### Requirement: The image pins are the images of the rendered Applications
`devops k8s image-pins` SHALL render each Argo CD Application of the repository, a path source with `kubectl kustomize` and a chart source with `helm template --skip-tests` and the value files of the repository, and SHALL take each `image` value of the rendered objects. It SHALL NOT resolve an image whose repository an `ImageUpdater` object names, or an image of a registry that only the cluster or the host reaches.

#### Scenario: A path Application and a chart Application
- **WHEN** a path Application's Deployment runs a Docker Hub image, an image that the chart's `ImageUpdater` names and an image of a `.svc` registry, and the chart renders a StatefulSet with a tab after a value
- **THEN** the pins are the Docker Hub image and the StatefulSet's image, the managed repository is listed apart, the `.svc` image is listed as local, and `helm template` runs with `--skip-tests`

#### Scenario: A chart that does not render
- **WHEN** `helm template` of a chart Application exits 1
- **THEN** the command stops with an `ImagePinError` that names the chart command and gives helm's error

## ADDED Requirements

### Requirement: An image on the latest tag fails the check
The command SHALL refuse each rendered image that names no digest, and names the `latest` tag or no tag, unless an `ImageUpdater` object names its repository. It SHALL exit 1 before it resolves any image, and SHALL name each refused image and its Applications.

#### Scenario: The latest tag or no tag
- **WHEN** an image names `latest` or no tag, and no digest
- **THEN** it names `latest`; an image with a version tag, or with a digest, does not

#### Scenario: A path Application names latest images
- **WHEN** a path Application's Deployment runs an image with the tag `latest`, an untagged image, an untagged image that the chart's `ImageUpdater` names, and a `latest` image of a `.svc` registry
- **THEN** the `latest` images are the tagged one, the untagged one and the `.svc` one, and none of them is a pin

#### Scenario: A value file sets the latest tag
- **WHEN** the chart's render names `quay.io/example/alertmanager:latest`
- **THEN** that image is a `latest` image of the chart's Application, and not a pin

#### Scenario: The command refuses a latest image
- **WHEN** an Application names `example/app:latest`
- **THEN** the command exits 1, names the image and its Application, and resolves no image
