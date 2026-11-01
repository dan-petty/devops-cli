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

### Requirement: ai-model-gateway-request-plans
Sixteen external-request commands in `ai` and `ai gateway` SHALL carry the `request-plan` dry-run class.
Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.
When `--format json` or `--json` is supplied, the command SHALL return its real result type marked as a dry run.

#### Scenario: Dry run on ai models
- **WHEN** user executes `devops ai models --dry-run`
- **THEN** no network request is sent to the LLM provider and the planned models request is printed

#### Scenario: Dry run on ai gateway status
- **WHEN** user executes `devops ai gateway status --dry-run`
- **THEN** no network probe is sent to the gateway and the planned health and routes requests are printed

#### Scenario: Dry run on ai test
- **WHEN** user executes `devops ai test --dry-run`
- **THEN** no inference request is sent and the planned test prompt request is printed

### Requirement: ai-gateway-no-external-request
The local gateway commands `ai gateway failover` and `ai gateway render` SHALL carry the `no-external-request` dry-run class.
Both commands SHALL execute locally without external network or cluster requests under `devops --dry-run`.
`ai gateway failover` with `--dry-run` SHALL print the change and write nothing.

#### Scenario: Dry run on ai gateway render
- **WHEN** user executes `devops --dry-run ai gateway render`
- **THEN** the command renders gateway configuration locally without external network or cluster requests

#### Scenario: Dry run on ai gateway failover
- **WHEN** user executes `devops ai gateway failover devops-default --dry-run`
- **THEN** the failover preview is printed and no state file is modified

### Requirement: ai-rag-ingest-analyze-research-request-plans
Sixteen external-request commands in `ai analyze`, `ai ingest`, `ai rag`, and `ai research` SHALL carry the `request-plan` dry-run class.
Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.
When `--format json` or `--json` is supplied, the command SHALL return its real result type marked as a dry run.

#### Scenario: Dry run on ai analyze branch
- **WHEN** user executes `devops ai analyze branch --dry-run`
- **THEN** no remote Git or embedding calls are made and planned embedding requests are printed

#### Scenario: Dry run on ai ingest docs
- **WHEN** user executes `devops ai ingest docs https://example.com/docs --dry-run`
- **THEN** no remote HTTP fetch is executed and planned documentation ingest requests are printed

#### Scenario: Dry run on ai rag query
- **WHEN** user executes `devops ai rag query "database migrations" --dry-run`
- **THEN** no Valkey cache or Qdrant vector database request is sent and planned retrieval requests are printed

#### Scenario: Dry run on ai research model
- **WHEN** user executes `devops ai research model "qwen2.5-coder" --dry-run`
- **THEN** no outbound HTTP request is dispatched and planned model research requests are printed

### Requirement: ai-rag-ingest-analyze-research-no-external-request
The five local AI commands (`ai analyze`, `ai ingest library`, `ai rag`, `ai research annotate`, and `ai research forage`) SHALL carry the `no-external-request` dry-run class.
Each command SHALL execute locally without external network or cluster requests under `devops --dry-run`.

#### Scenario: Dry run on ai analyze group
- **WHEN** user executes `devops --dry-run ai analyze`
- **THEN** the command renders help or local analysis explanation without external requests

#### Scenario: Dry run on ai ingest library
- **WHEN** user executes `devops --dry-run ai ingest library devops_cli`
- **THEN** the command inspects local symbols without network or external database calls

#### Scenario: Dry run on ai research annotate
- **WHEN** user executes `devops --dry-run ai research annotate report.md`
- **THEN** the command processes the local markdown file without external requests

### Requirement: ai-runs-cost-update-request-plans
Eight external-request commands in `ai cost update-pricing`, `ai runs baseline set`, `ai runs baseline show`, `ai runs check`, `ai runs compare`, `ai runs connect`, `ai runs reindex`, and `ai runs show` SHALL carry the `request-plan` dry-run class.
Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.
When `--format json` or `--json` is supplied, the command SHALL return its real result type marked as a dry run.

#### Scenario: Dry run on ai cost update-pricing
- **WHEN** user executes `devops ai cost update-pricing --dry-run`
- **THEN** no outbound HTTP pricing request is dispatched and planned pricing synchronization requests are printed

#### Scenario: Dry run on ai runs reindex
- **WHEN** user executes `devops ai runs reindex --dry-run`
- **THEN** no Valkey connection or write is performed and planned index pipeline requests are printed

#### Scenario: Dry run on ai runs connect
- **WHEN** user executes `devops ai runs connect --dry-run`
- **THEN** no Kubernetes API or Valkey cluster requests are executed and planned connect requests are printed

### Requirement: ai-cost-local-preview
Two mutating local commands (`ai cost reset` and `ai cost set-price`) SHALL expose `--dry-run` and carry the `no-external-request` dry-run class.
Under `--dry-run`, each command SHALL print the planned state modification and write nothing.

#### Scenario: Dry run on ai cost reset
- **WHEN** user executes `devops ai cost reset --dry-run`
- **THEN** the reset preview is printed and no spend ledger records are cleared

#### Scenario: Dry run on ai cost set-price
- **WHEN** user executes `devops ai cost set-price gpt-4o 2.50 10.00 --dry-run`
- **THEN** the configured price preview is printed and custom pricing is not persisted

### Requirement: ai-runs-cost-cache-no-external-request
The eleven local AI commands (`ai cache clear`, `ai cache status`, `ai cost`, `ai cost list-pricing`, `ai cost payback`, `ai cost payoff`, `ai cost prometheus`, `ai cost report`, `ai cost roi`, `ai runs baseline list`, and `ai runs list`) SHALL carry the `no-external-request` dry-run class.
Each command SHALL execute locally without external network or cluster requests under `devops --dry-run`.

