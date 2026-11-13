## ADDED Requirements

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
`devops k8s image-pins <folder>` SHALL build the kustomization folder `<folder>`, such as the product base `k8s/devops`, as a path source of an Application builds, and SHALL check and resolve its images with the folder as the name of the Application. It SHALL read no environment tree.

#### Scenario: The product base alone
- **WHEN** `devops k8s image-pins k8s/devops` runs, and the registry holds the image of its Deployment
- **THEN** the command exits 0 and names the folder as the Application of the image

## MODIFIED Requirements

### Requirement: The image pins are the images of the rendered Applications
`devops k8s image-pins` SHALL render each Argo CD Application of the environment tree (`--k8s-dir`, else the profile fact `kubernetes.dir`), a path source with `kubectl kustomize` and a chart source with `helm template --skip-tests` and the value files that its ref sources name, and SHALL take each `image` value of the rendered objects. It SHALL NOT resolve an image whose repository an `ImageUpdater` object names, or an image of a registry that only the cluster or the host reaches.

#### Scenario: A path Application and a chart Application
- **WHEN** a path Application's Deployment runs a Docker Hub image, an image that the chart's `ImageUpdater` names and an image of a `.svc` registry, and the chart renders a StatefulSet with a tab after a value
- **THEN** the pins are the Docker Hub image and the StatefulSet's image, the managed repository is listed apart, the `.svc` image is listed as local, and `helm template` runs with `--skip-tests`

#### Scenario: A chart that does not render
- **WHEN** `helm template` of a chart Application exits 1
- **THEN** the command stops with an `ImagePinError` that names the chart command and gives helm's error

### Requirement: The CI job checks a pull request that changes the pins
The job `image-pins` of `.github/workflows/image-pins.yml` SHALL run `devops k8s image-pins` with read-only permissions and the pinned helm. The workflow SHALL run only for a pull request that changes `k8s/`, the command's modules, the registry module `src/devops_cli/docker/registry.py`, the project file `.devops/project.toml` or the workflow file.

#### Scenario: The job's steps
- **WHEN** `image-pins.yml` is read
- **THEN** its `pull_request` trigger has the paths `k8s/**`, `src/devops_cli/**/image_pins.py`, `src/devops_cli/k8s/app_sources.py`, `src/devops_cli/k8s/environment.py`, `src/devops_cli/docker/registry.py`, `.devops/project.toml` and `.github/workflows/image-pins.yml`, the job has the permission `contents: read`, and its last step runs `uv run devops k8s image-pins`

#### Scenario: A pull request that changes no pin
- **WHEN** a pull request changes only `README.md`
- **THEN** the `paths` filter starts no run of the workflow
