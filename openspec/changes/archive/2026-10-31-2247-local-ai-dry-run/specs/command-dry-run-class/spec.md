# Spec Delta

## ADDED Requirements

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