#### Scenario: Dry run on ai cache clear
- **WHEN** user executes `devops --dry-run ai cache clear`
- **THEN** the command clears cache entries locally without echo-only preview shim

#### Scenario: Dry run on ai cost report
- **WHEN** user executes `devops --dry-run ai cost report`
- **THEN** the command generates the spend report from local data without external requests

### Requirement: local-ai-tools-no-external-request
The ten local AI inspection commands (`ai`, `ai ast graph`, `ai ast parse`, `ai audit-library-usage`, `ai bundle-models`, `ai config`, `ai diagram`, `ai pack-context`, `ai read`, and `ai repomap`) SHALL carry the `no-external-request` dry-run class. Under `devops --dry-run`, each command SHALL execute locally without external requests.

#### Scenario: Dry run on ai ast parse
- **WHEN** user executes `devops --dry-run ai ast parse <file>`
- **THEN** the command parses AST symbols locally without echo-only preview

### Requirement: local-ai-controller-harness-no-external-request
The ten local AI controller, harness, and evaluation commands (`ai constellation`, `ai failover`, `ai harness offload`, `ai harness run`, `ai harness status`, `ai quiesce`, `ai resume`, `ai spec`, `ai test-gen`, and `ai token-count`) SHALL carry the `no-external-request` dry-run class. Under `devops --dry-run`, each command SHALL execute locally without external requests.

#### Scenario: Dry run on ai quiesce
- **WHEN** user executes `devops --dry-run ai quiesce`
- **THEN** the command reports the quiesce preview without modifying the snapshot file

### Requirement: review-request-plans
Twelve external-request commands in `review` SHALL carry the `request-plan` dry-run class: `review benchmark`, `review branch`, `review corpus generate`, `review corpus score`, `review intake`, `review path`, `review pr`, `review samples fetch`, `review samples validate`, `review score`, `review templates check`, and `review templates sweep`. Under dry run, each command SHALL make zero external requests and output its planned requests.

#### Scenario: Dry run on review path
- **WHEN** user executes `devops review path src/ --dry-run`
- **THEN** the command prints planned LLM review requests and makes zero external calls

#### Scenario: Dry run on review samples fetch
- **WHEN** user executes `devops review samples fetch --dry-run`
- **THEN** the command prints planned git clone and fetch requests and makes zero network calls

### Requirement: review-no-external-request
Eight local review commands SHALL carry the `no-external-request` dry-run class: `review`, `review export-feedback`, `review findings`, `review rules test`, `review samples list`, `review stats`, `review templates list`, and `review verify`. Under `devops --dry-run`, each command SHALL execute locally without external requests. Mutating command `review export-feedback` with `--dry-run` SHALL print its planned export and write nothing.

#### Scenario: Dry run on review export-feedback
- **WHEN** user executes `devops review export-feedback --dry-run`
- **THEN** the command prints planned feedback export details and writes no file

#### Scenario: Dry run on review stats
- **WHEN** user executes `devops --dry-run review stats`
- **THEN** the command renders local review session statistics without external requests

### Requirement: tf-request-plans
Nine external-request commands in `tf` SHALL carry the `request-plan` dry-run class: `tf init`, `tf plan`, `tf apply`, `tf destroy`, `tf output`, `tf deploy-cloud`, `tf lint`, `tf cost breakdown`, and `tf cost diff`.
Under dry run, each command SHALL make zero external requests, execute zero subprocesses, and output its planned requests.

#### Scenario: Dry run on tf init
- **WHEN** user executes `devops tf init --dry-run`
- **THEN** the command prints planned init execution requests and starts no process

#### Scenario: Dry run on tf plan
- **WHEN** user executes `devops tf plan --dry-run`
- **THEN** the command prints planned plan execution requests and starts no process

#### Scenario: Dry run on tf apply
- **WHEN** user executes `devops tf apply --dry-run`
- **THEN** the command prints planned apply execution requests and starts no process

#### Scenario: Dry run on tf cost breakdown
- **WHEN** user executes `devops tf cost breakdown --dry-run`
- **THEN** the command prints planned Infracost execution requests and starts no process

### Requirement: tf-no-external-request
Six local OpenTofu commands SHALL carry the `no-external-request` dry-run class: `tf drift`, `tf fmt`, `tf graph`, `tf notify-plan`, `tf status`, and `tf validate`.
Under `devops --dry-run`, each command SHALL execute locally without external requests.
Echo-only previews and explicit `--dry-run` options SHALL be removed from read-only commands without a shim.

#### Scenario: Dry run on tf status
- **WHEN** user executes `devops --dry-run tf status`
- **THEN** the command renders local status information without external requests

#### Scenario: Dry run on tf graph
- **WHEN** user executes `devops --dry-run tf graph`
- **THEN** the command renders local dependency graph data without echo-only preview

### Requirement: scan-request-plans
Five commands in `scan` SHALL carry the `request-plan` dry-run class: `scan` (callback), `scan trivy`, `scan fix`, `scan report`, and `scan sast`.
Under dry run, each command SHALL make zero external requests, execute zero subprocesses, and output its planned requests.

#### Scenario: Dry run on scan trivy
- **WHEN** user executes `devops scan trivy --dry-run`
- **THEN** the command prints planned Trivy scan requests and starts no process

#### Scenario: Dry run on scan sast
- **WHEN** user executes `devops scan sast --dry-run`
- **THEN** the command prints planned Semgrep scan requests and starts no process

#### Scenario: Dry run on scan report
- **WHEN** user executes `devops scan report --dry-run`
- **THEN** the command prints planned scanner suite requests and starts no process

#### Scenario: Dry run on scan fix
- **WHEN** user executes `devops scan fix --dry-run`
- **THEN** the command prints planned OSV query and remediation requests and starts no process

