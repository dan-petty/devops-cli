# command-dry-run-class Specification Delta

## ADDED Requirements

### Requirement: argo-request-plans
Twenty external-request commands in `argo` SHALL carry the `request-plan` dry-run class.
Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.
For Argo CD HTTP operations, the plan SHALL list the token request before the target action request.
When `--format json` or `--json` is supplied, the command SHALL return its real result type marked as a dry run.

#### Scenario: Dry run on argo cd apps list
- **WHEN** user executes `devops argo cd apps list --dry-run`
- **THEN** no network request is sent to Argo CD and the planned token request and applications request are printed

#### Scenario: Dry run on argo rollouts abort
- **WHEN** user executes `devops argo rollouts abort my-rollout --dry-run`
- **THEN** no resource is patched on Kubernetes and the planned Rollout abort patch request is printed

#### Scenario: Dry run on argo workflows submit
- **WHEN** user executes `devops argo workflows submit workflow.yaml --dry-run`
- **THEN** no workflow resource is created in the cluster and the planned submission request is printed

### Requirement: argo-no-external-request
The two local GitOps commands (`argo cd gitops drift` and `argo gitops drift`) SHALL carry the `no-external-request` dry-run class.
Both commands SHALL execute normally without external network or cluster requests under `devops --dry-run`.

#### Scenario: Dry run on argo cd gitops drift
- **WHEN** user executes `devops --dry-run argo cd gitops drift`
- **THEN** the command inspects local manifest files against git without external network or cluster requests
