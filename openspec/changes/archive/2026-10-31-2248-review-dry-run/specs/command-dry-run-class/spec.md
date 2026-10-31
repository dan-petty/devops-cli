# Spec Delta

## ADDED Requirements

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