### Requirement: scan-no-external-request
Seven local scan commands SHALL carry the `no-external-request` dry-run class: `scan aibom`, `scan complexity`, `scan injection`, `scan sarif`, `scan sbom`, `scan secrets`, and `scan workflows`.
Under `devops --dry-run`, each command SHALL execute locally without external network requests.
Echo-only previews and explicit `--dry-run` options SHALL be removed from read-only commands without a shim.

#### Scenario: Dry run on scan complexity
- **WHEN** user executes `devops --dry-run scan complexity`
- **THEN** the command renders local complexity analysis without echo-only preview

#### Scenario: Dry run on scan workflows
- **WHEN** user executes `devops --dry-run scan workflows`
- **THEN** the command executes local workflow audit without external requests

### Requirement: docker-request-plans
Nine commands in `docker` SHALL carry the `request-plan` dry-run class: `docker build`, `docker cache`, `docker images`, `docker prune`, `docker push`, `docker sandbox`, `docker sign`, `docker stats`, and `docker verify`.
Under dry run, each command SHALL make zero external requests, execute zero daemon socket calls, invoke zero subprocesses, and output its planned requests.

#### Scenario: Dry run on docker images
- **WHEN** user executes `devops docker images --dry-run`
- **THEN** the command prints planned Docker engine image listing requests and makes zero daemon calls

#### Scenario: Dry run on docker build
- **WHEN** user executes `devops docker build . -t test:latest --dry-run`
- **THEN** the command prints planned Docker engine build requests and makes zero daemon calls

#### Scenario: Dry run on docker sign
- **WHEN** user executes `devops docker sign test:latest --key cosign.key --dry-run`
- **THEN** the command prints planned cosign sign requests and executes zero subprocesses

#### Scenario: Dry run on docker verify
- **WHEN** user executes `devops docker verify test:latest --key cosign.pub --dry-run`
- **THEN** the command prints planned cosign verify requests and executes zero subprocesses

### Requirement: sandbox-request-plans
Nine commands in `sandbox` SHALL carry the `request-plan` dry-run class: `sandbox deploy`, `sandbox exec`, `sandbox logs`, `sandbox metrics`, `sandbox network-policy`, `sandbox probe`, `sandbox status`, `sandbox stop`, and `sandbox traces`.
Under dry run, each command SHALL make zero external requests, execute zero daemon socket calls, perform zero HTTP or DNS requests, and output its planned requests.

#### Scenario: Dry run on sandbox deploy
- **WHEN** user executes `devops sandbox deploy --dry-run`
- **THEN** the command prints planned container creation and start requests and makes zero engine calls

#### Scenario: Dry run on sandbox exec
- **WHEN** user executes `devops sandbox exec ls --dry-run`
- **THEN** the command prints planned exec requests and makes zero engine calls

#### Scenario: Dry run on sandbox probe
- **WHEN** user executes `devops sandbox probe --dry-run`
- **THEN** the command prints planned HTTP health probe requests and makes zero network calls

#### Scenario: Dry run on sandbox metrics
- **WHEN** user executes `devops sandbox metrics --dry-run`
- **THEN** the command prints planned Prometheus metrics endpoint requests and makes zero network calls

### Requirement: cloudflare-request-plans
Ten commands in `cloudflare` SHALL carry the `request-plan` dry-run class:
`cloudflare status`, `cloudflare service-status`, `cloudflare dns list`, `cloudflare dns sync`, `cloudflare dns delete`, `cloudflare tunnel routes`, `cloudflare tunnel sync`, `cloudflare access status`, `cloudflare access sync`, and `cloudflare access policies`.
Under dry run, each command SHALL make zero external HTTP requests, open zero sockets, and output its planned requests.

#### Scenario: Dry run on cloudflare status
- **WHEN** user executes `devops cloudflare status --dry-run`
- **THEN** the command prints planned token verification and zone details requests and makes zero external calls

#### Scenario: Dry run on cloudflare service-status
- **WHEN** user executes `devops cloudflare service-status --dry-run`
- **THEN** the command prints planned statuspage summary requests and makes zero external calls

#### Scenario: Dry run on cloudflare dns list
- **WHEN** user executes `devops cloudflare dns list --dry-run`
- **THEN** the command prints planned DNS record listing requests and makes zero external calls

#### Scenario: Dry run on cloudflare dns sync
- **WHEN** user executes `devops cloudflare dns sync --dry-run`
- **THEN** the command prints planned DNS record reconciliation requests and makes zero external calls

#### Scenario: Dry run on cloudflare dns delete
- **WHEN** user executes `devops cloudflare dns delete example.com --dry-run`
- **THEN** the command prints planned DNS record deletion requests and makes zero external calls

#### Scenario: Dry run on cloudflare tunnel routes
- **WHEN** user executes `devops cloudflare tunnel routes --dry-run`
- **THEN** the command prints planned tunnel configuration retrieval requests and makes zero external calls

#### Scenario: Dry run on cloudflare tunnel sync
- **WHEN** user executes `devops cloudflare tunnel sync --dry-run`
- **THEN** the command prints planned tunnel configuration update requests and makes zero external calls

#### Scenario: Dry run on cloudflare access status
- **WHEN** user executes `devops cloudflare access status --dry-run`
- **THEN** the command prints planned Access application listing requests and makes zero external calls

#### Scenario: Dry run on cloudflare access sync
- **WHEN** user executes `devops cloudflare access sync --domain example.com --allowed-emails user@example.com --dry-run`
- **THEN** the command prints planned Access application and policy configuration requests and makes zero external calls

#### Scenario: Dry run on cloudflare access policies
- **WHEN** user executes `devops cloudflare access policies app-123 --dry-run`
- **THEN** the command prints planned Access policy retrieval requests and makes zero external calls

