## MODIFIED Requirements

### Requirement: The deploy stack and the kustomizations list every file
Every file of `k8s/devops/searxng/` SHALL be in its `kustomization.yaml`, in `k8s/devops/kustomization.yaml` as the folder, and in `MANIFESTS_BY_STACK["devops"]`.

#### Scenario: A file is in one list only
- **WHEN** `uv run devops ci --check --only k8s` renders Application `devops`, and `uv run devops k8s deploy-stack --stack devops --dry-run` lists its manifests
- **THEN** the render and the list of the dry run each hold every file of `k8s/devops/searxng/`
