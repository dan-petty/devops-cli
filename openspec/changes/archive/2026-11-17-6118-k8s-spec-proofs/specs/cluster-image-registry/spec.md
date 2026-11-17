## MODIFIED Requirements

### Requirement: The manifests deploy no in-cluster Distribution registry
No Kubernetes object that a YAML file under `k8s/` declares SHALL run the Distribution image (Docker Hub's `registry`), be the Namespace `registry`, or be in namespace `registry`. The root kustomization `k8s/` SHALL render none of these objects.

#### Scenario: A manifest under k8s/ runs the Distribution image
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row fails when the image of a container or an init container of an object under `k8s/` resolves to `docker.io/registry` or `docker.io/library/registry`

#### Scenario: A manifest under k8s/ declares the registry namespace
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row fails when an object under `k8s/` is the Namespace `registry` or has `metadata.namespace` `registry`

#### Scenario: The root kustomization renders the registry
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/` with `kubectl kustomize`
- **THEN** the row fails when the render holds the Namespace `registry` or an object in namespace `registry`

## REMOVED Requirements

### Requirement: Gitea's container registry is on
**Reason**: Its scenario named a test that reads `k8s/gitea/values.yaml`. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check (#6083).
**Migration**: The requirement "Gitea serves the container registry of the cluster" holds the same rule.

## ADDED Requirements

### Requirement: Gitea serves the container registry of the cluster
The Gitea values file `k8s/gitea/values.yaml` SHALL turn on Gitea's packages (`gitea.config.packages.ENABLED: true`), which hold the container registry of the cluster.

#### Scenario: The registry API answers
- **WHEN** a person runs `kubectl -n gitea port-forward svc/gitea-http 3000:3000` and sends `GET /v2/` to the local port with no credential
- **THEN** Gitea answers 401 with a `WWW-Authenticate` header that names its token route, and not 404
