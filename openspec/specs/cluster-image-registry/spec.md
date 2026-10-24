# cluster-image-registry Specification

## Purpose
Where the cluster keeps its internal container images: Gitea's container registry, and no in-cluster Distribution registry that accepts pushes with no authentication.

## Requirements

### Requirement: The manifests deploy no in-cluster Distribution registry
No Kubernetes object that a YAML file under `k8s/` declares SHALL run the Distribution image (Docker Hub's `registry`), be the Namespace `registry`, or be in namespace `registry`. The root kustomization `k8s/` SHALL render none of these objects.

#### Scenario: A manifest under k8s/ runs the Distribution image
- **WHEN** a test reads the image of every container and init container that a Kubernetes object under `k8s/` declares, and resolves each with docker-py
- **THEN** no image resolves to `docker.io/registry` or `docker.io/library/registry`

#### Scenario: A manifest under k8s/ declares the registry namespace
- **WHEN** a test reads every Kubernetes object that a YAML file under `k8s/` declares
- **THEN** no object is the Namespace `registry`, and no object has `metadata.namespace` `registry`

#### Scenario: The root kustomization renders the registry
- **WHEN** a test renders `k8s/` with `kubectl kustomize`
- **THEN** the render holds no Namespace `registry` and no object in namespace `registry`

### Requirement: Gitea's container registry is on
The Gitea values file `k8s/gitea/values.yaml` SHALL turn on Gitea's packages (`gitea.config.packages.ENABLED: true`), which hold the container registry of the cluster.

#### Scenario: A test reads the Gitea values
- **WHEN** a test reads `k8s/gitea/values.yaml`
- **THEN** `gitea.config.packages` is `{"ENABLED": true}`
