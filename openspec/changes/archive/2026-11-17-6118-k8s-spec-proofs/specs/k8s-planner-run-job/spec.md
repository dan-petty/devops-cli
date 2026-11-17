## MODIFIED Requirements

### Requirement: The Role allows get on the CronJob
Role `roadmap-service-jobs` SHALL allow `get` on CronJob `devops-cli-planner-run`.

#### Scenario: The rules of the Role
- **WHEN** a person runs `kubectl auth can-i get cronjob/devops-cli-planner-run -n devops --as=system:serviceaccount:devops:roadmap-service`
- **THEN** the API server answers `yes`

### Requirement: The kustomization and deploy-stack hold the new files
The kustomization of the roadmap Service and `deploy-stack` SHALL list the CronJob and the NetworkPolicy.

#### Scenario: A read of the kustomization
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/devops`
- **THEN** the render holds CronJob `devops-cli-planner-run` and its NetworkPolicy, and the row passes only when `deploy-stack` or an owned exemption applies every NetworkPolicy under `k8s/`
