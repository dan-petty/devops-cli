# command-dry-run-class Specification

## Purpose
Devops-cli commands declare their dry-run behavior so that users and agents know command side effects and run read-only operations safely.

## Requirements

### Requirement: command-declares-dry-run-class
Every command callback in devops-cli SHALL support explicit dry-run classification via the `@dry_run_class` decorator with values `request-plan` or `no-external-request`. A command marked with `request-plan` SHALL declare the `--dry-run` option.

#### Scenario: command declares request-plan class
- **WHEN** a command callback is decorated with `@dry_run_class("request-plan")`
- **THEN** inspecting the callback or Click command reveals the classification attribute `request-plan` and the command exposes `--dry-run`

### Requirement: proxy-runs-no-external-request-commands
When the user executes `devops --dry-run <command>` for a command with the `no-external-request` classification, the lazy proxy SHALL execute the command normally without `--dry-run` if the command does not declare `--dry-run`.

#### Scenario: dry run executes no-external-request command
- **WHEN** the user executes `devops --dry-run <command>` on a command marked `no-external-request`
- **THEN** the command executes without error and prints its normal output

### Requirement: ratchet-prevents-unclassified-commands
Every command path reachable from `_COMMAND_SPECS` SHALL either carry a dry-run classification or be listed in `tests/fixtures/dry_run_gaps.json`. An unclassified command missing from the gap list, or a classified command remaining in the gap list, SHALL fail the ratchet test.

#### Scenario: unclassified command not in gap list fails
- **WHEN** a new command path is added without a dry-run class and without an entry in `dry_run_gaps.json`
- **THEN** the ratchet test fails and identifies the missing command

### Requirement: mcp-read-only-hint-agrees-with-no-external-request
An MCP tool entry in `CONST_MCP_EXPOSURE_TABLE` that delegates to a command marked `no-external-request` SHALL specify `readOnlyHint` as true.

#### Scenario: mcp tool wraps no-external-request command
- **WHEN** an MCP tool definition in `CONST_MCP_EXPOSURE_TABLE` maps to a command path with `no-external-request`
- **THEN** the third element of the table entry is `True`

### Requirement: gh-project-views-pages-request-plans
The ten external-request commands in `gh project`, `gh views`, and `gh pages` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on gh pages build
- **WHEN** user executes `devops gh pages build --dry-run`
- **THEN** no external request is made and the planned build request is printed

#### Scenario: Dry run on gh project sync
- **WHEN** user executes `devops gh project sync --dry-run`
- **THEN** no external request is made and the planned board, field, and view requests are printed

### Requirement: gh-project-views-pages-no-external-request
The five local commands in `gh project`, `gh views`, and `gh pages` SHALL carry the `no-external-request` dry-run class, allowing execution under `devops --dry-run <command>` without external requests.

#### Scenario: Dry run on local command gh views list
- **WHEN** user executes `devops --dry-run gh views list`
- **THEN** the command executes locally and renders the standardized views table

### Requirement: gh-issues-milestones-labels-runs-request-plans
The 16 external-request commands in `gh issues`, `gh labels`, `gh milestones`, `gh runs`, `roadmap run`, and `survey` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on gh issues create
- **WHEN** user executes `devops gh issues create --title "test" --dry-run`
- **THEN** no external request is made and the planned issue create request is printed

#### Scenario: Dry run on gh milestones list
- **WHEN** user executes `devops gh milestones list --dry-run`
- **THEN** no external request is made and the planned milestones listing request is printed

#### Scenario: Dry run on roadmap run
- **WHEN** user executes `devops roadmap run --dry-run`
- **THEN** no external request is made and the planned evaluation requests are printed

#### Scenario: Dry run on survey
- **WHEN** user executes `devops survey --dry-run`
- **THEN** no external request is made and the planned survey requests are printed

### Requirement: gh-api-status-branch-protection-secrets-request-plans
The nine external-request commands in `gh api`, `gh branch-protection audit`, `gh branch-protection sync`, `gh metrics`, `gh rate-limit`, `gh secrets list`, `gh secrets sync`, `gh status`, and `status` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on gh api
- **WHEN** user executes `devops gh api repos/:owner/:repo/issues --dry-run`
- **THEN** no external request is made and the planned api request is printed

#### Scenario: Dry run on gh rate-limit
- **WHEN** user executes `devops gh rate-limit --dry-run`
- **THEN** no external request is made and the planned rate_limit request is printed

#### Scenario: Dry run on gh branch-protection sync
- **WHEN** user executes `devops gh branch-protection sync --dry-run`
- **THEN** no external request is made, no remote branch protection is fetched, and planned protection requests are printed

