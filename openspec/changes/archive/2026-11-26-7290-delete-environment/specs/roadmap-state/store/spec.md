## MODIFIED Requirements

### Requirement: The product base builds valkey-roadmap from the shared Valkey base
The folder `k8s/devops/valkey-roadmap` SHALL build the Valkey base of dan-petty/infra with the components `valkey-persistence`, `valkey-exporter` and `valkey-acl`, each pinned at the same release tag with `?ref=`. The repository SHALL hold no copy of the base and no Deployment of the store. `k8s/devops/kustomization.yaml` SHALL list the folder, and the build SHALL hold a Deployment and a Service with the name `valkey-roadmap` in namespace `devops`.

#### Scenario: The build of the product base
- **WHEN** a person runs `uv run devops ci --check --only k8s`
- **THEN** the row builds `k8s/devops` with the folder `valkey-roadmap`, and passes

#### Scenario: The images of the store resolve
- **WHEN** a person runs `uv run devops k8s image-pins k8s/devops/valkey-roadmap`
- **THEN** the command resolves the image of Valkey and the image of the exporter in their registries, and exits 0