### Requirement: valkey-request-plans
Nine commands in `valkey` SHALL carry the `request-plan` dry-run class:
`valkey backup`, `valkey cli`, `valkey flush`, `valkey get`, `valkey info`, `valkey keys`, `valkey ping`, `valkey set`, and `valkey stats`.
Under dry run, each command SHALL make zero external network requests, open zero sockets, and output its planned requests.

#### Scenario: Dry run on valkey ping
- **WHEN** user executes `devops valkey ping --dry-run`
- **THEN** the command prints planned PING request and makes zero external calls

#### Scenario: Dry run on valkey info
- **WHEN** user executes `devops valkey info --dry-run`
- **THEN** the command prints planned INFO request and makes zero external calls

#### Scenario: Dry run on valkey stats
- **WHEN** user executes `devops valkey stats --dry-run`
- **THEN** the command prints planned INFO and DBSIZE requests and makes zero external calls

#### Scenario: Dry run on valkey keys
- **WHEN** user executes `devops valkey keys --dry-run`
- **THEN** the command prints planned KEYS request and makes zero external calls

#### Scenario: Dry run on valkey get
- **WHEN** user executes `devops valkey get mykey --dry-run`
- **THEN** the command prints planned GET request and makes zero external calls

#### Scenario: Dry run on valkey set
- **WHEN** user executes `devops valkey set mykey myval --dry-run`
- **THEN** the command prints planned SET request with placeholder and makes zero external calls

#### Scenario: Dry run on valkey flush
- **WHEN** user executes `devops valkey flush --dry-run`
- **THEN** the command prints planned FLUSHDB request and makes zero external calls

#### Scenario: Dry run on valkey backup
- **WHEN** user executes `devops valkey backup --dry-run`
- **THEN** the command prints planned BGSAVE request and makes zero external calls

#### Scenario: Dry run on valkey cli
- **WHEN** user executes `devops valkey cli ping --dry-run`
- **THEN** the command prints planned CLI execution request and makes zero external calls

### Requirement: vault-request-plans
Seven commands in `vault` SHALL carry the `request-plan` dry-run class:
`vault get`, `vault leases`, `vault login`, `vault logout`, `vault set`, `vault status`, and `vault sync`.
Under dry run, each command SHALL make zero external HTTP requests, open zero sockets, and output its planned requests.

#### Scenario: Dry run on vault status
- **WHEN** user executes `devops vault status --dry-run`
- **THEN** the command prints planned sys/health request and makes zero external calls

#### Scenario: Dry run on vault get
- **WHEN** user executes `devops vault get secret/data/app --dry-run`
- **THEN** the command prints planned secret retrieval request and makes zero external calls

#### Scenario: Dry run on vault set
- **WHEN** user executes `devops vault set secret/data/app KEY=VAL --dry-run`
- **THEN** the command prints planned secret storage request with placeholders and makes zero external calls

#### Scenario: Dry run on vault sync
- **WHEN** user executes `devops vault sync secret/data/app --dry-run`
- **THEN** the command prints planned secret synchronization request and makes zero external calls

#### Scenario: Dry run on vault login
- **WHEN** user executes `devops vault login --method approle --role-id r --secret-id s --dry-run`
- **THEN** the command prints planned authentication request with placeholders and makes zero external calls

#### Scenario: Dry run on vault logout
- **WHEN** user executes `devops vault logout --dry-run`
- **THEN** the command prints planned token revocation request and makes zero external calls

#### Scenario: Dry run on vault leases
- **WHEN** user executes `devops vault leases --revoke lease-1 --dry-run`
- **THEN** the command prints planned lease revocation request and makes zero external calls

### Requirement: vault-no-external-request
The `vault audit` command SHALL carry the `no-external-request` dry-run class. Under dry run, the command executes normally and inspects in-process audit records.

#### Scenario: Dry run on vault audit
- **WHEN** user executes `devops --dry-run vault audit`
- **THEN** the command executes without error and prints session credential access audit records

### Requirement: dashboard-request-plans
The `dashboard` command SHALL carry the `request-plan` dry-run class. Under dry run, the command makes zero external requests and returns an ordered plan of planned status inspection queries across Kubernetes, Docker, Telemetry, AI, and Valkey.

#### Scenario: Dry run on dashboard
- **WHEN** user executes `devops dashboard --dry-run`
- **THEN** no external requests are made and the planned status queries are printed

### Requirement: grafana-request-plans
Seven commands in `grafana` SHALL carry the `request-plan` dry-run class:
`grafana alerts`, `grafana dashboards export`, `grafana dashboards import`, `grafana dashboards list`, `grafana dashboards sync`, `grafana datasources`, and `grafana search`.
Under dry run, each command makes zero HTTP or network requests and outputs its planned requests.

#### Scenario: Dry run on grafana alerts
- **WHEN** user executes `devops grafana alerts --dry-run`
- **THEN** no external request is made and the planned alert rules query is printed

#### Scenario: Dry run on grafana dashboards list
- **WHEN** user executes `devops grafana dashboards list --dry-run`
- **THEN** no external request is made and the planned dashboard search request is printed

#### Scenario: Dry run on grafana datasources
- **WHEN** user executes `devops grafana datasources --dry-run`
- **THEN** no external request is made and the planned datasources query is printed

### Requirement: grafana-no-external-request
The `grafana dashboards lint` command SHALL carry the `no-external-request` dry-run class. Under dry run, the command executes normally and inspects local JSON files.

#### Scenario: Dry run on grafana dashboards lint
- **WHEN** user executes `devops --dry-run grafana dashboards lint tests/fixtures/`
- **THEN** the command executes locally and lints dashboard files without making external requests

### Requirement: prometheus-request-plans
Five commands in `prometheus` SHALL carry the `request-plan` dry-run class:
`prometheus analyze`, `prometheus query`, `prometheus query-range`, `prometheus rules`, and `prometheus targets`.
Under dry run, each command makes zero HTTP or network requests and outputs its planned requests.

