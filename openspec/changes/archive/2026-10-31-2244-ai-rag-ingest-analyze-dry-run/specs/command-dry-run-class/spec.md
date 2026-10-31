# Spec Delta

## ADDED Requirements

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