#### Scenario: Dry run on gh secrets sync
- **WHEN** user executes `devops gh secrets sync -n TOKEN --dry-run`
- **THEN** no external request is made, OS Keyring and Vault are not accessed, and planned secret upload requests are printed

#### Scenario: Dry run on status
- **WHEN** user executes `devops status --dry-run`
- **THEN** no external HTTP request is made and planned statuspage requests are printed

### Requirement: pr-commands-request-plans
The seventeen external-request commands in `pr check-readiness`, `pr checks`, `pr close`, `pr create`, `pr diff`, `pr edit`, `pr hardening-report`, `pr list`, `pr monitor`, `pr ready`, `pr threads list`, `pr threads reply`, `pr threads resolve`, `pr threads resolve-all`, `pr threads unresolve`, `pr view`, and `pr wait` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on pr list
- **WHEN** user executes `devops pr list --dry-run`
- **THEN** no external request is made and the planned pull requests query is printed

#### Scenario: Dry run on pr view
- **WHEN** user executes `devops pr view 123 --dry-run`
- **THEN** no external request is made and the planned pull request view is printed

#### Scenario: Dry run on pr checks
- **WHEN** user executes `devops pr checks 123 --dry-run`
- **THEN** no external request is made and the planned checks query is printed

#### Scenario: Dry run on pr monitor
- **WHEN** user executes `devops pr monitor 123 --dry-run`
- **THEN** no external request is made and the repeated monitoring requests are printed

#### Scenario: Dry run on pr edit
- **WHEN** user executes `devops pr edit 123 --title "new title" --dry-run`
- **THEN** no external request is made and the planned edit request is printed

#### Scenario: Dry run on pr create
- **WHEN** user executes `devops pr create --title "feat: new feature" --dry-run`
- **THEN** no external request is made and the planned draft creation and labeling requests are printed

#### Scenario: Dry run on pr ready
- **WHEN** user executes `devops pr ready 123 --dry-run`
- **THEN** no external request is made and the planned verification and ready conversion requests are printed

#### Scenario: Dry run on pr diff
- **WHEN** user executes `devops pr diff 123 --dry-run`
- **THEN** no external request is made and the planned diff request is printed

#### Scenario: Dry run on pr close
- **WHEN** user executes `devops pr close 123 --dry-run`
- **THEN** no external request is made and the planned close request is printed

#### Scenario: Dry run on pr check-readiness
- **WHEN** user executes `devops pr check-readiness 123 --dry-run`
- **THEN** no external request is made and the planned readiness validation requests are printed

#### Scenario: Dry run on pr hardening-report
- **WHEN** user executes `devops pr hardening-report --pr 123 --dry-run`
- **THEN** no external request is made and the planned audit query is printed

#### Scenario: Dry run on pr threads commands
- **WHEN** user executes `devops pr threads list 123 --dry-run` or `devops pr threads reply tid "reply" --dry-run` or `devops pr threads resolve tid --dry-run` or `devops pr threads unresolve tid --dry-run` or `devops pr threads resolve-all 123 --dry-run`
- **THEN** no external request is made and the planned GraphQL requests are printed

### Requirement: k8s-cluster-request-plans
The eleven external-request commands in `k8s` (`audit`, `contexts`, `logs`, `pods`, `port-forward`, `rbac-audit`, `security-stream`, `service-url`, `status`, `stream-logs`, and `switch-context`) SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on k8s pods
- **WHEN** user executes `devops k8s pods --dry-run`
- **THEN** no external request is made and the planned Kubernetes API list pods request is printed

#### Scenario: Dry run on k8s audit
- **WHEN** user executes `devops k8s audit --dry-run`
- **THEN** no cluster scan is executed and the planned Popeye command is printed

#### Scenario: Dry run on k8s port-forward
- **WHEN** user executes `devops k8s port-forward --dry-run`
- **THEN** no daemon is started and the planned kubectl port-forward commands are printed

### Requirement: k8s-cluster-no-external-request
The three local commands in `k8s` (`gpu-matrix`, `port-forward-status`, and `port-forward-stop`) SHALL carry the `no-external-request` dry-run class.
`k8s gpu-matrix` and `k8s port-forward-status` SHALL execute normally without external requests under `devops --dry-run`.
`k8s port-forward-stop` SHALL accept `--dry-run` and print how many daemons it would stop without terminating any process.

#### Scenario: Dry run on local command k8s gpu-matrix
- **WHEN** user executes `devops --dry-run k8s gpu-matrix`
- **THEN** the command runs normally and prints the local GPU matrix

#### Scenario: Dry run on k8s port-forward-stop
- **WHEN** user executes `devops k8s port-forward-stop --dry-run`
- **THEN** no process receives a termination signal and the preview output describes the action

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