#### Scenario: Dry run on prometheus query
- **WHEN** user executes `devops prometheus query "up" --dry-run`
- **THEN** no external request is made and the planned PromQL query request is printed

#### Scenario: Dry run on prometheus rules
- **WHEN** user executes `devops prometheus rules --dry-run`
- **THEN** no external request is made and the planned rules request is printed

#### Scenario: Dry run on prometheus targets
- **WHEN** user executes `devops prometheus targets --dry-run`
- **THEN** no external request is made and the planned targets request is printed

### Requirement: telemetry-request-plans
Five commands in `telemetry` SHALL carry the `request-plan` dry-run class:
`telemetry connect`, `telemetry profile`, `telemetry semconv refresh`, `telemetry status`, and `telemetry test`.
Under dry run, each command makes zero external requests or subprocess calls and outputs its planned requests.

#### Scenario: Dry run on telemetry status
- **WHEN** user executes `devops telemetry status --dry-run`
- **THEN** no external request is made and the planned collector connection test is printed

#### Scenario: Dry run on telemetry test
- **WHEN** user executes `devops telemetry test --dry-run`
- **THEN** no external request is made and the planned test trace export is printed

#### Scenario: Dry run on telemetry semconv refresh
- **WHEN** user executes `devops telemetry semconv refresh --commit main --dry-run`
- **THEN** no external request is made and the planned weaver command is printed

### Requirement: telemetry-no-external-request
Two commands in `telemetry` SHALL carry the `no-external-request` dry-run class:
`telemetry logfire` and `telemetry open-ui`. Under dry run, each command executes normally without making external requests.

#### Scenario: Dry run on telemetry logfire
- **WHEN** user executes `devops --dry-run telemetry logfire`
- **THEN** the command executes locally and displays logfire bridge status

#### Scenario: Dry run on telemetry open-ui
- **WHEN** user executes `devops --dry-run telemetry open-ui`
- **THEN** the command executes locally and displays the tempo URL

### Requirement: config-request-plans
The `config init` command SHALL carry the `request-plan` dry-run class. Under dry run, it executes zero subprocesses and renders the planned external requests.

#### Scenario: Dry run on config init
- **WHEN** user executes `devops config init --dry-run`
- **THEN** zero subprocesses execute and the planned `gh auth status` command is printed

#### Scenario: JSON dry run on config init
- **WHEN** user executes `devops config init --dry-run --json`
- **THEN** structured JSON with `dry_run: true` and the list of planned requests is printed

### Requirement: config-no-external-request
The ten commands `config audit-keys`, `config audit-stream`, `config auth-headless`, `config env`, `config env-vars`, `config get`, `config output`, `config set`, `config show`, and `config unset` SHALL carry the `no-external-request` dry-run class. `config set` SHALL provide a local preview under `--dry-run` without modifying settings or OS keyring.

#### Scenario: Dry run on config set
- **WHEN** user executes `devops config set test.key test-value --dry-run`
- **THEN** a preview line is printed and no configuration or keyring writes occur

#### Scenario: Dry run on config show
- **WHEN** user executes `devops --dry-run config show`
- **THEN** the command executes locally and renders settings without external requests

### Requirement: workspace-no-external-request
The five commands `workspace add`, `workspace clean`, `workspace generate`, `workspace open`, and `workspace remove` SHALL carry the `no-external-request` dry-run class. `workspace add`, `workspace generate`, and `workspace remove` SHALL provide local previews under `--dry-run` without modifying workspace files.

#### Scenario: Dry run on workspace add
- **WHEN** user executes `devops workspace add . --dry-run`
- **THEN** a preview line is printed and the workspace file is not modified

### Requirement: openspec-no-external-request
The three commands `openspec archive`, `openspec check`, and `openspec regenerate` SHALL carry the `no-external-request` dry-run class, running locally without external requests.

#### Scenario: Dry run on openspec check
- **WHEN** user executes `devops --dry-run openspec check`
- **THEN** the local OpenSpec gate runs and reports findings

### Requirement: docs-no-external-request
The three commands `docs check`, `docs generate`, and `docs sync-readme` SHALL carry the `no-external-request` dry-run class, running locally without external requests.

#### Scenario: Dry run on docs check
- **WHEN** user executes `devops --dry-run docs check`
- **THEN** documentation checks execute locally without external requests

### Requirement: devcontainer-request-plans
The five commands `devcontainer bootstrap-k8s`, `devcontainer post-create`, `devcontainer post-start`, `devcontainer run-lifecycle`, and `devcontainer unlock-keyring` SHALL carry the `request-plan` dry-run class. Under dry run, they execute zero subprocesses or network requests and render the planned requests.

#### Scenario: Dry run on devcontainer bootstrap-k8s
- **WHEN** user executes `devops devcontainer bootstrap-k8s --dry-run`
- **THEN** zero subprocesses execute and planned Minikube commands are printed

#### Scenario: Dry run on devcontainer post-create
- **WHEN** user executes `devops devcontainer post-create --dry-run`
- **THEN** zero network or installation subprocesses execute and planned tool installation requests are printed

#### Scenario: Dry run on devcontainer post-start
- **WHEN** user executes `devops devcontainer post-start --dry-run`
- **THEN** zero subprocesses execute and planned git and kubectl requests are printed

#### Scenario: Dry run on devcontainer run-lifecycle
- **WHEN** user executes `devops devcontainer run-lifecycle --dry-run`
- **THEN** zero lifecycle actions execute and planned lifecycle requests are printed

#### Scenario: Dry run on devcontainer unlock-keyring
- **WHEN** user executes `devops devcontainer unlock-keyring --dry-run`
- **THEN** zero subprocesses execute and planned gnome-keyring and gh auth commands are printed

