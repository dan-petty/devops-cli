# command-dry-run-class Specification Delta

## ADDED Requirements

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
