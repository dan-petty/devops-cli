# command-dry-run-class Specification Delta

## ADDED Requirements

### Requirement: k8s-manifest-request-plans
Sixteen manifest, stack, and kustomize commands (`apply`, `bootstrap`, `bootstrap-openwebui`, `chaos`, `check-deprecated`, `configure-urls`, `create-tls-secret`, `diff-helm`, `enable-tls`, `render`, `sync-secrets`, `teardown-stack`, `validate`, `kustomize apply`, `kustomize build`, and `kustomize diff`) SHALL carry the `request-plan` dry-run class, expose `--dry-run`, make zero external requests during a dry run, and output their planned requests.

#### Scenario: Dry run on k8s apply
- **WHEN** user executes `devops k8s apply manifest.yaml --dry-run`
- **THEN** no manifest is applied to the cluster and the planned kubectl apply request is printed

#### Scenario: Dry run on kustomize build
- **WHEN** user executes `devops kustomize build . --dry-run`
- **THEN** no subprocess or remote base fetch occurs and the planned kustomize build command is printed

#### Scenario: Dry run on k8s teardown-stack
- **WHEN** user executes `devops k8s teardown-stack --stack infra --dry-run`
- **THEN** no resource is deleted from the cluster and the planned deletion requests are printed

### Requirement: k8s-manifest-no-external-request
The two local commands in `k8s` (`k8s lint` and `k8s validate-policy`) SHALL carry the `no-external-request` dry-run class.
Both commands SHALL execute normally without external network or cluster requests under `devops --dry-run`.

#### Scenario: Dry run on local command k8s lint
- **WHEN** user executes `devops --dry-run k8s lint manifests/`
- **THEN** the command runs local manifest linting without external calls

#### Scenario: Dry run on local command k8s validate-policy
- **WHEN** user executes `devops --dry-run k8s validate-policy manifests/`
- **THEN** the command evaluates policies locally without external calls