### Requirement: install-tools-request-plans
The `install-tools` command SHALL carry the `request-plan` dry-run class. Under dry run, it executes zero downloads or installer subprocesses and renders the planned requests.

#### Scenario: Dry run on install-tools
- **WHEN** user executes `devops install-tools --dry-run`
- **THEN** zero HTTP requests or installer subprocesses execute and planned downloads are printed

### Requirement: devcontainer-no-external-request
The four commands `devcontainer init`, `devcontainer update`, `devcontainer list`, and `devcontainer validate` SHALL carry the `no-external-request` dry-run class. `devcontainer init` and `devcontainer update` SHALL provide local previews under `--dry-run` without modifying filesystem paths.

#### Scenario: Dry run on devcontainer init
- **WHEN** user executes `devops devcontainer init --dry-run`
- **THEN** a preview line is printed and no configuration files are created

#### Scenario: Dry run on devcontainer update
- **WHEN** user executes `devops devcontainer update --dry-run`
- **THEN** a preview line is printed and `devcontainer.json` is not modified

#### Scenario: Dry run on devcontainer list
- **WHEN** user executes `devops --dry-run devcontainer list`
- **THEN** the command executes locally and renders the devcontainer list

#### Scenario: Dry run on devcontainer validate
- **WHEN** user executes `devops --dry-run devcontainer validate`
- **THEN** the command executes locally and validates the manifest syntax

### Requirement: install-tools-no-external-request
The `install-tools status` command SHALL carry the `no-external-request` dry-run class, running locally without external requests.

#### Scenario: Dry run on install-tools status
- **WHEN** user executes `devops --dry-run install-tools status`
- **THEN** the status check executes locally without external requests

### Requirement: git-workspace-request-plans
The seven commands `branches sync`, `branches update`, `repos clone`, `repos clone-org`, `repos sync`, `repos update` and `repos worktrees prune` SHALL carry the `request-plan` dry-run class and SHALL expose `--dry-run`, in the forms `devops <command> --dry-run` and `devops --dry-run <command>`. A dry run SHALL make no external request and SHALL print the requests of the real run, numbered, in the order of the real run.

#### Scenario: Dry run on branches sync
- **WHEN** user executes `devops branches sync --dry-run` for a workspace with one repository whose remote is `origin` and whose current branch tracks `origin`
- **THEN** no `git fetch` and no `git pull` runs, and the output lists `git -C <repo> fetch --prune origin` and then `git -C <repo> pull origin <branch>`

#### Scenario: A dry run refuses what a run refuses
- **WHEN** user executes `devops repos clone --dry-run -- -bad` or `devops --dry-run repos clone -- -bad`
- **THEN** the command exits with status 1, reports `Invalid repository URL: must not start with a hyphen.` and lists no request

#### Scenario: Dry run on repos update through the root flag
- **WHEN** user executes `devops --dry-run repos update --no-pull`
- **THEN** no git command that changes state runs, the output lists one `git fetch --prune` for each remote of each repository and no `git pull`, and the last line is the `code --reuse-window` command that reloads the workspace

#### Scenario: Dry run on repos clone
- **WHEN** user executes `devops repos clone https://github.com/example-org/app.git --dry-run`
- **THEN** nothing is cloned, `known_hosts` is not changed, and the output lists `git clone -- https://github.com/example-org/app.git <base-dir>/example-org/app` and then the `code --reuse-window` command

#### Scenario: Dry run on repos clone-org
- **WHEN** user executes `devops repos clone-org example-org --dry-run`
- **THEN** GitHub receives no request, and the output lists the listing request `GET /orgs/example-org/repos`, the fallback listing for the own account with its condition, and a `git clone` for each listed repository with the repeat `for each listed repository`

#### Scenario: Dry run on repos worktrees prune
- **WHEN** user executes `devops repos worktrees prune --dry-run`
- **THEN** GitHub receives no request, and the output lists `GET /repos/<repo>/commits/<sha>/pulls` for each worktree that local state does not decide

#### Scenario: The plan matches the real run
- **WHEN** a test runs `devops repos sync` on a `git_fake` that answers the local reads, and compares the git commands that are not local reads with the plan of `devops repos sync --dry-run`
- **THEN** the commands and the plan lines are the same, in the same order

### Requirement: git-workspace-no-external-request
The five commands `branches clean`, `branches jira`, `branches list`, `repos list` and `repos worktrees status` SHALL carry the `no-external-request` dry-run class. `branches list`, `repos list` and `repos worktrees status` SHALL run normally under `devops --dry-run` and have no `--dry-run` option. `branches clean` and `branches jira` SHALL preview under `--dry-run` and change nothing.

#### Scenario: Dry run on branches list
- **WHEN** user executes `devops --dry-run branches list --base-dir <dir>`
- **THEN** the command lists the branches of each repository and starts only git commands that read

#### Scenario: Dry run on repos list
- **WHEN** user executes `devops --dry-run repos list`
- **THEN** the command lists the cloned repositories and prints no JSON preview

#### Scenario: repos list has no dry-run option
- **WHEN** user executes `devops repos list --dry-run`
- **THEN** the command exits with status 2 and reports `No such option: --dry-run`

#### Scenario: Dry run on repos worktrees status
- **WHEN** user executes `devops --dry-run repos worktrees status`
- **THEN** the command lists the worktrees and starts only git commands that read

#### Scenario: Dry run on branches clean
- **WHEN** user executes `devops --dry-run branches clean --base-dir <dir>` for a repository with a merged branch
- **THEN** the output says that it would delete the branch and no branch is deleted

#### Scenario: Dry run on branches jira with a bad ticket
- **WHEN** user executes `devops branches jira bad --dry-run`
- **THEN** the command exits with status 1, as a run does

