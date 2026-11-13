# k8s-image-pins Specification

## Purpose
Before a merge, each image that an Argo CD Application of the repository pins resolves in its registry, so a wrong tag fails the pull request and not the sync.

## Requirements

### Requirement: The image pins are the images of the rendered Applications
`devops k8s image-pins` SHALL render each Argo CD Application of the environment tree (`--k8s-dir`, else the profile fact `kubernetes.dir`), a path source with `kubectl kustomize` and a chart source with `helm template --skip-tests` and the value files that its ref sources name, and SHALL take each `image` value of the rendered objects. It SHALL NOT resolve an image whose repository an `ImageUpdater` object names, or an image of a registry that only the cluster or the host reaches.

#### Scenario: A path Application and a chart Application
- **WHEN** a path Application's Deployment runs a Docker Hub image, an image that the chart's `ImageUpdater` names and an image of a `.svc` registry, and the chart renders a StatefulSet with a tab after a value
- **THEN** the pins are the Docker Hub image and the StatefulSet's image, the managed repository is listed apart, the `.svc` image is listed as local, and `helm template` runs with `--skip-tests`

#### Scenario: A chart that does not render
- **WHEN** `helm template` of a chart Application exits 1
- **THEN** the command stops with an `ImagePinError` that names the chart command and gives helm's error

### Requirement: Each pin resolves in its registry as an anonymous client
The command SHALL resolve each pinned image once with a HEAD request of its manifest, through the HTTP client of the project at the public egress level, as an anonymous client that sends no stored credential. It SHALL exit 1 when an image does not resolve, naming the image, its Applications, its registry and the error of the resolver.

#### Scenario: A tag that its registry does not hold
- **WHEN** the registry answers the HEAD of a pinned image with 404
- **THEN** the command exits 1 and names the image, its Application, its registry and the error line `The registry gives no manifest for <image> (HTTP 404).`

#### Scenario: Each pin resolves
- **WHEN** each pinned image resolves to a digest
- **THEN** the command exits 0 and reports the number of resolved images

#### Scenario: A Docker Hub name
- **WHEN** the pins are `nginx:1.27`, `valkey/valkey:9.1.2-alpine` and `docker.io/traefik:v3.7.16`
- **THEN** the HEAD requests go to the host `registry-1.docker.io` for the repositories `library/nginx`, `valkey/valkey` and `library/traefik`, no request goes to the host `docker.io`, and the registry column shows `docker.io`

#### Scenario: A registry that asks for a token
- **WHEN** the registry answers the first HEAD with 401 and a Bearer challenge
- **THEN** the client sends one token request to the realm of the challenge with no credential, sends the HEAD again with the token, and the image resolves

#### Scenario: A reference with a digest
- **WHEN** a pinned image is `ghcr.io/example/app:1.0@sha256:<digest>`
- **THEN** the HEAD goes to the manifest of that digest, and the image resolves to it

#### Scenario: A registry that refuses an anonymous client
- **WHEN** the token endpoint of the registry answers 401
- **THEN** the command exits 1 and the error line says that reading the image needs credentials

#### Scenario: A manifest read sends no GET
- **WHEN** the command resolves its pins
- **THEN** each request to a manifest is a HEAD

### Requirement: A dry run renders and resolves nothing
`devops k8s image-pins --dry-run` SHALL start no render and no resolve, SHALL send no request, and SHALL name the request that a run sends for each image.

#### Scenario: A dry run
- **WHEN** a person runs `devops k8s image-pins --dry-run`
- **THEN** no request reaches a registry and the output names `HEAD https://<registry>/v2/<repository>/manifests/<reference>`

### Requirement: The CI job checks a pull request that changes the pins
The job `image-pins` of `.github/workflows/image-pins.yml` SHALL run `devops k8s image-pins` with read-only permissions and the pinned helm. The workflow SHALL run only for a pull request that changes `k8s/`, the command's modules, the registry module `src/devops_cli/docker/registry.py`, the project file `.devops/project.toml` or the workflow file.

#### Scenario: The job's steps
- **WHEN** `image-pins.yml` is read
- **THEN** its `pull_request` trigger has the paths `k8s/**`, `src/devops_cli/**/image_pins.py`, `src/devops_cli/k8s/app_sources.py`, `src/devops_cli/k8s/environment.py`, `src/devops_cli/docker/registry.py`, `.devops/project.toml` and `.github/workflows/image-pins.yml`, the job has the permission `contents: read`, and its last step runs `uv run devops k8s image-pins`

#### Scenario: A pull request that changes no pin
- **WHEN** a pull request changes only `README.md`
- **THEN** the `paths` filter starts no run of the workflow

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

### Requirement: A source of another public repository is fetched at its revision
A git source that does not name the origin of the repository that holds the tree SHALL be fetched once for each repository and revision, at its `targetRevision`, with a shallow `git fetch` that reads the URL and the revision after `--end-of-options`. A path source SHALL render from the fetched folder, and a value file `$<ref>/<path>` SHALL name `<path>` in the folder of the source with that ref. Only an `https` repository SHALL be fetched, and a dry run SHALL fetch nothing.

#### Scenario: The product base of another repository and a second ref
- **WHEN** the Application `devops` names the path `k8s/devops` of another public repository at `main`, and the Application `monitoring` has a `values` ref on the origin and a `product` ref on the other repository
- **THEN** the other repository is fetched once at `main`, the image of its Deployment is a pin of `devops`, and `helm template` reads the first value file from the checkout and the second from the fetched folder

#### Scenario: A source that is not an https repository
- **WHEN** a path source names `file:///srv/product`
- **THEN** the command stops with an `ApplicationSourceError` and starts no fetch

#### Scenario: A dry run of another repository
- **WHEN** `collect_image_pins` runs under a dry run with a path source of another repository
- **THEN** the planned commands hold the fetch of that repository at its revision, and no fetch starts

### Requirement: The Argo CD gate reads the sources of another repository
The Argo CD gate (`check_argocd_gate`) SHALL check the Applications of an environment tree, and SHALL read each git source and each `$<ref>` value file as `devops k8s image-pins` reads them. A fetch that fails SHALL fail the Application and name the repository, the revision and git's error.

#### Scenario: The gate builds the sources of another repository
- **WHEN** the gate checks a tree whose Application `devops` names another repository and whose Application `prometheus` has two refs
- **THEN** the gate fetches the other repository once and passes

#### Scenario: A fetch that fails
- **WHEN** git refuses the fetch of the other repository
- **THEN** the gate fails the Application with `The fetch of <repository> at main failed:` and git's error

### Requirement: A kustomization folder renders in place of the Applications
`devops k8s image-pins <folder>` SHALL build the kustomization folder `<folder>`, such as the product base `k8s/devops`, as a path source of an Application builds, and SHALL check and resolve its images with the folder as the name of the Application. It SHALL read no environment tree. A folder holds no `ImageUpdater` object, so the option `--managed <repository>` SHALL name a repository whose tag the deploy sets: the command SHALL NOT refuse or resolve its images, and SHALL name the repository.

#### Scenario: The product base alone
- **WHEN** `devops k8s image-pins k8s/devops` runs, and the registry holds the image of its Deployment
- **THEN** the command exits 0 and names the folder as the Application of the image

#### Scenario: An image whose tag the deploy sets
- **WHEN** the Deployment of the folder names `ghcr.io/example/service` with no tag, and `devops k8s image-pins <folder>` runs once with no option and once with `--managed ghcr.io/example/service`
- **THEN** the first run exits 1, and the second exits 0, sends no request to a registry and names the repository
