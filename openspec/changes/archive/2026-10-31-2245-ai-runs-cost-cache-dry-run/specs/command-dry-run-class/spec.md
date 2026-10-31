# Spec Delta

## ADDED Requirements

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