#### Scenario: Dry run on branches jira
- **WHEN** user executes `devops --dry-run branches jira PROJ-1 --repo <repo>`
- **THEN** the output says that it would create the branch `feature/PROJ-1` and no `git checkout` runs

### Requirement: ssh-request-plans
The commands `ssh register` and `ssh rotate` SHALL carry the `request-plan` dry-run class and SHALL expose `--dry-run`. A dry run SHALL make no request to GitHub, start no process, and print the requests of the real run in order.

#### Scenario: Dry run on ssh register
- **WHEN** user executes `devops ssh register --dry-run` and `devops --dry-run ssh register`
- **THEN** `github_api` receives no request, no process starts, and the output lists `POST /user/keys` and `POST /user/ssh_signing_keys` with the key as a placeholder, the listing of each endpoint with the condition that the `POST` answers HTTP 422, and the `git config` commands that point git signing at the key

#### Scenario: Dry run on ssh rotate
- **WHEN** user executes `devops ssh rotate --dry-run`
- **THEN** no key file is written, `github_api` receives no request, and the output lists the same requests with the condition that the key is old enough or `--force` is set

#### Scenario: The plan matches the real run
- **WHEN** a test runs `devops ssh register` against `github_api` routes that accept both keys, and compares the requests that it received with the plan lines that have no condition
- **THEN** the methods and the paths are the same, in the same order

### Requirement: ssh-no-external-request
The commands `ssh audit`, `ssh generate`, `ssh list` and `ssh status` SHALL carry the `no-external-request` dry-run class. `ssh audit`, `ssh list` and `ssh status` SHALL run normally under `devops --dry-run` and SHALL have no `--dry-run` option. `ssh generate` SHALL provide a local preview under `--dry-run` that writes no key.

#### Scenario: Dry run on ssh list
- **WHEN** user executes `devops --dry-run ssh list --key-dir <dir>` for a directory with one managed key
- **THEN** the command prints the table of the key, starts no process and sends no request

#### Scenario: ssh status has no dry-run option
- **WHEN** user executes `devops ssh status --dry-run`
- **THEN** the command exits with status 2 and reports `No such option: --dry-run`

#### Scenario: Dry run on ssh generate
- **WHEN** user executes `devops ssh generate --key-dir <dir> --dry-run`
- **THEN** the output says which key file it would write, and neither the private key nor the public key exists afterwards

### Requirement: tls-request-plans
The command `tls enable-k8s` SHALL carry the `request-plan` dry-run class and SHALL expose `--dry-run`. A dry run SHALL start no process and print the kubectl requests of the real run, for each namespace in order.

#### Scenario: Dry run on tls enable-k8s
- **WHEN** user executes `devops tls enable-k8s --namespace web --namespace db --dry-run` and `devops --dry-run tls enable-k8s --namespace web --namespace db`
- **THEN** `process_fake` records no call, and the output lists, for `web` and then for `db`: `kubectl get namespace`, `kubectl create namespace` with the condition that the namespace does not exist, `kubectl create secret tls ... --dry-run=client -o yaml`, and `kubectl apply -f -` with the rendered secret as a placeholder on standard input

#### Scenario: Dry run with a context
- **WHEN** user executes `devops tls enable-k8s --context example --namespace web --dry-run`
- **THEN** each listed kubectl command ends with `--context example`

#### Scenario: The plan matches the real run
- **WHEN** a test runs `devops tls enable-k8s --namespace web` on a `process_fake` that answers `get namespace` with status 1 and the other calls with status 0, and compares the recorded argv with the plan
- **THEN** the four recorded commands and the four plan lines are the same, in the same order

### Requirement: tls-no-external-request
The commands `tls ca`, `tls cert`, `tls homelab`, `tls inspect` and `tls verify` SHALL carry the `no-external-request` dry-run class. `tls inspect` and `tls verify` SHALL run normally under `devops --dry-run`. `tls ca`, `tls cert` and `tls homelab` SHALL provide a local preview under `--dry-run` that writes no key and no certificate.

#### Scenario: Dry run on tls inspect
- **WHEN** user executes `devops --dry-run tls inspect <certificate>`
- **THEN** the command prints the table of the certificate

#### Scenario: Dry run on tls ca
- **WHEN** user executes `devops tls ca --output-dir <dir> --dry-run`
- **THEN** the output says which files it would write, and `<dir>` holds no `ca.crt` and no `ca.key`

#### Scenario: tls ca and tls cert are not MCP tools
- **WHEN** a client lists the tools of the MCP server
- **THEN** the list holds no `tls_ca` and no `tls_cert`, and it holds `tls_inspect`

#### Scenario: Dry run on tls homelab through the root flag
- **WHEN** user executes `devops --dry-run tls homelab --output-dir <dir>`
- **THEN** the output says which bundle it would write, and `<dir>` is empty or absent

### Requirement: uv-request-plans
The four commands `uv lock`, `uv python-install`, `uv run` and `uv sync` SHALL carry the `request-plan` dry-run class and expose `--dry-run`. Under `--dry-run` each command SHALL start no process and SHALL print one request. That request SHALL hold the argument list of the real run, with the uv preview features that the process runner adds.

#### Scenario: Dry run on uv sync
- **WHEN** a user runs `devops uv sync --frozen --dry-run` or `devops --dry-run uv sync --frozen`
- **THEN** no process starts and the plan prints one request whose argument list is `uv --preview-features malware-check,check-command sync --frozen`

#### Scenario: Dry run on uv run keeps the tokens after the separator
- **WHEN** a user runs `devops --dry-run uv run -- pytest --dry-run`
- **THEN** no process starts and the plan prints one request whose argument list ends with `run pytest --dry-run`

#### Scenario: The plan matches the real run
- **WHEN** a test runs `devops uv lock --upgrade` against a process fake that records each call
- **THEN** the recorded argument list equals the argument list of the plan that `devops uv lock --upgrade --dry-run` prints

### Requirement: pipeline-request-plans
The command `pipeline` SHALL carry the `request-plan` dry-run class. Under `--dry-run` it SHALL start no process, print one `dagger call` request built by `build_dagger_cmd`, and print no simulated result.

#### Scenario: Dry run on pipeline
- **WHEN** a user runs `devops pipeline <dir> --function build --dry-run` or `devops --dry-run pipeline <dir> --function build`, where `<dir>` is a directory that exists
- **THEN** no process starts and the plan prints one request that starts with `dagger call -m` and names the function `build`

### Requirement: test-request-plans
The commands `test load`, `test run` and `test sandbox` SHALL carry the `request-plan` dry-run class. Under `--dry-run` each command SHALL make no request and print the requests of the real run: one `k6 run` request for `test load`, one `uv run pytest` request for `test run`, and the container lifecycle requests of `docker sandbox` for `test sandbox`. `test sandbox` SHALL refuse a forbidden workspace before it prints the plan.

#### Scenario: Dry run on test load
- **WHEN** a user runs `devops test load smoke.js --vus 5 --duration 5s --dry-run`
- **THEN** no process starts and the plan prints one request `k6 run` with `--vus 5` and `--duration 5s`, and no simulated metrics

#### Scenario: Dry run on test run
- **WHEN** a user runs `devops --dry-run test run tests/unit -x -k parse`
- **THEN** no process starts and the plan prints one request `uv run pytest -x -k parse tests/unit` with the uv preview features

#### Scenario: Dry run on test sandbox
- **WHEN** a user runs `devops test sandbox --dry-run --workspace <dir> echo hi` with the Docker client patched to fail
- **THEN** no Docker client is built and the plan prints `DOCKER POST /containers/create` followed by the start, wait, logs and remove requests

#### Scenario: Dry run on test sandbox with a forbidden workspace
- **WHEN** a user runs `devops test sandbox --dry-run --workspace /` with the Docker client patched to fail
- **THEN** the command refuses the workspace, exits with the error status, and prints no plan

### Requirement: test-profile-memory-local-preview
The command `test profile-memory` SHALL carry the `no-external-request` dry-run class and expose `--dry-run`. Under `--dry-run` it SHALL run no profiler, import no module and write no file. It SHALL print the target, the iteration count, the limits and the path of the report that the run would write.

#### Scenario: Dry run on profile-memory with a custom target
- **WHEN** a user runs `devops test profile-memory example.module:work --output report.json --dry-run` with the module import patched to fail
- **THEN** the preview names the target and the path `report.json`, no module is imported and no file is written

### Requirement: mcp-local-preview
The command `mcp export-schemas` SHALL carry the `no-external-request` dry-run class and expose `--dry-run`. Under `--dry-run` it SHALL print the directory and the number of tool schemas that it would export, create no directory and write no file.

#### Scenario: Dry run on mcp export-schemas
- **WHEN** a user runs `devops mcp export-schemas --output-dir <dir> --dry-run` with directory creation and file writes patched to fail
- **THEN** the preview prints `<dir>` and the tool count, and nothing is created

### Requirement: mcp-tools-no-external-request
The command `mcp tools` SHALL carry the `no-external-request` dry-run class and declare no `--dry-run` option, so `devops --dry-run mcp tools` runs it as it is.

#### Scenario: Dry run on mcp tools
- **WHEN** a user runs `devops --dry-run mcp tools` with the process runner and the HTTP clients patched to fail
- **THEN** the command prints the table of tools and starts no process

### Requirement: server-request-plans
The commands `mcp serve` and `serve` SHALL carry the `request-plan` dry-run class and expose `--dry-run`. Under `--dry-run` each command SHALL start no server and open no socket. It SHALL print a bind request and a start request built from the values of the real call. `mcp serve --transport sse` SHALL refuse a host that is not loopback without `--allow-remote`, as the real run does. `serve --service --dry-run` SHALL load no settings and read no credential.

#### Scenario: Dry run on mcp serve over sse
- **WHEN** a user runs `devops mcp serve --transport sse --host 127.0.0.1 --port 9090 --dry-run` with `run_mcp_server` patched to fail
- **THEN** the plan prints a bind request for `127.0.0.1:9090` and a start request for the `sse` transport

#### Scenario: Dry run on mcp serve with a remote host
- **WHEN** a user runs `devops mcp serve --transport sse --host 192.0.2.10 --dry-run`
- **THEN** the command refuses the host as the real run does and prints no plan

#### Scenario: Dry run on serve
- **WHEN** a user runs `devops --dry-run serve --host 127.0.0.1 --port 9000 --workers 2` with `uvicorn.run` patched to fail
- **THEN** the plan prints a bind request for `127.0.0.1:9000` and a start request that names 2 workers

### Requirement: ci-fail-to-pass-request-plans
The command `ci fail-to-pass`, and the paths `format fail-to-pass` and `lint fail-to-pass` that share its callback, SHALL carry the `request-plan` dry-run class. Under `--dry-run` the command SHALL start no process, git call included. It SHALL print the ordered requests of the replay, built by the argument builders that the replay uses, with the placeholders `<merge-base>`, `<temp-dir>` and `<changed test files>`.

#### Scenario: Dry run on ci fail-to-pass
- **WHEN** a user runs `devops ci fail-to-pass --base main --dry-run` with the process fake patched to fail on any call
- **THEN** the plan prints the merge base, the two revision checks, the diff, the untracked-file listing (`git ls-files --others`), the worktree add, the archive, the pytest replay, the worktree remove and the worktree prune requests in that order, and no process starts

#### Scenario: The plan matches the replay
- **WHEN** a test runs the replay against a process fake that records each call
- **THEN** each recorded argument list equals the matching request of the plan after the placeholders are replaced
